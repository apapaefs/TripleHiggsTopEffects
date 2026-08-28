from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from scripts.fit_ct3_rate import (
    BASIS_NAMES,
    RatePoint,
    basis_vector,
    combine_replicates,
    draft_ratio,
    fit_points,
)


class PolynomialBasisTests(unittest.TestCase):
    def test_sm_basis_contains_only_the_constant(self) -> None:
        row = basis_vector(1.0, 1.0, 0.0)
        np.testing.assert_array_equal(row, np.asarray([1.0] + [0.0] * 13))

    def test_draft_ratio_is_normalized_at_the_sm(self) -> None:
        for energy in ("13", "13.6", "14"):
            self.assertAlmostEqual(draft_ratio(energy, 1.0, 1.0), 1.0)

    def test_publication_grid_has_full_rank_and_recovers_coefficients(self) -> None:
        normalized = np.asarray(
            [
                1.0,
                -0.8,
                0.9,
                -0.25,
                0.04,
                -0.09,
                -0.16,
                0.05,
                0.017,
                1.3,
                -0.4,
                0.08,
                0.02,
                3.2,
            ]
        )
        sigma_sm = 4.8e-5
        absolute = normalized * sigma_sm
        coordinates = [
            (k3, k4, 0.0)
            for k4 in (-50.0, 1.0, 50.0)
            for k3 in (-8.0, -5.0, 1.0, 3.0, 6.0)
        ]
        for k3, k4 in ((-8.0, 50.0), (6.0, 50.0), (-5.0, -50.0), (3.0, -50.0), (1.0, 1.0)):
            coordinates.extend((k3, k4, k3t) for k3t in (-5.0, -0.5, 0.5, 5.0))
        points = []
        for index, (k3, k4, k3t) in enumerate(coordinates):
            value = float(basis_vector(k3, k4, k3t) @ absolute)
            points.append(
                RatePoint(
                    energy="13.6",
                    run_name=f"synthetic_{index}",
                    k3=k3,
                    k4=k4,
                    k3t=k3t,
                    cross_section_pb=value,
                    error_pb=max(value * 1e-4, 1e-12),
                    requested_events=20000,
                    source=Path("synthetic.jsonl"),
                )
            )
        result = fit_points("13.6", points)
        self.assertEqual(result.rank, len(BASIS_NAMES))
        np.testing.assert_allclose(result.normalized_coefficients, normalized, rtol=1e-9, atol=1e-9)

    def test_replicates_are_inverse_variance_combined(self) -> None:
        common = dict(
            energy="14",
            k3=1.0,
            k4=1.0,
            k3t=0.0,
            requested_events=20000,
            source=Path("manifest.jsonl"),
        )
        combined = combine_replicates(
            [
                RatePoint(run_name="a", cross_section_pb=4.0, error_pb=1.0, **common),
                RatePoint(run_name="b", cross_section_pb=5.0, error_pb=0.5, **common),
            ]
        )[0]
        self.assertAlmostEqual(combined.cross_section_pb, 4.8)
        self.assertAlmostEqual(combined.error_pb, 1.0 / np.sqrt(5.0))
        self.assertEqual(combined.requested_events, 40000)

    def test_tracked_campaign_grids_have_expected_sizes(self) -> None:
        root = Path(__file__).resolve().parents[1] / "scans"
        expected = {
            "ct3.rate-fit-smoke.csv": 1,
            "ct3.rate-fit-baseline.csv": 15,
            "ct3.rate-fit-contact.csv": 20,
            "ct3.rate-fit-validation.csv": 6,
        }
        for filename, count in expected.items():
            rows = [
                line
                for line in (root / filename).read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#") and not line.startswith("name,")
            ]
            self.assertEqual(len(rows), count)


if __name__ == "__main__":
    unittest.main()
