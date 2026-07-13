#!/usr/bin/env python3
"""Generate restricted-model triple-Higgs LHE files from a CSV point list."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator, Mapping, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MG5_ROOT = REPOSITORY_ROOT / "MG5_aMC_v3_5_16"
LHA_CODES = {"ct1": 993, "ct2": 994, "ct3": 995, "c3": 996, "d4": 997}
RUN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*$")
BLOCK_RE = re.compile(r"^\s*BLOCK\s+(\S+)", re.IGNORECASE)
SLHA_ENTRY_RE = re.compile(r"^(\s*)(\d+)(\s+)([^\s#]+)(.*)$")
RUN_CARD_RE = re.compile(r"^(\s*)(\S+)(\s*=\s*)([A-Za-z0-9_]+)(\b.*)$")


class CampaignError(RuntimeError):
    """A user-actionable campaign configuration or runtime error."""


@dataclass(frozen=True)
class ScanPoint:
    name: str
    scan: str
    c3: Decimal
    d4: Decimal
    active_contact: Decimal

    def couplings(self, ct1: Decimal) -> dict[str, Decimal]:
        return {
            "ct1": ct1,
            "ct2": self.active_contact if self.scan == "ct2" else Decimal(0),
            "ct3": self.active_contact if self.scan == "ct3" else Decimal(0),
            "c3": self.c3,
            "d4": self.d4,
        }

    @property
    def run_name(self) -> str:
        return f"{self.scan}_{self.name}"


def decimal_arg(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value}") from exc
    if not result.is_finite():
        raise argparse.ArgumentTypeError(f"number must be finite: {value}")
    return result


def parse_decimal(value: str, *, field: str, line: int) -> Decimal:
    try:
        result = Decimal(value.strip())
    except InvalidOperation as exc:
        raise CampaignError(f"line {line}: invalid {field} value {value!r}") from exc
    if not result.is_finite():
        raise CampaignError(f"line {line}: {field} must be finite")
    return result


def load_points(path: Path, scan: str) -> list[ScanPoint]:
    active = scan
    expected = ["name", "c3", "d4", active]
    try:
        handle = path.open(encoding="utf-8", newline="")
    except OSError as exc:
        raise CampaignError(f"cannot read points file {path}: {exc}") from exc

    with handle:
        rows = (
            line for line in handle if line.strip() and not line.lstrip().startswith("#")
        )
        reader = csv.DictReader(rows)
        if reader.fieldnames != expected:
            raise CampaignError(
                f"{path}: expected CSV columns {','.join(expected)}, got "
                f"{','.join(reader.fieldnames or [])}"
            )
        points: list[ScanPoint] = []
        names: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            name = (row["name"] or "").strip()
            if not RUN_NAME_RE.fullmatch(name):
                raise CampaignError(
                    f"line {line_number}: name must contain only letters, digits, "
                    "and underscores, and must not start with an underscore"
                )
            if name in names:
                raise CampaignError(f"line {line_number}: duplicate point name {name!r}")
            names.add(name)
            points.append(
                ScanPoint(
                    name=name,
                    scan=scan,
                    c3=parse_decimal(row["c3"], field="c3", line=line_number),
                    d4=parse_decimal(row["d4"], field="d4", line=line_number),
                    active_contact=parse_decimal(
                        row[active], field=active, line=line_number
                    ),
                )
            )
    if not points:
        raise CampaignError(f"{path}: no scan points found")
    return points


def format_decimal(value: Decimal) -> str:
    return format(value, ".12E")


def replace_slha_parameters(text: str, values: Mapping[int, Decimal]) -> str:
    lines = text.splitlines(keepends=True)
    current_block: str | None = None
    replaced: set[int] = set()

    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        block_match = BLOCK_RE.match(body)
        if block_match:
            current_block = block_match.group(1).upper()
            continue
        if current_block != "BSMINPUTS":
            continue
        match = SLHA_ENTRY_RE.match(body)
        if not match:
            continue
        code = int(match.group(2))
        if code not in values:
            continue
        lines[index] = (
            f"{match.group(1)}{match.group(2)}{match.group(3)}"
            f"{format_decimal(values[code])}{match.group(5)}{ending}"
        )
        replaced.add(code)

    missing = set(values) - replaced
    if missing:
        raise CampaignError(
            "param_card.dat is missing BSMINPUTS codes "
            + ", ".join(str(code) for code in sorted(missing))
        )
    return "".join(lines)


def extract_slha_parameters(text: str, codes: Sequence[int]) -> dict[int, Decimal]:
    wanted = set(codes)
    found: dict[int, Decimal] = {}
    current_block: str | None = None
    for line in text.splitlines():
        block_match = BLOCK_RE.match(line)
        if block_match:
            current_block = block_match.group(1).upper()
            continue
        if current_block != "BSMINPUTS":
            continue
        match = SLHA_ENTRY_RE.match(line)
        if not match:
            continue
        code = int(match.group(2))
        if code in wanted:
            try:
                found[code] = Decimal(match.group(4).replace("d", "e").replace("D", "E"))
            except InvalidOperation as exc:
                raise CampaignError(f"invalid value for BSMINPUTS code {code}") from exc
    return found


def replace_run_settings(text: str, updates: Mapping[str, str]) -> str:
    lines = text.splitlines(keepends=True)
    replaced: set[str] = set()
    for index, line in enumerate(lines):
        body = line.rstrip("\r\n")
        ending = line[len(body) :]
        match = RUN_CARD_RE.match(body)
        if not match:
            continue
        name = match.group(4).lower()
        if name not in updates:
            continue
        lines[index] = (
            f"{match.group(1)}{updates[name]}{match.group(3)}"
            f"{match.group(4)}{match.group(5)}{ending}"
        )
        replaced.add(name)
    missing = set(updates) - replaced
    if missing:
        raise CampaignError(
            "run_card.dat is missing settings " + ", ".join(sorted(missing))
        )
    return "".join(lines)


def extract_run_settings(text: str, names: Sequence[str]) -> dict[str, str]:
    wanted = {name.lower() for name in names}
    found: dict[str, str] = {}
    for line in text.splitlines():
        match = RUN_CARD_RE.match(line)
        if not match:
            continue
        name = match.group(4).lower()
        if name in wanted:
            found[name] = match.group(2)
    return found


def atomic_write(path: Path, data: bytes) -> None:
    mode = path.stat().st_mode
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def process_lock(process_dir: Path) -> Iterator[None]:
    lock_path = process_dir / ".triple_higgs_scan.lock"
    payload = (
        f"pid={os.getpid()}\nhost={socket.gethostname()}\n"
        f"started={datetime.now(timezone.utc).isoformat()}\n"
    )
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError as exc:
        try:
            owner = lock_path.read_text(encoding="utf-8").strip()
        except OSError:
            owner = "unreadable lock"
        raise CampaignError(f"process directory is locked ({owner})") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_banner(run_dir: Path) -> Path:
    banners = list(run_dir.glob("*_banner.txt"))
    if not banners:
        raise CampaignError(f"no MadGraph banner found in {run_dir}")
    return max(banners, key=lambda path: path.stat().st_mtime_ns)


def run_lhe(run_dir: Path) -> Path:
    candidates = [
        run_dir / "unweighted_events.lhe.gz",
        run_dir / "unweighted_events.lhe",
    ]
    for candidate in candidates:
        if candidate.is_file() and candidate.stat().st_size:
            return candidate
    raise CampaignError(f"no completed unweighted LHE found in {run_dir}")


def validate_completed_run(
    run_dir: Path,
    expected_couplings: Mapping[str, Decimal],
    *,
    events: int,
    ebeam: Decimal,
    seed: int,
) -> tuple[Path, Path]:
    lhe = run_lhe(run_dir)
    banner = latest_banner(run_dir)
    text = banner.read_text(encoding="utf-8", errors="replace")
    expected_by_code = {LHA_CODES[name]: value for name, value in expected_couplings.items()}
    actual = extract_slha_parameters(text, list(expected_by_code))
    if actual != expected_by_code:
        raise CampaignError(
            f"existing run {run_dir.name} has different couplings: {actual}"
        )
    settings = extract_run_settings(text, ["nevents", "ebeam1", "ebeam2", "iseed"])
    if int(settings.get("nevents", "-1")) != events:
        raise CampaignError(f"existing run {run_dir.name} has a different nevents")
    if Decimal(settings.get("ebeam1", "NaN")) != ebeam or Decimal(
        settings.get("ebeam2", "NaN")
    ) != ebeam:
        raise CampaignError(f"existing run {run_dir.name} has a different beam energy")
    if seed and int(settings.get("iseed", "-1")) != seed:
        raise CampaignError(f"existing run {run_dir.name} has a different random seed")
    return lhe, banner


def git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def banner_summary(banner: Path) -> dict[str, str | int | None]:
    text = banner.read_text(encoding="utf-8", errors="replace")
    cross_section = re.search(
        r"Integrated weight \(pb\)\s*:\s*([-+0-9.eEdD]+)", text
    )
    event_count = re.search(r"Number of Events\s*:\s*(\d+)", text)
    settings = extract_run_settings(text, ["iseed", "pdlabel", "lhaid"])
    return {
        "cross_section_pb": (
            cross_section.group(1).replace("D", "E").replace("d", "e")
            if cross_section
            else None
        ),
        "generated_events": int(event_count.group(1)) if event_count else None,
        "seed": int(settings["iseed"]) if "iseed" in settings else None,
        "pdlabel": settings.get("pdlabel"),
        "lhaid": settings.get("lhaid"),
    }


def copy_and_record(
    *,
    lhe: Path,
    banner: Path,
    point: ScanPoint,
    couplings: Mapping[str, Decimal],
    output_dir: Path,
    status: str,
    events: int,
    ebeam: Decimal,
) -> Path:
    suffix = ".lhe.gz" if lhe.suffix == ".gz" else ".lhe"
    destination = output_dir / f"{point.run_name}.unweighted_events{suffix}"
    temporary = destination.with_name(destination.name + ".tmp")
    shutil.copy2(lhe, temporary)
    os.replace(temporary, destination)
    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "run_name": point.run_name,
        "scan": point.scan,
        "couplings": {name: str(value) for name, value in couplings.items()},
        "requested_events": events,
        "beam_energy_gev": str(ebeam),
        "lhe": str(destination.resolve()),
        "lhe_bytes": destination.stat().st_size,
        "lhe_sha256": sha256_file(destination),
        "banner": str(banner.resolve()),
        "git_revision": git_revision(),
        **banner_summary(banner),
    }
    with (output_dir / "manifest.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return destination


def plan_payload(
    points: Sequence[ScanPoint],
    *,
    ct1: Decimal,
    events: int,
    ebeam: Decimal,
    cores: int,
    process_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    return {
        "process_dir": str(process_dir),
        "output_dir": str(output_dir),
        "events_per_point": events,
        "beam_energy_per_proton_gev": str(ebeam),
        "cores": cores,
        "points": [
            {
                "run_name": point.run_name,
                "couplings": {
                    name: str(value) for name, value in point.couplings(ct1).items()
                },
            }
            for point in points
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", choices=("ct2", "ct3"), required=True)
    parser.add_argument("--points", type=Path, required=True)
    parser.add_argument("--events", type=int, required=True)
    parser.add_argument("--cores", type=int, default=1)
    parser.add_argument("--ebeam", type=decimal_arg, default=Decimal("6800"))
    parser.add_argument("--ct1", type=decimal_arg, default=Decimal("1"))
    parser.add_argument(
        "--seed-start",
        type=int,
        default=0,
        help="first explicit seed; zero lets MadGraph assign seeds",
    )
    parser.add_argument("--pdlabel", help="optional run-card pdlabel override")
    parser.add_argument("--lhaid", type=int, help="optional run-card lhaid override")
    parser.add_argument("--mg5-root", type=Path, default=DEFAULT_MG5_ROOT)
    parser.add_argument("--process-dir", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=REPOSITORY_ROOT / "artifacts" / "lhe"
    )
    parser.add_argument("--dry-run", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--resume", action="store_true")
    mode.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.events <= 0:
        parser.error("--events must be positive")
    if args.cores <= 0:
        parser.error("--cores must be positive")
    if args.ebeam <= 0:
        parser.error("--ebeam must be positive")
    if args.seed_start < 0:
        parser.error("--seed-start must be non-negative")
    if (args.pdlabel is None) != (args.lhaid is None):
        parser.error("--pdlabel and --lhaid must be supplied together")
    return args


def main() -> int:
    args = parse_args()
    points_path = args.points.expanduser().resolve()
    points = load_points(points_path, args.scan)
    mg5_root = args.mg5_root.expanduser().resolve()
    process_dir = (
        args.process_dir.expanduser().resolve()
        if args.process_dir
        else mg5_root / "gg_hhh_restricted5"
    )
    output_dir = args.output_dir.expanduser().resolve()

    payload = plan_payload(
        points,
        ct1=args.ct1,
        events=args.events,
        ebeam=args.ebeam,
        cores=args.cores,
        process_dir=process_dir,
        output_dir=output_dir,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.dry_run:
        return 0

    executable = process_dir / "bin" / "generate_events"
    param_card = process_dir / "Cards" / "param_card.dat"
    run_card = process_dir / "Cards" / "run_card.dat"
    for required in (executable, param_card, run_card):
        if not required.is_file():
            raise CampaignError(f"required MadGraph file not found: {required}")

    output_dir.mkdir(parents=True, exist_ok=True)
    original_param = param_card.read_bytes()
    original_run = run_card.read_bytes()

    with process_lock(process_dir):
        try:
            for index, point in enumerate(points):
                couplings = point.couplings(args.ct1)
                seed = args.seed_start + index if args.seed_start else 0
                run_dir = process_dir / "Events" / point.run_name

                if run_dir.exists() and not args.force:
                    if not args.resume:
                        raise CampaignError(
                            f"run already exists: {run_dir}; use --resume or --force"
                        )
                    lhe, banner = validate_completed_run(
                        run_dir,
                        couplings,
                        events=args.events,
                        ebeam=args.ebeam,
                        seed=seed,
                    )
                    destination = copy_and_record(
                        lhe=lhe,
                        banner=banner,
                        point=point,
                        couplings=couplings,
                        output_dir=output_dir,
                        status="reused",
                        events=args.events,
                        ebeam=args.ebeam,
                    )
                    print(f"Reused {point.run_name}: {destination}")
                    continue

                param_values = {
                    LHA_CODES[name]: value for name, value in couplings.items()
                }
                updated_param = replace_slha_parameters(
                    original_param.decode("utf-8"), param_values
                )
                run_updates = {
                    "nevents": str(args.events),
                    "iseed": str(seed),
                    "ebeam1": format_decimal(args.ebeam),
                    "ebeam2": format_decimal(args.ebeam),
                }
                if args.pdlabel is not None:
                    run_updates["pdlabel"] = args.pdlabel
                    run_updates["lhaid"] = str(args.lhaid)
                updated_run = replace_run_settings(
                    original_run.decode("utf-8"), run_updates
                )
                atomic_write(param_card, updated_param.encode("utf-8"))
                atomic_write(run_card, updated_run.encode("utf-8"))

                command = [
                    str(executable),
                    point.run_name,
                    "-f",
                    "--laststep=parton",
                ]
                if args.cores > 1:
                    command.extend(["--multicore", f"--nb_core={args.cores}"])
                print("Running:", " ".join(command), flush=True)
                try:
                    subprocess.run(command, cwd=process_dir, check=True)
                except subprocess.CalledProcessError as exc:
                    raise CampaignError(
                        f"MadGraph failed for {point.run_name} with exit code "
                        f"{exc.returncode}"
                    ) from exc

                lhe = run_lhe(run_dir)
                banner = latest_banner(run_dir)
                destination = copy_and_record(
                    lhe=lhe,
                    banner=banner,
                    point=point,
                    couplings=couplings,
                    output_dir=output_dir,
                    status="generated",
                    events=args.events,
                    ebeam=args.ebeam,
                )
                print(f"Generated {point.run_name}: {destination}")
        finally:
            atomic_write(param_card, original_param)
            atomic_write(run_card, original_run)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as error:
        raise SystemExit(f"error: {error}") from error
