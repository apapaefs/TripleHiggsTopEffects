from __future__ import annotations

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.run_scan import (
    CampaignError,
    LHA_CODES,
    extract_run_settings,
    extract_slha_parameters,
    load_points,
    replace_run_settings,
    replace_slha_parameters,
)


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
        path = self.write_csv("name,c3,d4,ct2\np1,2,-1,0.5\n")
        point = load_points(path, "ct2")[0]
        self.assertEqual(point.run_name, "ct2_p1")
        self.assertEqual(
            point.couplings(Decimal("1")),
            {
                "ct1": Decimal("1"),
                "ct2": Decimal("0.5"),
                "ct3": Decimal("0"),
                "c3": Decimal("2"),
                "d4": Decimal("-1"),
            },
        )

    def test_ct3_point_sets_inactive_ct2_to_zero(self) -> None:
        path = self.write_csv("# example\nname,c3,d4,ct3\np2,1,1,-0.25\n")
        point = load_points(path, "ct3")[0]
        self.assertEqual(point.couplings(Decimal("1"))["ct2"], Decimal("0"))
        self.assertEqual(point.couplings(Decimal("1"))["ct3"], Decimal("-0.25"))

    def test_wrong_columns_are_rejected(self) -> None:
        path = self.write_csv("name,c3,d4,ct3\np1,1,1,0\n")
        with self.assertRaises(CampaignError):
            load_points(path, "ct2")


class CardTests(unittest.TestCase):
    def test_all_five_bsm_parameters_are_replaced(self) -> None:
        expected = {
            LHA_CODES["ct1"]: Decimal("1"),
            LHA_CODES["ct2"]: Decimal("2"),
            LHA_CODES["ct3"]: Decimal("0"),
            LHA_CODES["c3"]: Decimal("-1.5"),
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
        }
        updated = replace_run_settings(RUN_CARD, updates)
        self.assertEqual(extract_run_settings(updated, list(updates)), updates)

    def test_missing_parameter_is_rejected(self) -> None:
        with self.assertRaises(CampaignError):
            replace_slha_parameters(PARAM_CARD, {999: Decimal("1")})


if __name__ == "__main__":
    unittest.main()
