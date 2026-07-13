#!/usr/bin/env python3
"""Run independent scan points concurrently in isolated MadGraph processes."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.run_scan import (  # noqa: E402
    CampaignError,
    ScanPoint,
    decimal_arg,
    load_points,
    sha256_file,
)


DEFAULT_PROCESS_DIR = REPOSITORY_ROOT / "MG5_aMC_v3_5_16" / "gg_hhh_restricted5"
DEFAULT_WORK_DIR = REPOSITORY_ROOT / ".work" / "parallel-scan"
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "artifacts" / "lhe"
DEFAULT_LOG_DIR = REPOSITORY_ROOT / "logs" / "parallel-scan"
CLONE_RECORD = ".triple_higgs_clone.json"
SIGNATURE_FILES = (
    "bin/generate_events",
    "Cards/param_card.dat",
    "Cards/run_card.dat",
    "SubProcesses/subproc.mg",
)


@dataclass(frozen=True)
class ParallelTask:
    index: int
    point: ScanPoint
    cores: int
    seed: int
    process_dir: Path
    points_file: Path
    task_output_dir: Path
    log_file: Path

    @property
    def run_name(self) -> str:
        return self.point.run_name


ACTIVE_PROCESSES: set[subprocess.Popen[bytes]] = set()
ACTIVE_LOCK = threading.Lock()


def available_cpu_slots() -> int:
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def allocate_core_slots(total_cores: int, task_count: int) -> tuple[list[int], int]:
    """Return per-task slots and the maximum number of concurrent tasks."""
    if total_cores <= 0:
        raise ValueError("total_cores must be positive")
    if task_count <= 0:
        raise ValueError("task_count must be positive")
    if task_count > total_cores:
        return [1] * task_count, total_cores

    base, remainder = divmod(total_cores, task_count)
    allocations = [base + (index < remainder) for index in range(task_count)]
    return [int(value) for value in allocations], task_count


def load_campaign_points(
    ct2_paths: Sequence[Path], ct3_paths: Sequence[Path]
) -> list[ScanPoint]:
    points: list[ScanPoint] = []
    for scan, paths in (("ct2", ct2_paths), ("ct3", ct3_paths)):
        for path in paths:
            points.extend(load_points(path.expanduser().resolve(), scan))
    if not points:
        raise CampaignError("at least one --ct2-points or --ct3-points file is required")
    names = [point.run_name for point in points]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise CampaignError("duplicate run names: " + ", ".join(duplicates))
    return points


def process_signature(process_dir: Path) -> dict[str, str]:
    signature: dict[str, str] = {}
    for relative in SIGNATURE_FILES:
        path = process_dir / relative
        if not path.is_file():
            raise CampaignError(f"required MadGraph file not found: {path}")
        signature[relative] = sha256_file(path)
    return signature


def clone_payload(source: Path, signature: dict[str, str]) -> dict[str, object]:
    return {
        "format": 1,
        "source_process": str(source.resolve()),
        "source_signature": signature,
    }


def read_clone_record(process_dir: Path) -> dict[str, object]:
    path = process_dir / CLONE_RECORD
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CampaignError(
            f"worker {process_dir} has no valid {CLONE_RECORD}; rebuild it"
        ) from exc


def repair_external_symlinks(source: Path, temporary: Path, destination: Path) -> None:
    """Keep links outside a process valid when a clone has a different depth."""
    source = source.resolve()
    for current, directories, files in os.walk(source, followlinks=False):
        for name in [*directories, *files]:
            source_link = Path(current) / name
            if not source_link.is_symlink():
                continue
            raw_target = Path(os.readlink(source_link))
            resolved_target = (
                raw_target.resolve()
                if raw_target.is_absolute()
                else (source_link.parent / raw_target).resolve()
            )
            try:
                internal_relative = resolved_target.relative_to(source)
            except ValueError:
                internal_relative = None

            replacement: Path | None = None
            if raw_target.is_absolute() and internal_relative is not None:
                replacement = destination / internal_relative
            elif not raw_target.is_absolute() and internal_relative is None:
                replacement = resolved_target
            if replacement is None:
                continue

            copied_link = temporary / source_link.relative_to(source)
            copied_link.unlink()
            copied_link.symlink_to(replacement)


def copy_process(source: Path, destination: Path, payload: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    if temporary.exists():
        shutil.rmtree(temporary)

    result = subprocess.run(
        ["cp", "-a", "--reflink=auto", str(source), str(temporary)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode:
        if temporary.exists():
            shutil.rmtree(temporary)
        shutil.copytree(source, temporary, symlinks=True)

    (temporary / ".triple_higgs_scan.lock").unlink(missing_ok=True)
    repair_external_symlinks(source, temporary, destination)
    (temporary / CLONE_RECORD).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)


def prepare_worker(
    source: Path,
    destination: Path,
    signature: dict[str, str],
    *,
    rebuild: bool,
) -> str:
    payload = clone_payload(source, signature)
    if destination.exists() and rebuild:
        shutil.rmtree(destination)
    if not destination.exists():
        copy_process(source, destination, payload)
        return "created"

    if read_clone_record(destination) != payload:
        raise CampaignError(
            f"worker {destination} was cloned from a different process; "
            "use --rebuild-workers"
        )
    if process_signature(destination) != signature:
        raise CampaignError(
            f"worker {destination} has modified process inputs; use --rebuild-workers"
        )
    return "reused"


def write_one_point(path: Path, point: ScanPoint) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "k3", "k4", point.scan])
        writer.writerow([point.name, str(point.k3), str(point.k4), str(point.active_contact)])
    os.replace(temporary, path)


def build_tasks(
    points: Sequence[ScanPoint],
    allocations: Sequence[int],
    *,
    seed_start: int,
    work_dir: Path,
    log_dir: Path,
) -> list[ParallelTask]:
    return [
        ParallelTask(
            index=index,
            point=point,
            cores=allocations[index],
            seed=seed_start + index,
            process_dir=work_dir / "processes" / point.run_name,
            points_file=work_dir / "points" / f"{point.run_name}.csv",
            task_output_dir=work_dir / "outputs" / point.run_name,
            log_file=log_dir / f"{point.run_name}.log",
        )
        for index, point in enumerate(points)
    ]


def task_command(args: argparse.Namespace, task: ParallelTask) -> list[str]:
    command = [
        sys.executable,
        str(REPOSITORY_ROOT / "scripts" / "run_scan.py"),
        "--scan",
        task.point.scan,
        "--points",
        str(task.points_file),
        "--events",
        str(args.events),
        "--cores",
        str(task.cores),
        "--survey-splitting",
        str(task.cores),
        "--ebeam",
        str(args.ebeam),
        "--ct1",
        str(args.ct1),
        "--seed-start",
        str(task.seed),
        "--process-dir",
        str(task.process_dir),
        "--output-dir",
        str(task.task_output_dir),
        f"--{args.run_mode}",
    ]
    if args.pdlabel is not None:
        command.extend(["--pdlabel", args.pdlabel, "--lhaid", str(args.lhaid)])
    if args.dynamical_scale_choice is not None:
        command.extend(
            ["--dynamical-scale-choice", str(args.dynamical_scale_choice)]
        )
    if args.use_systematics is not None:
        command.append("--systematics" if args.use_systematics else "--no-systematics")
    return command


def run_task(args: argparse.Namespace, task: ParallelTask) -> ParallelTask:
    task.log_file.parent.mkdir(parents=True, exist_ok=True)
    task.task_output_dir.mkdir(parents=True, exist_ok=True)
    command = task_command(args, task)
    with task.log_file.open("a", encoding="utf-8") as log:
        log.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] "
            + shlex.join(command)
            + "\n"
        )
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=REPOSITORY_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        with ACTIVE_LOCK:
            ACTIVE_PROCESSES.add(process)
        try:
            return_code = process.wait()
        finally:
            with ACTIVE_LOCK:
                ACTIVE_PROCESSES.discard(process)
    if return_code:
        raise CampaignError(
            f"{task.run_name} failed with exit code {return_code}; see {task.log_file}"
        )
    return task


def stop_active_processes() -> None:
    with ACTIVE_LOCK:
        processes = list(ACTIVE_PROCESSES)
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
            except ProcessLookupError:
                pass

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if all(process.poll() is not None for process in processes):
            return
        time.sleep(0.2)
    for process in processes:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def latest_task_record(task: ParallelTask) -> dict[str, object]:
    manifest = task.task_output_dir / "manifest.jsonl"
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CampaignError(f"cannot read task manifest {manifest}: {exc}") from exc
    for line in reversed(lines):
        record = json.loads(line)
        if record.get("run_name") == task.run_name:
            return record
    raise CampaignError(f"task manifest has no record for {task.run_name}: {manifest}")


def publish_task(
    task: ParallelTask, output_dir: Path, *, allow_replace: bool
) -> Path:
    record = latest_task_record(task)
    source = Path(str(record["lhe"]))
    if not source.is_file():
        raise CampaignError(f"task LHE is missing: {source}")
    expected_hash = str(record["lhe_sha256"])
    if sha256_file(source) != expected_hash:
        raise CampaignError(f"task LHE checksum changed: {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / source.name
    if destination.exists() and not allow_replace:
        if sha256_file(destination) != expected_hash:
            raise CampaignError(
                f"refusing to replace a different published LHE: {destination}"
            )
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)

    record.update(
        {
            "lhe": str(destination.resolve()),
            "parallel_cpu_slots": task.cores,
            "parallel_seed": task.seed,
            "worker_process_dir": str(task.process_dir.resolve()),
        }
    )
    with (output_dir / "manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ct2-points", type=Path, action="append", default=[])
    parser.add_argument("--ct3-points", type=Path, action="append", default=[])
    parser.add_argument("--events", type=int, required=True)
    parser.add_argument("--total-cores", type=int, required=True)
    parser.add_argument("--ebeam", type=decimal_arg, default=Decimal("6800"))
    parser.add_argument("--ct1", type=decimal_arg, default=Decimal("1"))
    parser.add_argument("--seed-start", type=int, default=13001)
    parser.add_argument("--pdlabel")
    parser.add_argument("--lhaid", type=int)
    parser.add_argument("--dynamical-scale-choice", type=int)
    systematics = parser.add_mutually_exclusive_group()
    systematics.add_argument(
        "--systematics", dest="use_systematics", action="store_const", const=True
    )
    systematics.add_argument(
        "--no-systematics", dest="use_systematics", action="store_const", const=False
    )
    parser.add_argument("--process-dir", type=Path, default=DEFAULT_PROCESS_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", dest="run_mode", action="store_const", const="resume")
    mode.add_argument("--force", dest="run_mode", action="store_const", const="force")
    parser.set_defaults(run_mode="resume")
    parser.add_argument("--rebuild-workers", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-oversubscription", action="store_true")
    args = parser.parse_args()
    if args.events <= 0:
        parser.error("--events must be positive")
    if args.total_cores <= 0:
        parser.error("--total-cores must be positive")
    if args.ebeam <= 0:
        parser.error("--ebeam must be positive")
    if args.seed_start <= 0:
        parser.error("--seed-start must be positive for isolated parallel workers")
    if (args.pdlabel is None) != (args.lhaid is None):
        parser.error("--pdlabel and --lhaid must be supplied together")
    return args


def main() -> int:
    args = parse_args()
    source = args.process_dir.expanduser().resolve()
    work_dir = args.work_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    log_dir = args.log_dir.expanduser().resolve()
    points = load_campaign_points(args.ct2_points, args.ct3_points)
    allocations, max_parallel = allocate_core_slots(args.total_cores, len(points))
    tasks = build_tasks(
        points,
        allocations,
        seed_start=args.seed_start,
        work_dir=work_dir,
        log_dir=log_dir,
    )
    available = available_cpu_slots()
    if args.total_cores > available and not args.allow_oversubscription:
        raise CampaignError(
            f"requested {args.total_cores} CPU slots but this process can use only "
            f"{available}; reduce --total-cores"
        )

    plan = {
        "source_process": str(source),
        "work_dir": str(work_dir),
        "output_dir": str(output_dir),
        "events_per_point": args.events,
        "beam_energy_per_proton_gev": str(args.ebeam),
        "available_cpu_slots": available,
        "requested_cpu_slots": args.total_cores,
        "maximum_parallel_points": max_parallel,
        "seed_start": args.seed_start,
        "points": [
            {
                "run_name": task.run_name,
                "cores": task.cores,
                "survey_splitting": task.cores,
                "seed": task.seed,
                "couplings": {
                    name: str(value)
                    for name, value in task.point.couplings(args.ct1).items()
                },
            }
            for task in tasks
        ],
    }
    print(json.dumps(plan, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    if (source / ".triple_higgs_scan.lock").exists():
        raise CampaignError(f"source process is currently locked: {source}")
    signature = process_signature(source)
    for number, task in enumerate(tasks, start=1):
        write_one_point(task.points_file, task.point)
        status = prepare_worker(
            source,
            task.process_dir,
            signature,
            rebuild=args.rebuild_workers,
        )
        print(f"Prepared {number}/{len(tasks)} {task.run_name}: {status}", flush=True)
    if args.prepare_only:
        print(f"Prepared {len(tasks)} isolated workers; no events were generated.")
        return 0

    print(
        f"Launching {len(tasks)} points with at most {max_parallel} concurrent "
        f"points and {args.total_cores} total CPU slots.",
        flush=True,
    )
    executor = ThreadPoolExecutor(max_workers=max_parallel)
    futures: dict[Future[ParallelTask], ParallelTask] = {
        executor.submit(run_task, args, task): task for task in tasks
    }
    completed = 0
    try:
        for future in as_completed(futures):
            task = future.result()
            destination = publish_task(
                task, output_dir, allow_replace=args.run_mode == "force"
            )
            completed += 1
            print(
                f"Completed {completed}/{len(tasks)} {task.run_name}: {destination}",
                flush=True,
            )
    except BaseException:
        stop_active_processes()
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    print(f"Completed all {len(tasks)} parallel scan points.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as error:
        raise SystemExit(f"error: {error}") from error
