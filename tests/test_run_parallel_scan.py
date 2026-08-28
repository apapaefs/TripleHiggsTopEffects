from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from scripts.run_parallel_scan import (
    allocate_core_slots,
    build_tasks,
    load_campaign_points,
    prepare_worker,
    process_signature,
    select_shards,
    task_command,
    write_one_point,
)
from scripts.run_scan import DEFAULT_CT1, CampaignError


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

    def test_fixed_96_core_points_run_two_at_a_time(self) -> None:
        allocations, max_parallel = allocate_core_slots(
            192, 55, cores_per_point=96
        )
        self.assertEqual(allocations, [96] * 55)
        self.assertEqual(max_parallel, 2)


class ParallelGridTests(unittest.TestCase):
    @staticmethod
    def full_corrected_campaign():
        return load_campaign_points(
            [
                REPOSITORY_ROOT / "scans" / "ct2.13tev.csv",
                REPOSITORY_ROOT / "scans" / "ct2.13tev-additional.csv",
            ],
            [
                REPOSITORY_ROOT / "scans" / "ct3.13tev.csv",
                REPOSITORY_ROOT / "scans" / "ct3.13tev-additional.csv",
            ],
        )

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

    def test_thermal_guard_marker_wraps_each_isolated_worker(self) -> None:
        point = load_campaign_points(
            [], [REPOSITORY_ROOT / "scans" / "ct3.14tev-sm-shapes.csv"]
        )[0]
        task = build_tasks(
            [point],
            [96],
            seed_start=36001,
            work_dir=Path("/work"),
            log_dir=Path("/logs"),
        )[0]
        args = SimpleNamespace(
            events=100000,
            ebeam=Decimal("7000"),
            ct1=Decimal("0"),
            run_mode="resume",
            pdlabel="lhapdf",
            lhaid=331900,
            dynamical_scale_choice=3,
            scalefact=Decimal("0.5"),
            use_systematics=False,
            thermal_guard_wrapper=Path("/campaign/thermal_guard_wrapper.sh"),
            thermal_guard_controller_script="run_validation_campaign.py",
            thermal_guard_controller_action="full",
        )

        command = task_command(args, task)

        self.assertEqual(
            command[:4],
            [
                "/campaign/thermal_guard_wrapper.sh",
                "run_validation_campaign.py",
                "full",
                "--",
            ],
        )
        self.assertIn("run_scan.py", command[5])
        self.assertIn("--scalefact", command)
        self.assertEqual(command[command.index("--scalefact") + 1], "0.5")

    def test_55_points_split_into_disjoint_18_and_37_point_host_shards(self) -> None:
        points = self.full_corrected_campaign()
        tiresias = select_shards(points, 3, [1])
        odysseus = select_shards(points, 3, [0, 2])
        self.assertEqual(len(points), 55)
        self.assertEqual(len(tiresias), 18)
        self.assertEqual(len(odysseus), 37)
        self.assertFalse(
            {point.run_name for point in tiresias}
            & {point.run_name for point in odysseus}
        )
        self.assertEqual(
            {point.run_name for point in points},
            {point.run_name for point in tiresias + odysseus},
        )

    def test_corrected_campaign_exactly_matches_the_physics_contract(self) -> None:
        points = self.full_corrected_campaign()
        expected_kappas = {
            (Decimal("-8"), Decimal("50")),
            (Decimal("6"), Decimal("50")),
            (Decimal("-5"), Decimal("-50")),
            (Decimal("3"), Decimal("-50")),
            (Decimal("1"), Decimal("1")),
        }
        expected_contacts = {
            "ct2": {
                Decimal("-4"),
                Decimal("-0.3"),
                Decimal("-0.1"),
                Decimal("0"),
                Decimal("0.1"),
                Decimal("0.6"),
                Decimal("4"),
            },
            "ct3": {
                Decimal("-5"),
                Decimal("-0.5"),
                Decimal("0.5"),
                Decimal("5"),
            },
        }
        self.assertEqual({(point.k3, point.k4) for point in points}, expected_kappas)
        for k3, k4 in expected_kappas:
            for scan, expected in expected_contacts.items():
                actual = {
                    point.active_contact
                    for point in points
                    if point.scan == scan and (point.k3, point.k4) == (k3, k4)
                }
                self.assertEqual(actual, expected)

        for point in points:
            couplings = point.card_couplings(DEFAULT_CT1)
            self.assertEqual(couplings["ct1"], Decimal("0"))
            self.assertEqual(couplings["d3"], point.k3 - Decimal("1"))
            self.assertEqual(couplings["d4"], point.k4 - Decimal("1"))
            inactive = "ct3" if point.scan == "ct2" else "ct2"
            self.assertEqual(couplings[inactive], Decimal("0"))


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
