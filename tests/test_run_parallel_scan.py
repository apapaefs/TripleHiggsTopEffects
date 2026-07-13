from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.run_parallel_scan import (
    allocate_core_slots,
    build_tasks,
    load_campaign_points,
    prepare_worker,
    process_signature,
    write_one_point,
)
from scripts.run_scan import CampaignError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class CoreAllocationTests(unittest.TestCase):
    def test_64_slots_are_distributed_across_24_points(self) -> None:
        allocations, max_parallel = allocate_core_slots(64, 24)
        self.assertEqual(allocations, [3] * 16 + [2] * 8)
        self.assertEqual(sum(allocations), 64)
        self.assertEqual(max_parallel, 24)

    def test_more_points_than_slots_run_in_waves(self) -> None:
        allocations, max_parallel = allocate_core_slots(4, 10)
        self.assertEqual(allocations, [1] * 10)
        self.assertEqual(max_parallel, 4)


class ParallelGridTests(unittest.TestCase):
    def test_production_grid_builds_24_unique_tasks(self) -> None:
        points = load_campaign_points(
            [REPOSITORY_ROOT / "scans" / "ct2.13tev.csv"],
            [REPOSITORY_ROOT / "scans" / "ct3.13tev.csv"],
        )
        allocations, _ = allocate_core_slots(64, len(points))
        tasks = build_tasks(
            points,
            allocations,
            seed_start=13001,
            work_dir=Path("/work"),
            log_dir=Path("/logs"),
        )
        self.assertEqual(len(tasks), 24)
        self.assertEqual(len({task.run_name for task in tasks}), 24)
        self.assertEqual(tasks[0].seed, 13001)
        self.assertEqual(tasks[-1].seed, 13024)
        self.assertEqual(sum(task.cores for task in tasks), 64)

    def test_one_point_csv_round_trips(self) -> None:
        points = load_campaign_points(
            [REPOSITORY_ROOT / "scans" / "ct2.13tev.csv"], []
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "one.csv"
            write_one_point(path, points[0])
            loaded = load_campaign_points([path], [])
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].k3, Decimal("-8"))
        self.assertEqual(loaded[0].active_contact, Decimal("-0.3"))


class WorkerCloneTests(unittest.TestCase):
    def test_worker_clone_is_reusable_and_detects_modified_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            for relative in (
                "bin/generate_events",
                "Cards/param_card.dat",
                "Cards/run_card.dat",
                "SubProcesses/subproc.mg",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative + "\n", encoding="utf-8")
            external = root / "external" / "libexample.a"
            external.parent.mkdir(parents=True)
            external.write_text("library\n", encoding="utf-8")
            external_link = source / "lib" / "libexample.a"
            external_link.parent.mkdir(parents=True)
            external_link.symlink_to(Path("../../external/libexample.a"))
            signature = process_signature(source)
            worker = root / "worker"

            self.assertEqual(
                prepare_worker(source, worker, signature, rebuild=False), "created"
            )
            self.assertEqual(
                prepare_worker(source, worker, signature, rebuild=False), "reused"
            )
            self.assertEqual(
                (worker / "lib" / "libexample.a").resolve(), external.resolve()
            )

            (worker / "Cards" / "run_card.dat").write_text(
                "changed\n", encoding="utf-8"
            )
            with self.assertRaises(CampaignError):
                prepare_worker(source, worker, signature, rebuild=False)


if __name__ == "__main__":
    unittest.main()
