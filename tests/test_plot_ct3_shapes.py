from __future__ import annotations

import gzip
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from scripts.plot_ct3_shapes import (
    EventShapes,
    ManifestSample,
    PlotError,
    adaptive_upper_edge,
    absolute_bin_cross_sections,
    fixed_bin_edges,
    normalized_bin_weights,
    pairwise_total_variation_records,
    parse_sample_selection,
    read_event_shapes,
    sample_label,
    total_variation_distance,
    validate_sample_settings,
    weighted_quantile,
    write_summary,
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
    @staticmethod
    def sample(**overrides) -> ManifestSample:
        values = {
            "run_name": "sample",
            "ct3": Decimal("0"),
            "k3": Decimal("1"),
            "k4": Decimal("1"),
            "cross_section_pb": Decimal("0.00005"),
            "generated_events": 100,
            "lhe": Path("events.lhe.gz"),
            "pdlabel": "lhapdf",
            "lhaid": 93100,
            "dynamical_scale_choice": 4,
            "scalefact": Decimal("0.5"),
            "beam_energy_gev": Decimal("7000"),
        }
        values.update(overrides)
        return ManifestSample(**values)

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

    def test_weighted_quantile_uses_event_weights(self) -> None:
        self.assertEqual(
            weighted_quantile([10.0, 20.0, 30.0], [1.0, 8.0, 1.0], 0.5),
            20.0,
        )

    def test_adaptive_upper_edge_is_rounded_and_bin_aligned(self) -> None:
        upper = adaptive_upper_edge(
            [([410.0, 985.0], [1.0, 1.0])],
            lower_edge=360.0,
            quantile=1.0,
            rounding_step=200.0,
        )
        self.assertEqual(upper, 1000.0)
        self.assertEqual((upper - 360.0) % 40.0, 0.0)

    def test_fixed_ranges_match_figure_7_binning(self) -> None:
        m3h_edges = fixed_bin_edges((400.0, 1200.0))
        sum_pt_edges = fixed_bin_edges((0.0, 1200.0))
        self.assertEqual(len(m3h_edges) - 1, 20)
        self.assertEqual(len(sum_pt_edges) - 1, 30)
        self.assertTrue(
            all(right - left == 40.0 for left, right in zip(m3h_edges, m3h_edges[1:]))
        )

    def test_fixed_range_must_align_with_bin_width(self) -> None:
        with self.assertRaises(PlotError):
            fixed_bin_edges((400.0, 1210.0))

    def test_total_variation_distance_detects_shape_changes(self) -> None:
        self.assertEqual(total_variation_distance([1.0, 1.0], [2.0, 2.0]), 0.0)
        self.assertAlmostEqual(
            total_variation_distance([3.0, 1.0], [1.0, 3.0]), 0.5
        )

    def test_pairwise_distances_cover_every_sample_pair(self) -> None:
        samples = [
            self.sample(run_name="sm"),
            self.sample(run_name="hard"),
            self.sample(run_name="soft"),
        ]
        records = pairwise_total_variation_records(
            samples,
            [
                ([1.0, 1.0], [1.0, 1.0]),
                ([0.0, 2.0], [2.0, 0.0]),
                ([2.0, 0.0], [0.0, 2.0]),
            ],
        )
        self.assertEqual(len(records), 3)
        self.assertEqual(
            (records[-1]["run_name_a"], records[-1]["run_name_b"]),
            ("hard", "soft"),
        )
        self.assertEqual(records[-1]["observables"]["m3h"], 1.0)
        self.assertEqual(records[-1]["observables"]["sum_pt_h"], 1.0)

    def test_sm_self_couplings_are_omitted_from_curve_labels(self) -> None:
        self.assertEqual(
            sample_label(Decimal("0.18"), Decimal("1"), Decimal("1")),
            r"$\kappa_{3t}=0.18$",
        )
        self.assertEqual(
            sample_label(Decimal("0.18"), Decimal("0.8"), Decimal("1.2")),
            r"$\kappa_3=0.8,\quad \kappa_4=1.2,\quad \kappa_{3t}=0.18$",
        )
        self.assertEqual(
            sample_label(
                Decimal("-2.3"),
                Decimal("2.1"),
                Decimal("23"),
                compact=True,
            ),
            r"$\kappa_3=2.1,\;\kappa_4=23,\;\kappa_{3t}=-2.3$",
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

    def test_common_pdf_and_scale_settings_are_validated(self) -> None:
        samples = [self.sample(run_name="sm"), self.sample(run_name="bsm")]
        validate_sample_settings(
            samples,
            expected_pdlabel="lhapdf",
            expected_lhaid=93100,
            expected_dynamical_scale_choice=4,
            expected_scalefact=Decimal("0.5"),
            expected_beam_energy_gev=Decimal("7000"),
        )

    def test_mixed_generation_settings_are_rejected(self) -> None:
        samples = [
            self.sample(run_name="sm"),
            self.sample(run_name="bsm", lhaid=331900),
        ]
        with self.assertRaises(PlotError):
            validate_sample_settings(samples)

    def test_unexpected_beam_energy_is_rejected(self) -> None:
        with self.assertRaises(PlotError):
            validate_sample_settings(
                [self.sample()], expected_beam_energy_gev=Decimal("6500")
            )

    def test_summary_uses_unix_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.csv"
            write_summary(
                path,
                [self.sample()],
                [EventShapes(m3h=(500.0,), sum_pt_h=(200.0,), weights=(1.0,))],
            )
            contents = path.read_bytes()
        self.assertNotIn(b"\r\n", contents)
        self.assertTrue(contents.endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
