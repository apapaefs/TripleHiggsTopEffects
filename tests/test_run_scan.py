from __future__ import annotations

import tempfile
import unittest
import sys
from decimal import Decimal
from pathlib import Path

from scripts.run_scan import (
    CampaignError,
    DEFAULT_CT1,
    LHA_CODES,
    extract_run_settings,
    extract_slha_parameters,
    generate_events_command,
    integration_result,
    load_points,
    replace_run_settings,
    replace_slha_parameters,
    set_pdf_labels,
    set_optional_run_setting,
)
from scripts.mg5_generate_events import repair_lhapdf_include


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


PARAM_CARD = """BLOCK BSMINPUTS #
      993 1.300000e+00 # ct1
      994 1.400000e+00 # ct2
      995 1.500000e+00 # ct3
      996 1.600000e+00 # d3
      997 1.700000e+00 # d4
BLOCK MASS
       25 1.250000e+02 # mh
"""

RUN_CARD = """  1000 = nevents ! requested events
  0 = iseed ! random seed
  6800.0 = ebeam1 ! beam energy
  6800.0 = ebeam2 ! beam energy
  nn23lo1 = pdlabel ! PDF
  230000 = lhaid ! PDF ID
  -1 = dynamical_scale_choice ! scale
  1.0 = scalefact ! scale multiplier
  True = use_syst ! systematics
"""


class PointTests(unittest.TestCase):
    def write_csv(self, content: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        path = directory / "points.csv"
        path.write_text(content, encoding="utf-8")
        return path

    def test_ct2_point_sets_inactive_ct3_to_zero(self) -> None:
        path = self.write_csv("name,k3,k4,ct2\np1,2,-1,0.5\n")
        point = load_points(path, "ct2")[0]
        self.assertEqual(point.run_name, "ct2_p1")
        self.assertEqual(point.kappas(), {"k3": Decimal("2"), "k4": Decimal("-1")})
        self.assertEqual(
            point.card_couplings(DEFAULT_CT1),
            {
                "ct1": Decimal("0"),
                "ct2": Decimal("0.5"),
                "ct3": Decimal("0"),
                "d3": Decimal("1"),
                "d4": Decimal("-2"),
            },
        )

    def test_ct3_point_sets_inactive_ct2_to_zero(self) -> None:
        path = self.write_csv("# example\nname,k3,k4,ct3\np2,1,1,-0.25\n")
        point = load_points(path, "ct3")[0]
        self.assertEqual(point.card_couplings(DEFAULT_CT1)["ct2"], Decimal("0"))
        self.assertEqual(
            point.card_couplings(DEFAULT_CT1)["ct3"], Decimal("-0.25")
        )

    def test_sm_kappas_write_zero_self_coupling_shifts(self) -> None:
        path = self.write_csv("name,k3,k4,ct2\nsm,1,1,0\n")
        point = load_points(path, "ct2")[0]
        couplings = point.card_couplings(DEFAULT_CT1)
        self.assertEqual(couplings["d3"], Decimal("0"))
        self.assertEqual(couplings["d4"], Decimal("0"))

    def test_default_ct1_is_sm_top_yukawa(self) -> None:
        self.assertEqual(DEFAULT_CT1, Decimal("0"))

    def test_wrong_columns_are_rejected(self) -> None:
        path = self.write_csv("name,k3,k4,ct3\np1,1,1,0\n")
        with self.assertRaises(CampaignError):
            load_points(path, "ct2")


class CardTests(unittest.TestCase):
    def test_all_five_bsm_parameters_are_replaced(self) -> None:
        expected = {
            LHA_CODES["ct1"]: Decimal("0"),
            LHA_CODES["ct2"]: Decimal("2"),
            LHA_CODES["ct3"]: Decimal("0"),
            LHA_CODES["d3"]: Decimal("-1.5"),
            LHA_CODES["d4"]: Decimal("3"),
        }
        updated = replace_slha_parameters(PARAM_CARD, expected)
        self.assertEqual(extract_slha_parameters(updated, list(expected)), expected)
        self.assertIn("BLOCK MASS", updated)

    def test_run_settings_are_replaced(self) -> None:
        updates = {
            "nevents": "25",
            "iseed": "123",
            "ebeam1": "7.000000E+03",
            "ebeam2": "7.000000E+03",
            "pdlabel": "lhapdf",
            "lhaid": "260000",
            "dynamical_scale_choice": "3",
            "scalefact": "0.5",
            "use_syst": "False",
        }
        updated = replace_run_settings(RUN_CARD, updates)
        self.assertEqual(extract_run_settings(updated, list(updates)), updates)

    def test_integration_result_reads_cross_section_and_error(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        process = Path(temporary.name) / "process"
        banner = process / "Events" / "run" / "run_banner.txt"
        banner.parent.mkdir(parents=True)
        banner.write_text("banner\n", encoding="utf-8")
        results = process / "SubProcesses" / "results.dat"
        results.parent.mkdir(parents=True)
        results.write_text("0.42100D-04 0.12500D-07 0 0\n", encoding="utf-8")
        self.assertEqual(integration_result(banner), ("0.42100E-04", "0.12500E-07"))

    def test_pdf_labels_are_set_for_global_and_both_beams(self) -> None:
        updated = set_pdf_labels(RUN_CARD, "lhapdf")
        self.assertEqual(
            extract_run_settings(
                updated, ["pdlabel", "pdlabel1", "pdlabel2", "lhaid"]
            ),
            {
                "pdlabel": "lhapdf",
                "pdlabel1": "lhapdf",
                "pdlabel2": "lhapdf",
                "lhaid": "230000",
            },
        )
        self.assertEqual(updated.count("= pdlabel1"), 1)
        self.assertEqual(updated.count("= pdlabel2"), 1)

        repeated = set_pdf_labels(updated, "lhapdf")
        self.assertEqual(repeated.count("= pdlabel1"), 1)
        self.assertEqual(repeated.count("= pdlabel2"), 1)

    def test_hidden_run_setting_is_added_or_replaced(self) -> None:
        updated = set_optional_run_setting(
            RUN_CARD, "survey_splitting", "3", comment="parallel survey"
        )
        self.assertEqual(
            extract_run_settings(updated, ["survey_splitting"]),
            {"survey_splitting": "3"},
        )
        self.assertEqual(updated.count("= survey_splitting"), 1)

        repeated = set_optional_run_setting(updated, "survey_splitting", "2")
        self.assertEqual(
            extract_run_settings(repeated, ["survey_splitting"]),
            {"survey_splitting": "2"},
        )
        self.assertEqual(repeated.count("= survey_splitting"), 1)

    def test_missing_parameter_is_rejected(self) -> None:
        with self.assertRaises(CampaignError):
            replace_slha_parameters(PARAM_CARD, {999: Decimal("1")})

    def test_one_core_is_explicitly_constrained(self) -> None:
        command = generate_events_command(Path("/process/bin/generate_events"), "p1", 1)
        self.assertEqual(command[:2], [sys.executable, "-O"])
        self.assertIn("scripts/mg5_generate_events.py", command[2])
        self.assertEqual(command[3:6], ["--process-dir", "/process", "--"])
        self.assertIn("--multicore", command)
        self.assertIn("--nb_core=1", command)

    def test_lhapdf_include_repair_changes_only_global_label(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "run_card.inc"
        path.write_text(
            "      PDLABEL = 'nn23lo1'\n"
            "      PDSUBLABEL(1) = 'lhapdf'\n"
            "      LHAID = 331900\n",
            encoding="utf-8",
        )
        repair_lhapdf_include(path)
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "      PDLABEL = 'lhapdf'\n"
            "      PDSUBLABEL(1) = 'lhapdf'\n"
            "      LHAID = 331900\n",
        )


class ProductionGridTests(unittest.TestCase):
    def test_ct2_grid_is_four_by_four(self) -> None:
        points = load_points(REPOSITORY_ROOT / "scans/ct2.13tev.csv", "ct2")
        self.assertEqual(len(points), 16)
        self.assertEqual(
            {(point.k3, point.k4) for point in points},
            {
                (Decimal("-8"), Decimal("50")),
                (Decimal("6"), Decimal("50")),
                (Decimal("-5"), Decimal("-50")),
                (Decimal("3"), Decimal("-50")),
            },
        )
        self.assertEqual(
            {point.active_contact for point in points},
            {Decimal("-0.3"), Decimal("0.6"), Decimal("-4"), Decimal("4")},
        )

    def test_ct3_grid_is_four_by_two(self) -> None:
        points = load_points(REPOSITORY_ROOT / "scans/ct3.13tev.csv", "ct3")
        self.assertEqual(len(points), 8)
        self.assertEqual(
            {(point.k3, point.k4) for point in points},
            {
                (Decimal("-8"), Decimal("50")),
                (Decimal("6"), Decimal("50")),
                (Decimal("-5"), Decimal("-50")),
                (Decimal("3"), Decimal("-50")),
            },
        )
        self.assertEqual(
            {point.active_contact for point in points},
            {Decimal("-5"), Decimal("5")},
        )

    def test_ct3_sm_shape_grid_uses_physical_sm_kappas(self) -> None:
        expected_contacts = {
            Decimal("-0.05"),
            Decimal("-0.025"),
            Decimal("0"),
            Decimal("0.025"),
            Decimal("0.05"),
            Decimal("0.075"),
            Decimal("0.10"),
            Decimal("0.125"),
            Decimal("0.15"),
            Decimal("0.18"),
            Decimal("0.20"),
            Decimal("0.25"),
        }
        for filename in (
            "ct3.13tev-sm-shapes.csv",
            "ct3.14tev-sm-shapes.csv",
        ):
            with self.subTest(filename=filename):
                points = load_points(REPOSITORY_ROOT / "scans" / filename, "ct3")
                self.assertEqual(len(points), 12)
                self.assertEqual(
                    {(point.k3, point.k4) for point in points},
                    {(Decimal("1"), Decimal("1"))},
                )
                self.assertEqual(
                    {point.active_contact for point in points}, expected_contacts
                )
                for point in points:
                    couplings = point.card_couplings(DEFAULT_CT1)
                    self.assertEqual(couplings["d3"], Decimal("0"))
                    self.assertEqual(couplings["d4"], Decimal("0"))
                    self.assertEqual(couplings["ct1"], Decimal("0"))
                    self.assertEqual(couplings["ct2"], Decimal("0"))


if __name__ == "__main__":
    unittest.main()
