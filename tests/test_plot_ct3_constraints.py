from __future__ import annotations

import unittest

from scripts.fit_ct3_rate import BASIS_NAMES, basis_vector
from scripts.plot_ct3_constraints import (
    cross_section_ratio,
    k4_k3t_limit_ellipse,
    padded_symmetric_range,
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

    def test_plot_polynomial_matches_fit_basis(self) -> None:
        coefficients = [COEFFICIENTS[name] for name in BASIS_NAMES]
        for k3, k4, k3t in ((1.0, 1.0, 0.0), (2.1, 17.0, -0.2), (1.9, 0.0, 0.4)):
            expected = float(basis_vector(k3, k4, k3t) @ coefficients)
            self.assertAlmostEqual(
                cross_section_ratio(COEFFICIENTS, k3, k4, k3t), expected
            )

    def test_k4_k3t_ellipse_bounds_end_on_limit(self) -> None:
        limit = 125.0
        ellipse = k4_k3t_limit_ellipse(COEFFICIENTS, limit)
        for k3t in (ellipse.k3t_min, ellipse.k3t_max):
            y_at_fixed_k3t_minimum = -(
                COEFFICIENTS["c01"] + COEFFICIENTS["d01"] * k3t
            ) / (2.0 * COEFFICIENTS["c02"])
            self.assertAlmostEqual(
                cross_section_ratio(
                    COEFFICIENTS, 1.0, y_at_fixed_k3t_minimum + 1.0, k3t
                ),
                limit,
                places=10,
            )
        for k4 in (ellipse.k4_min, ellipse.k4_max):
            y = k4 - 1.0
            k3t_at_fixed_k4_minimum = -(
                COEFFICIENTS["d00"] + COEFFICIENTS["d01"] * y
            ) / (2.0 * COEFFICIENTS["e00"])
            self.assertAlmostEqual(
                cross_section_ratio(
                    COEFFICIENTS, 1.0, k4, k3t_at_fixed_k4_minimum
                ),
                limit,
                places=10,
            )

    def test_padded_range_contains_complete_ellipse(self) -> None:
        ellipse = k4_k3t_limit_ellipse(COEFFICIENTS, 125.0)
        lower, upper = padded_symmetric_range(ellipse.k3t_min, ellipse.k3t_max)
        self.assertLess(lower, ellipse.k3t_min)
        self.assertGreater(upper, ellipse.k3t_max)


if __name__ == "__main__":
    unittest.main()
