from __future__ import annotations

import unittest

from scripts.plot_ct3_constraints import (
    cross_section_ratio,
    rate_degenerate_k3t,
    single_parameter_k3t_interval,
)


COEFFICIENTS = {
    "c00": 1.0,
    "c10": -0.85,
    "c20": 0.86,
    "c30": -0.26,
    "c40": 0.039,
    "c01": -0.092,
    "c11": -0.166,
    "c21": 0.048,
    "c02": 0.017,
    "d00": -3.0,
    "d10": -3.9,
    "d20": 0.90,
    "d01": 0.80,
    "e00": 15.0,
}


class ConstraintPlotTests(unittest.TestCase):
    def test_sm_point_has_unit_ratio(self) -> None:
        self.assertEqual(cross_section_ratio(COEFFICIENTS, 1.0, 1.0, 0.0), 1.0)

    def test_offsets_are_kappas_minus_one(self) -> None:
        expected = 1.0 + COEFFICIENTS["c10"] + COEFFICIENTS["c20"]
        expected += COEFFICIENTS["c30"] + COEFFICIENTS["c40"]
        self.assertAlmostEqual(
            cross_section_ratio(COEFFICIENTS, 2.0, 1.0, 0.0), expected
        )

    def test_nonzero_solution_is_rate_degenerate_with_sm(self) -> None:
        solution = rate_degenerate_k3t(COEFFICIENTS)
        self.assertNotEqual(solution, 0.0)
        self.assertAlmostEqual(
            cross_section_ratio(COEFFICIENTS, 1.0, 1.0, solution), 1.0
        )

    def test_single_parameter_interval_ends_at_limit(self) -> None:
        lower, upper = single_parameter_k3t_interval(COEFFICIENTS, 125.0)
        self.assertLess(lower, 0.0)
        self.assertGreater(upper, 0.0)
        self.assertAlmostEqual(
            cross_section_ratio(COEFFICIENTS, 1.0, 1.0, lower), 125.0
        )
        self.assertAlmostEqual(
            cross_section_ratio(COEFFICIENTS, 1.0, 1.0, upper), 125.0
        )


if __name__ == "__main__":
    unittest.main()
