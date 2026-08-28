from __future__ import annotations

import gzip
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.plot_ct3_shapes import (
    absolute_bin_cross_sections,
    normalized_bin_weights,
    parse_sample_selection,
    read_event_shapes,
    sample_label,
)


TOY_LHE = """<LesHouchesEvents version="3.0">
<event>
 5 0 2.0 500.0 0.0 0.0
 21 -1 0 0 501 502 0 0 250 250 0 0 1
 21 -1 0 0 502 501 0 0 -250 250 0 0 1
 25 1 1 2 0 0 100 0 0 160.0781059 125 0 0
 25 1 1 2 0 0 -50 0 0 134.6291202 125 0 0
 25 1 1 2 0 0 -50 0 0 134.6291202 125 0 0
</event>
</LesHouchesEvents>
"""


class LheShapeTests(unittest.TestCase):
    def test_reads_three_higgs_shapes_from_gzip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.lhe.gz"
            with gzip.open(path, "wt", encoding="utf-8") as handle:
                handle.write(TOY_LHE)
            shapes = read_event_shapes(path)
        self.assertEqual(shapes.event_count, 1)
        self.assertEqual(shapes.weights, (2.0,))
        self.assertAlmostEqual(shapes.sum_pt_h[0], 200.0)
        self.assertAlmostEqual(shapes.m3h[0], 429.3363463, places=5)

    def test_histogram_is_normalized_to_all_event_weight(self) -> None:
        result = normalized_bin_weights(
            [10.0, 50.0, 500.0], [1.0, 2.0, 1.0], [0.0, 40.0, 80.0]
        )
        self.assertEqual(result.tolist(), [0.25, 0.5])

    def test_absolute_histogram_is_scaled_by_total_cross_section(self) -> None:
        result = absolute_bin_cross_sections(
            [10.0, 50.0, 500.0],
            [1.0, 2.0, 1.0],
            [0.0, 40.0, 80.0],
            Decimal("0.004"),
        )
        self.assertAlmostEqual(result[0], 0.001)
        self.assertAlmostEqual(result[1], 0.002)

    def test_sm_self_couplings_are_omitted_from_curve_labels(self) -> None:
        self.assertEqual(
            sample_label(Decimal("0.18"), Decimal("1"), Decimal("1")),
            r"$\kappa_{3t}=0.18$",
        )
        self.assertEqual(
            sample_label(Decimal("0.18"), Decimal("0.8"), Decimal("1.2")),
            r"$\kappa_3=0.8,\quad \kappa_4=1.2,\quad \kappa_{3t}=0.18$",
        )

    def test_only_the_all_sm_point_is_labelled_sm(self) -> None:
        self.assertEqual(
            sample_label(Decimal("0"), Decimal("1"), Decimal("1")), "SM"
        )
        self.assertEqual(
            sample_label(Decimal("0"), Decimal("0.8"), Decimal("1")),
            r"$\kappa_3=0.8,\quad \kappa_{3t}=0$",
        )

    def test_mixed_sample_selection_uses_physical_kappas(self) -> None:
        selection = parse_sample_selection(
            ["manifest.jsonl", "1.806", "0", "0.40"]
        )
        self.assertEqual(selection.manifest, Path("manifest.jsonl"))
        self.assertEqual(selection.k3, Decimal("1.806"))
        self.assertEqual(selection.k4, Decimal("0"))
        self.assertEqual(selection.ct3, Decimal("0.40"))


if __name__ == "__main__":
    unittest.main()
