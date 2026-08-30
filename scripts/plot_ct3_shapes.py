#!/usr/bin/env python3
"""Plot normalized and absolute gg -> hhh benchmark shapes."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import tempfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Iterator, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    REPOSITORY_ROOT / "artifacts/lhe/14tev-ct3-sm-shapes/manifest.jsonl"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "artifacts/figures/14tev-ct3-sm-shapes"
SM_ZERO = Decimal("0")
SM_ONE = Decimal("1")
SHAPE_BIN_WIDTH_GEV = 40.0
SHAPE_RANGE_QUANTILE = 0.995
MIN_PLOTTED_WEIGHT_FRACTION = 0.995


class PlotError(RuntimeError):
    """A user-actionable plotting or input-data error."""


@dataclass(frozen=True)
class ManifestSample:
    run_name: str
    ct3: Decimal
    k3: Decimal
    k4: Decimal
    cross_section_pb: Decimal
    generated_events: int
    lhe: Path
    pdlabel: str | None
    lhaid: int | None
    dynamical_scale_choice: int | None
    scalefact: Decimal | None
    beam_energy_gev: Decimal | None


@dataclass(frozen=True)
class SampleSelection:
    manifest: Path
    k3: Decimal
    k4: Decimal
    ct3: Decimal


@dataclass(frozen=True)
class EventShapes:
    m3h: tuple[float, ...]
    sum_pt_h: tuple[float, ...]
    weights: tuple[float, ...]

    @property
    def event_count(self) -> int:
        return len(self.weights)


def parse_decimal(value: object, *, context: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PlotError(f"invalid decimal for {context}: {value!r}") from exc
    if not result.is_finite():
        raise PlotError(f"non-finite decimal for {context}: {value!r}")
    return result


def load_manifest_samples(
    manifest: Path,
    requested_ct3: Sequence[Decimal],
    requested_k3: Decimal = SM_ONE,
    requested_k4: Decimal = SM_ONE,
) -> list[ManifestSample]:
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PlotError(f"cannot read manifest {manifest}: {exc}") from exc

    # Resume operations append records.  The final record for a run is the
    # authoritative one, whether its status is "generated" or "reused".
    latest_by_run: dict[str, dict[str, object]] = {}
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PlotError(
                f"{manifest}:{line_number}: invalid JSON: {exc.msg}"
            ) from exc
        run_name = record.get("run_name")
        if not isinstance(run_name, str) or not run_name:
            raise PlotError(f"{manifest}:{line_number}: missing run_name")
        latest_by_run[run_name] = record

    by_ct3: dict[Decimal, ManifestSample] = {}
    for run_name, record in latest_by_run.items():
        couplings = record.get("couplings")
        kappas = record.get("kappas")
        if not isinstance(couplings, dict) or not isinstance(kappas, dict):
            continue
        required = {
            "ct1": SM_ZERO,
            "ct2": SM_ZERO,
            "d3": requested_k3 - SM_ONE,
            "d4": requested_k4 - SM_ONE,
        }
        try:
            if any(
                parse_decimal(couplings[name], context=f"{run_name}.{name}")
                != expected
                for name, expected in required.items()
            ):
                continue
            k3 = parse_decimal(kappas["k3"], context=f"{run_name}.k3")
            k4 = parse_decimal(kappas["k4"], context=f"{run_name}.k4")
            if k3 != requested_k3 or k4 != requested_k4:
                continue
            ct3 = parse_decimal(couplings["ct3"], context=f"{run_name}.ct3")
        except KeyError:
            continue
        if ct3 not in requested_ct3:
            continue
        if ct3 in by_ct3:
            raise PlotError(
                f"manifest has multiple samples at k3={requested_k3}, "
                f"k4={requested_k4}, CT3={ct3}: "
                f"{by_ct3[ct3].run_name} and {run_name}"
            )
        lhe_value = record.get("lhe")
        if not isinstance(lhe_value, str):
            raise PlotError(f"{run_name}: manifest record has no LHE path")
        lhe = Path(lhe_value).expanduser()
        if not lhe.is_absolute():
            lhe = manifest.parent / lhe
        if not lhe.is_file():
            raise PlotError(f"{run_name}: LHE file does not exist: {lhe}")
        try:
            generated_events = int(record["generated_events"])
            cross_section_pb = parse_decimal(
                record["cross_section_pb"], context=f"{run_name}.cross_section_pb"
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlotError(f"{run_name}: incomplete manifest record") from exc
        if generated_events <= 0 or cross_section_pb <= 0:
            raise PlotError(f"{run_name}: non-positive event count or cross section")

        pdlabel_value = record.get("pdlabel")
        pdlabel = str(pdlabel_value) if pdlabel_value is not None else None
        try:
            lhaid = int(record["lhaid"]) if record.get("lhaid") is not None else None
            dynamical_scale_choice = (
                int(record["dynamical_scale_choice"])
                if record.get("dynamical_scale_choice") is not None
                else None
            )
            scalefact = (
                parse_decimal(record["scalefact"], context=f"{run_name}.scalefact")
                if record.get("scalefact") is not None
                else None
            )
            beam_energy_gev = (
                parse_decimal(
                    record["beam_energy_gev"], context=f"{run_name}.beam_energy_gev"
                )
                if record.get("beam_energy_gev") is not None
                else None
            )
        except (TypeError, ValueError) as exc:
            raise PlotError(f"{run_name}: malformed generation settings") from exc
        by_ct3[ct3] = ManifestSample(
            run_name=run_name,
            ct3=ct3,
            k3=k3,
            k4=k4,
            cross_section_pb=cross_section_pb,
            generated_events=generated_events,
            lhe=lhe.resolve(),
            pdlabel=pdlabel,
            lhaid=lhaid,
            dynamical_scale_choice=dynamical_scale_choice,
            scalefact=scalefact,
            beam_energy_gev=beam_energy_gev,
        )

    missing = [value for value in requested_ct3 if value not in by_ct3]
    if missing:
        raise PlotError(
            f"manifest is missing completed samples at k3={requested_k3}, "
            f"k4={requested_k4} for CT3=" + ", ".join(str(value) for value in missing)
        )
    return [by_ct3[value] for value in requested_ct3]


def _open_lhe(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", errors="replace")
    return path.open(encoding="utf-8", errors="replace")


def iter_lhe_events(path: Path) -> Iterator[tuple[float, list[list[float]]]]:
    """Yield (event weight, Higgs four-vectors) from an LHE or LHE.GZ file."""
    with _open_lhe(path) as handle:
        iterator = iter(handle)
        for line in iterator:
            if line.strip() != "<event>":
                continue
            for header in iterator:
                if header.strip():
                    break
            else:
                raise PlotError(f"{path}: truncated event header")
            fields = header.split()
            if len(fields) < 3:
                raise PlotError(f"{path}: malformed event header {header.strip()!r}")
            try:
                particle_count = int(fields[0])
                weight = float(fields[2].replace("D", "E").replace("d", "e"))
            except ValueError as exc:
                raise PlotError(
                    f"{path}: malformed event header {header.strip()!r}"
                ) from exc

            higgs: list[list[float]] = []
            for _ in range(particle_count):
                try:
                    particle = next(iterator)
                except StopIteration as exc:
                    raise PlotError(f"{path}: truncated particle list") from exc
                columns = particle.split()
                if len(columns) < 11:
                    raise PlotError(
                        f"{path}: malformed particle row {particle.strip()!r}"
                    )
                try:
                    pdg_id = int(columns[0])
                    status = int(columns[1])
                    momentum = [
                        float(value.replace("D", "E").replace("d", "e"))
                        for value in columns[6:10]
                    ]
                except ValueError as exc:
                    raise PlotError(
                        f"{path}: malformed particle row {particle.strip()!r}"
                    ) from exc
                if pdg_id == 25 and status == 1:
                    higgs.append(momentum)
            yield weight, higgs


def read_event_shapes(path: Path) -> EventShapes:
    m3h: list[float] = []
    sum_pt_h: list[float] = []
    weights: list[float] = []
    for event_number, (weight, higgs) in enumerate(iter_lhe_events(path), start=1):
        if not math.isfinite(weight):
            raise PlotError(f"{path}: event {event_number} has a non-finite weight")
        if len(higgs) != 3:
            raise PlotError(
                f"{path}: event {event_number} has {len(higgs)} final-state Higgs "
                "bosons; expected exactly 3"
            )
        px = sum(momentum[0] for momentum in higgs)
        py = sum(momentum[1] for momentum in higgs)
        pz = sum(momentum[2] for momentum in higgs)
        energy = sum(momentum[3] for momentum in higgs)
        if not all(math.isfinite(value) for momentum in higgs for value in momentum):
            raise PlotError(f"{path}: event {event_number} has non-finite momentum")
        mass_squared = energy * energy - px * px - py * py - pz * pz
        if mass_squared < -1e-5:
            raise PlotError(
                f"{path}: event {event_number} has negative m3h^2={mass_squared}"
            )
        m3h.append(math.sqrt(max(0.0, mass_squared)))
        sum_pt_h.append(
            sum(math.hypot(momentum[0], momentum[1]) for momentum in higgs)
        )
        weights.append(weight)
    if not weights:
        raise PlotError(f"{path}: no LHE events found")
    if not math.isfinite(sum(weights)) or sum(weights) <= 0:
        raise PlotError(f"{path}: non-positive or non-finite total event weight")
    return EventShapes(tuple(m3h), tuple(sum_pt_h), tuple(weights))


def normalized_bin_weights(
    values: Iterable[float], weights: Iterable[float], edges
):
    import numpy as np

    value_array = np.asarray(tuple(values), dtype=float)
    weight_array = np.asarray(tuple(weights), dtype=float)
    histogram, _ = np.histogram(value_array, bins=edges, weights=weight_array)
    total_weight = float(weight_array.sum())
    if total_weight <= 0:
        raise PlotError("cannot normalize a sample with non-positive total weight")
    return histogram / total_weight


def absolute_bin_cross_sections(
    values: Iterable[float],
    weights: Iterable[float],
    edges,
    cross_section_pb: Decimal,
):
    """Return the cross section in pb in each plotted bin."""
    return normalized_bin_weights(values, weights, edges) * float(cross_section_pb)


def weighted_quantile(
    values: Iterable[float], weights: Iterable[float], quantile: float
) -> float:
    """Return a quantile using the event weights as a discrete probability mass."""
    import numpy as np

    if not 0.0 <= quantile <= 1.0:
        raise PlotError(f"quantile must lie in [0, 1], got {quantile}")
    value_array = np.asarray(tuple(values), dtype=float)
    weight_array = np.asarray(tuple(weights), dtype=float)
    if value_array.size == 0 or value_array.shape != weight_array.shape:
        raise PlotError("weighted quantile requires equally sized, non-empty inputs")
    if not np.all(np.isfinite(value_array)) or not np.all(np.isfinite(weight_array)):
        raise PlotError("weighted quantile inputs must be finite")
    if np.any(weight_array < 0.0):
        raise PlotError("adaptive plot ranges require non-negative event weights")
    total_weight = float(weight_array.sum())
    if total_weight <= 0.0:
        raise PlotError("weighted quantile requires positive total event weight")

    order = np.argsort(value_array, kind="stable")
    sorted_values = value_array[order]
    cumulative_weight = np.cumsum(weight_array[order])
    target = quantile * total_weight
    index = int(np.searchsorted(cumulative_weight, target, side="left"))
    return float(sorted_values[min(index, sorted_values.size - 1)])


def adaptive_upper_edge(
    value_weight_pairs: Iterable[tuple[Iterable[float], Iterable[float]]],
    *,
    lower_edge: float,
    bin_width: float = SHAPE_BIN_WIDTH_GEV,
    quantile: float = SHAPE_RANGE_QUANTILE,
    rounding_step: float = 200.0,
) -> float:
    """Choose a reproducible upper edge containing the requested weighted tail."""
    if bin_width <= 0.0 or rounding_step <= 0.0:
        raise PlotError("plot bin width and range-rounding step must be positive")
    pairs = list(value_weight_pairs)
    if not pairs:
        raise PlotError("cannot choose a plot range without samples")
    largest_quantile = max(
        weighted_quantile(values, weights, quantile) for values, weights in pairs
    )
    upper_edge = math.ceil(largest_quantile / rounding_step) * rounding_step
    upper_edge = max(upper_edge, lower_edge + bin_width)
    # Keep every edge aligned to the histogram width even if callers change the
    # coarser rounding step in the future.
    bin_count = math.ceil((upper_edge - lower_edge) / bin_width)
    return lower_edge + bin_count * bin_width


def fixed_bin_edges(
    plot_range: Sequence[float], *, bin_width: float = SHAPE_BIN_WIDTH_GEV
) -> tuple[float, ...]:
    """Return fixed, uniformly spaced edges after validating the requested range."""
    if len(plot_range) != 2:
        raise PlotError("a fixed plot range requires exactly two edges")
    lower_edge, upper_edge = map(float, plot_range)
    if not math.isfinite(lower_edge) or not math.isfinite(upper_edge):
        raise PlotError("fixed plot-range edges must be finite")
    if bin_width <= 0.0 or upper_edge <= lower_edge:
        raise PlotError("fixed plot ranges must be increasing and use positive bins")
    bin_count_float = (upper_edge - lower_edge) / bin_width
    bin_count = round(bin_count_float)
    if bin_count < 1 or not math.isclose(
        bin_count_float, bin_count, rel_tol=0.0, abs_tol=1e-10
    ):
        raise PlotError(
            f"fixed plot range [{lower_edge:g}, {upper_edge:g}] is not an "
            f"integer multiple of the {bin_width:g} GeV bin width"
        )
    return tuple(lower_edge + index * bin_width for index in range(bin_count + 1))


def total_variation_distance(
    histogram: Sequence[float], reference: Sequence[float]
) -> float:
    """Compare two plotted shapes after normalising each inside the shown range."""
    import numpy as np

    values = np.asarray(histogram, dtype=float)
    reference_values = np.asarray(reference, dtype=float)
    if values.shape != reference_values.shape or values.size == 0:
        raise PlotError("shape-distance histograms must have equal nonzero sizes")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(reference_values)):
        raise PlotError("shape-distance histograms must be finite")
    if np.any(values < 0.0) or np.any(reference_values < 0.0):
        raise PlotError("shape-distance histograms must be non-negative")
    value_sum = float(values.sum())
    reference_sum = float(reference_values.sum())
    if value_sum <= 0.0 or reference_sum <= 0.0:
        raise PlotError("shape-distance histograms must have positive integrals")
    return float(
        0.5
        * np.abs(values / value_sum - reference_values / reference_sum).sum()
    )


def pairwise_total_variation_records(
    samples: Sequence[ManifestSample],
    normalized_histograms: Sequence[
        tuple[Sequence[float], Sequence[float]]
    ],
) -> list[dict[str, object]]:
    """Report every benchmark-to-benchmark distance in the plotted ranges."""
    if len(samples) != len(normalized_histograms):
        raise PlotError(
            "pairwise shape validation requires one histogram pair per sample"
        )
    records: list[dict[str, object]] = []
    for first_index, first_sample in enumerate(samples):
        for second_index in range(first_index + 1, len(samples)):
            second_sample = samples[second_index]
            records.append(
                {
                    "run_name_a": first_sample.run_name,
                    "run_name_b": second_sample.run_name,
                    "observables": {
                        name: total_variation_distance(
                            normalized_histograms[first_index][observable_index],
                            normalized_histograms[second_index][observable_index],
                        )
                        for observable_index, name in enumerate(
                            ("m3h", "sum_pt_h")
                        )
                    },
                }
            )
    return records


def sample_label(
    ct3: Decimal, k3: Decimal, k4: Decimal, *, compact: bool = False
) -> str:
    """Label a curve without repeating self-couplings fixed to their SM values."""
    if ct3 == SM_ZERO and k3 == SM_ONE and k4 == SM_ONE:
        return "SM"
    entries: list[str] = []
    if k3 != SM_ONE:
        entries.append(rf"\kappa_3={k3}")
    if k4 != SM_ONE:
        entries.append(rf"\kappa_4={k4}")
    entries.append(rf"\kappa_{{3t}}={ct3}")
    separator = r",\;" if compact else r",\quad "
    return "$" + separator.join(entries) + "$"


def validate_sample_settings(
    samples: Sequence[ManifestSample],
    *,
    expected_pdlabel: str | None = None,
    expected_lhaid: int | None = None,
    expected_dynamical_scale_choice: int | None = None,
    expected_scalefact: Decimal | None = None,
    expected_beam_energy_gev: Decimal | None = None,
) -> None:
    """Require a common generation setup and any explicitly requested settings."""
    if not samples:
        raise PlotError("no samples were selected")
    attributes = (
        "pdlabel",
        "lhaid",
        "dynamical_scale_choice",
        "scalefact",
        "beam_energy_gev",
    )
    reference = samples[0]
    for sample in samples[1:]:
        mismatches = [
            attribute
            for attribute in attributes
            if getattr(sample, attribute) != getattr(reference, attribute)
        ]
        if mismatches:
            raise PlotError(
                f"{sample.run_name}: generation settings differ from "
                f"{reference.run_name}: {', '.join(mismatches)}"
            )

    expectations = {
        "pdlabel": expected_pdlabel,
        "lhaid": expected_lhaid,
        "dynamical_scale_choice": expected_dynamical_scale_choice,
        "scalefact": expected_scalefact,
        "beam_energy_gev": expected_beam_energy_gev,
    }
    for attribute, expected in expectations.items():
        if expected is not None and getattr(reference, attribute) != expected:
            raise PlotError(
                f"expected {attribute}={expected}, but manifest records "
                f"{getattr(reference, attribute)}"
            )


def write_summary(
    path: Path,
    samples: Sequence[ManifestSample],
    shapes: Sequence[EventShapes],
) -> None:
    sm_cross_section = samples[0].cross_section_pb
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "ct3",
                "k3",
                "k4",
                "run_name",
                "events",
                "cross_section_pb",
                "cross_section_over_sm",
                "pdlabel",
                "lhaid",
                "dynamical_scale_choice",
                "scalefact",
                "beam_energy_gev",
                "lhe",
            ]
        )
        for sample, event_shapes in zip(samples, shapes):
            writer.writerow(
                [
                    str(sample.ct3),
                    str(sample.k3),
                    str(sample.k4),
                    sample.run_name,
                    event_shapes.event_count,
                    str(sample.cross_section_pb),
                    str(sample.cross_section_pb / sm_cross_section),
                    sample.pdlabel,
                    sample.lhaid,
                    sample.dynamical_scale_choice,
                    str(sample.scalefact) if sample.scalefact is not None else "",
                    (
                        str(sample.beam_energy_gev)
                        if sample.beam_energy_gev is not None
                        else ""
                    ),
                    str(sample.lhe),
                ]
            )


def plot_shapes(
    samples: Sequence[ManifestSample],
    shapes: Sequence[EventShapes],
    output: Path,
    collider_label: str,
    *,
    m3h_range: Sequence[float] | None = None,
    sum_pt_range: Sequence[float] | None = None,
    separate_panels: bool = False,
) -> tuple[Path, ...]:
    if not samples or len(samples) != len(shapes):
        raise PlotError(
            "plotting requires one non-empty event sample per manifest record"
        )
    cache = Path(tempfile.gettempdir()) / f"triple-higgs-mpl-{os.getuid()}"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import font_manager

    # The shared plotting cache can predate a newly installed font package.
    # Register the Times-compatible faces explicitly so publication reruns are
    # reproducible without requiring users to delete their Matplotlib cache.
    for font_path in Path("/usr/share/fonts/truetype/croscore").glob(
        "Tinos-*.ttf"
    ):
        font_manager.fontManager.addfont(str(font_path))

    output.parent.mkdir(parents=True, exist_ok=True)
    if m3h_range is None:
        m3h_lower = 360.0
        m3h_upper = adaptive_upper_edge(
            ((event_shapes.m3h, event_shapes.weights) for event_shapes in shapes),
            lower_edge=m3h_lower,
        )
        m3h_edges = np.arange(
            m3h_lower, m3h_upper + SHAPE_BIN_WIDTH_GEV, SHAPE_BIN_WIDTH_GEV
        )
    else:
        m3h_edges = np.asarray(fixed_bin_edges(m3h_range), dtype=float)
        m3h_lower, m3h_upper = float(m3h_edges[0]), float(m3h_edges[-1])
    if sum_pt_range is None:
        sum_pt_lower = 0.0
        sum_pt_upper = adaptive_upper_edge(
            (
                (event_shapes.sum_pt_h, event_shapes.weights)
                for event_shapes in shapes
            ),
            lower_edge=sum_pt_lower,
        )
        sum_pt_edges = np.arange(
            sum_pt_lower,
            sum_pt_upper + SHAPE_BIN_WIDTH_GEV,
            SHAPE_BIN_WIDTH_GEV,
        )
    else:
        sum_pt_edges = np.asarray(fixed_bin_edges(sum_pt_range), dtype=float)
        sum_pt_lower, sum_pt_upper = (
            float(sum_pt_edges[0]),
            float(sum_pt_edges[-1]),
        )
    styles = (
        {"color": "black", "linestyle": "-", "linewidth": 1.4},
        {"color": "#cc0000", "linestyle": "--", "linewidth": 1.4},
        {"color": "#0000cc", "linestyle": ":", "linewidth": 1.5},
        {"color": "#2ca02c", "linestyle": "-.", "linewidth": 1.5},
    )

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Tinos", "STIXGeneral"],
            "font.size": 10,
            "mathtext.fontset": "stix",
            "axes.linewidth": 0.9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    normalized_histograms = [
        (
            normalized_bin_weights(event_shapes.m3h, event_shapes.weights, m3h_edges),
            normalized_bin_weights(
                event_shapes.sum_pt_h, event_shapes.weights, sum_pt_edges
            ),
        )
        for event_shapes in shapes
    ]
    absolute_histograms = [
        (
            absolute_bin_cross_sections(
                event_shapes.m3h,
                event_shapes.weights,
                m3h_edges,
                sample.cross_section_pb,
            ),
            absolute_bin_cross_sections(
                event_shapes.sum_pt_h,
                event_shapes.weights,
                sum_pt_edges,
                sample.cross_section_pb,
            ),
        )
        for sample, event_shapes in zip(samples, shapes)
    ]
    pairwise_validation_records = pairwise_total_variation_records(
        samples, normalized_histograms
    )

    validation_records = []
    for sample_index, (sample, event_shapes, normalized, absolute) in enumerate(
        zip(samples, shapes, normalized_histograms, absolute_histograms)
    ):
        if event_shapes.event_count != sample.generated_events:
            raise PlotError(
                f"{sample.run_name}: manifest records {sample.generated_events} "
                f"events but the LHE contains {event_shapes.event_count}"
            )
        observables = {}
        for observable_index, (
            name,
            normalized_histogram,
            absolute_histogram,
        ) in enumerate(
            zip(("m3h", "sum_pt_h"), normalized, absolute)
        ):
            if not np.all(np.isfinite(normalized_histogram)) or not np.all(
                np.isfinite(absolute_histogram)
            ):
                raise PlotError(f"{sample.run_name}: non-finite histogram bin")
            if np.any(normalized_histogram < -1e-14) or np.any(
                absolute_histogram < -1e-14
            ):
                raise PlotError(f"{sample.run_name}: negative histogram bin")
            expected_absolute = normalized_histogram * float(sample.cross_section_pb)
            if not np.allclose(
                absolute_histogram, expected_absolute, rtol=1e-12, atol=1e-15
            ):
                raise PlotError(f"{sample.run_name}: absolute histogram closure failed")
            coverage = float(normalized_histogram.sum())
            if coverage < -1e-12 or coverage > 1.0 + 1e-12:
                raise PlotError(f"{sample.run_name}: invalid plotted-weight coverage")
            uses_adaptive_range = (
                m3h_range is None if name == "m3h" else sum_pt_range is None
            )
            if (
                uses_adaptive_range
                and coverage + 1e-12 < MIN_PLOTTED_WEIGHT_FRACTION
            ):
                raise PlotError(
                    f"{sample.run_name}: only {coverage:.3%} of the {name} "
                    f"distribution lies inside the plotted range"
                )
            observables[name] = {
                "normalized_bin_sum": coverage,
                "outside_range_fraction": 1.0 - coverage,
                "absolute_bin_sum_pb": float(absolute_histogram.sum()),
                "maximum_closure_error_pb": float(
                    np.max(np.abs(absolute_histogram - expected_absolute))
                ),
                "shape_total_variation_from_sm_in_plotted_range": (
                    total_variation_distance(
                        normalized_histogram,
                        normalized_histograms[0][observable_index],
                    )
                    if sample_index
                    else 0.0
                ),
            }
        validation_records.append(
            {
                "run_name": sample.run_name,
                "events": event_shapes.event_count,
                "manifest_events": sample.generated_events,
                "total_event_weight": float(sum(event_shapes.weights)),
                "cross_section_pb": float(sample.cross_section_pb),
                "observables": observables,
            }
        )

    def render_combined(*, absolute: bool, destination: Path) -> tuple[Path, Path]:
        figure, axes = plt.subplots(1, 2, figsize=(8.2, 3.9))
        plotted: list[tuple[object, object]] = []
        source_histograms = absolute_histograms if absolute else normalized_histograms
        for index, (sample, histograms) in enumerate(
            zip(samples, source_histograms)
        ):
            m3h_histogram, sum_pt_histogram = histograms
            plotted.append((m3h_histogram, sum_pt_histogram))
            style = styles[index % len(styles)]
            axes[0].stairs(
                m3h_histogram,
                m3h_edges,
                baseline=None,
                label=sample_label(sample.ct3, sample.k3, sample.k4),
                **style,
            )
            axes[1].stairs(
                sum_pt_histogram,
                sum_pt_edges,
                baseline=None,
                label=sample_label(sample.ct3, sample.k3, sample.k4),
                **style,
            )

        for axis in axes:
            axis.set_title(collider_label, fontsize=12)
            axis.set_yscale("log")
            axis.tick_params(which="both", direction="in", top=True, right=True)
            axis.minorticks_on()
        axes[0].set_xlim(m3h_lower, m3h_upper)
        axes[0].set_xlabel(r"$m_{3h}\;[\mathrm{GeV}]$")
        axes[1].set_xlim(sum_pt_lower, sum_pt_upper)
        axes[1].set_xlabel(r"$\sum p_{T,h}\;[\mathrm{GeV}]$")

        if absolute:
            for axis_index, axis in enumerate(axes):
                positive = [
                    float(value)
                    for histograms in plotted
                    for value in histograms[axis_index]
                    if value > 0
                ]
                axis.set_ylim(min(positive) * 0.7, max(positive) * 1.8)
            axes[0].set_ylabel(
                r"$\mathrm{d}\sigma/\mathrm{d}m_{3h}"
                r"\;[\mathrm{pb}/(40\,\mathrm{GeV})]$"
            )
            axes[1].set_ylabel(
                r"$\mathrm{d}\sigma/\mathrm{d}\sum p_{T,h}"
                r"\;[\mathrm{pb}/(40\,\mathrm{GeV})]$"
            )
        else:
            for axis_index, axis in enumerate(axes):
                positive = [
                    float(value)
                    for histograms in plotted
                    for value in histograms[axis_index]
                    if value > 0
                ]
                axis.set_ylim(min(positive) * 0.7, max(positive) * 1.8)
            axes[0].set_ylabel(
                r"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}m_{3h}"
                r"\;[1/(40\,\mathrm{GeV})]$"
            )
            axes[1].set_ylabel(
                r"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}\sum p_{T,h}"
                r"\;[1/(40\,\mathrm{GeV})]$"
            )

        handles, labels = axes[0].get_legend_handles_labels()
        figure.legend(
            handles,
            labels,
            frameon=False,
            fontsize=8.5,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.995),
            ncol=min(3, len(samples)),
            columnspacing=1.5,
            handlelength=3.0,
        )

        # The shared legend sits above the panel titles and cannot obscure a
        # distribution; retain room for centered final ticks on the right.
        figure.subplots_adjust(
            left=0.105, right=0.965, bottom=0.16, top=0.80, wspace=0.30
        )
        pdf = destination.with_suffix(".pdf")
        png = destination.with_suffix(".png")
        figure.savefig(pdf, bbox_inches="tight", pad_inches=0.04)
        figure.savefig(png, dpi=240, bbox_inches="tight", pad_inches=0.04)
        plt.close(figure)
        return pdf, png

    def render_publication_panel(
        *, absolute: bool, observable_index: int, destination: Path
    ) -> tuple[Path, Path]:
        from matplotlib import ticker

        panel_height_inches = 271.0 / 72.0
        figure, axis = plt.subplots(figsize=(4.0, panel_height_inches))
        source_histograms = absolute_histograms if absolute else normalized_histograms
        edges = m3h_edges if observable_index == 0 else sum_pt_edges
        lower = m3h_lower if observable_index == 0 else sum_pt_lower
        upper = m3h_upper if observable_index == 0 else sum_pt_upper
        plotted = []
        for index, (sample, histograms) in enumerate(
            zip(samples, source_histograms)
        ):
            histogram = histograms[observable_index]
            plotted.append(histogram)
            axis.stairs(
                histogram,
                edges,
                baseline=None,
                label=sample_label(
                    sample.ct3, sample.k3, sample.k4, compact=True
                ),
                **styles[index % len(styles)],
            )

        positive = [
            float(value)
            for histogram in plotted
            for value in histogram
            if value > 0
        ]
        axis.set_xlim(lower, upper)
        axis.set_ylim(min(positive) * 0.7, max(positive) * 1.7)
        axis.set_yscale("log")
        axis.set_title(collider_label, fontsize=14, pad=7)
        axis.xaxis.set_major_locator(ticker.MultipleLocator(200.0))
        axis.xaxis.set_minor_locator(ticker.MultipleLocator(50.0))
        major_subs = (1.0, 5.0) if observable_index == 0 else (1.0,)
        axis.yaxis.set_major_locator(
            ticker.LogLocator(base=10.0, subs=major_subs, numticks=20)
        )
        axis.yaxis.set_minor_locator(
            ticker.LogLocator(
                base=10.0,
                subs=(2.0, 3.0, 4.0, 6.0, 7.0, 8.0, 9.0),
                numticks=100,
            )
        )

        def format_log_tick(value: float, _position: float) -> str:
            if value <= 0.0:
                return ""
            exponent = int(round(math.log10(value)))
            if value >= 1.0e-3:
                return f"{value:.3f}"
            if math.isclose(value, 10.0**exponent, rel_tol=1.0e-10):
                return rf"$10^{{{exponent}}}$"
            return ""

        axis.yaxis.set_major_formatter(ticker.FuncFormatter(format_log_tick))
        axis.yaxis.set_minor_formatter(ticker.NullFormatter())
        axis.tick_params(
            which="major",
            direction="in",
            top=True,
            right=True,
            length=4.0,
            width=0.9,
            labelsize=11.5,
        )
        axis.tick_params(
            which="minor",
            direction="in",
            top=True,
            right=True,
            length=2.2,
            width=0.8,
        )
        if observable_index == 0:
            axis.set_xlabel(r"$m_{3h}\;[\mathrm{GeV}]$", fontsize=13.5)
            if absolute:
                axis.set_ylabel(
                    r"$d\sigma/dm_{3h}"
                    r"\;[\mathrm{pb}/(40\,\mathrm{GeV})]$",
                    fontsize=13.5,
                )
            else:
                axis.set_ylabel(
                    r"$1/\sigma\;d\sigma/dm_{3h}"
                    r"\;[1/(40\,\mathrm{GeV})]$",
                    fontsize=13.5,
                )
        else:
            axis.set_xlabel(r"$\sum p_{T,h}\;[\mathrm{GeV}]$", fontsize=13.5)
            if absolute:
                axis.set_ylabel(
                    r"$d\sigma/(d\sum p_{T,h})"
                    r"\;[\mathrm{pb}/(40\,\mathrm{GeV})]$",
                    fontsize=13.5,
                )
            else:
                axis.set_ylabel(
                    r"$1/\sigma\;d\sigma/(d\sum p_{T,h})"
                    r"\;[1/(40\,\mathrm{GeV})]$",
                    fontsize=13.5,
                )
        axis.legend(
            frameon=False,
            fontsize=9.3,
            loc="lower left",
            bbox_to_anchor=(0.055, 0.075),
            borderaxespad=0.0,
            handlelength=2.0,
            handletextpad=0.7,
            labelspacing=1.45,
        )
        figure.subplots_adjust(left=0.20, right=0.92, bottom=0.155, top=0.91)
        pdf = destination.with_suffix(".pdf")
        png = destination.with_suffix(".png")
        figure.savefig(pdf)
        figure.savefig(png, dpi=240)
        plt.close(figure)
        return pdf, png

    if separate_panels:
        normalized_m3h = render_publication_panel(
            absolute=False,
            observable_index=0,
            destination=output.with_name(f"{output.name}-m3h"),
        )
        normalized_sum_pt = render_publication_panel(
            absolute=False,
            observable_index=1,
            destination=output.with_name(f"{output.name}-sum-pth"),
        )
        unnormalized_m3h = render_publication_panel(
            absolute=True,
            observable_index=0,
            destination=output.with_name(f"{output.name}-m3h-unnormalized"),
        )
        unnormalized_sum_pt = render_publication_panel(
            absolute=True,
            observable_index=1,
            destination=output.with_name(f"{output.name}-sum-pth-unnormalized"),
        )
        plot_outputs = (
            *normalized_m3h,
            *normalized_sum_pt,
            *unnormalized_m3h,
            *unnormalized_sum_pt,
        )
    else:
        normalized_pdf, normalized_png = render_combined(
            absolute=False, destination=output
        )
        unnormalized_output = output.with_name(f"{output.name}-unnormalized")
        unnormalized_pdf, unnormalized_png = render_combined(
            absolute=True, destination=unnormalized_output
        )
        plot_outputs = (
            normalized_pdf,
            normalized_png,
            unnormalized_pdf,
            unnormalized_png,
        )
    summary = output.with_suffix(".csv")
    write_summary(summary, samples, shapes)
    validation = output.with_name(f"{output.name}-validation.json")
    validation.write_text(
        json.dumps(
            {
                "checks_passed": True,
                "separate_panels": separate_panels,
                "common_settings": {
                    "pdlabel": samples[0].pdlabel,
                    "lhaid": samples[0].lhaid,
                    "dynamical_scale_choice": samples[0].dynamical_scale_choice,
                    "scalefact": (
                        str(samples[0].scalefact)
                        if samples[0].scalefact is not None
                        else None
                    ),
                    "beam_energy_gev": (
                        str(samples[0].beam_energy_gev)
                        if samples[0].beam_energy_gev is not None
                        else None
                    ),
                },
                "binning_gev": {
                    "m3h": list(map(float, m3h_edges)),
                    "sum_pt_h": list(map(float, sum_pt_edges)),
                },
                "range_policy": {
                    "m3h": (
                        {"mode": "adaptive", "weighted_quantile": SHAPE_RANGE_QUANTILE}
                        if m3h_range is None
                        else {"mode": "fixed", "range_gev": [m3h_lower, m3h_upper]}
                    ),
                    "sum_pt_h": (
                        {"mode": "adaptive", "weighted_quantile": SHAPE_RANGE_QUANTILE}
                        if sum_pt_range is None
                        else {
                            "mode": "fixed",
                            "range_gev": [sum_pt_lower, sum_pt_upper],
                        }
                    ),
                    "adaptive_minimum_plotted_weight_fraction": (
                        MIN_PLOTTED_WEIGHT_FRACTION
                    ),
                    "bin_width_gev": SHAPE_BIN_WIDTH_GEV,
                },
                "samples": validation_records,
                "pairwise_shape_total_variation_in_plotted_range": (
                    pairwise_validation_records
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return (*plot_outputs, summary, validation)


def decimal_argument(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value}") from exc
    if not result.is_finite():
        raise argparse.ArgumentTypeError(f"number must be finite: {value}")
    return result


def parse_sample_selection(values: Sequence[str]) -> SampleSelection:
    """Parse MANIFEST K3 K4 CT3 supplied by one ``--sample`` option."""
    if len(values) != 4:
        raise argparse.ArgumentTypeError(
            "--sample requires MANIFEST K3 K4 CT3"
        )
    manifest, k3, k4, ct3 = values
    return SampleSelection(
        manifest=Path(manifest),
        k3=decimal_argument(k3),
        k4=decimal_argument(k4),
        ct3=decimal_argument(ct3),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--ct3-values",
        type=decimal_argument,
        nargs="+",
        default=[Decimal("0"), Decimal("0.10"), Decimal("0.18")],
        help="ordered CT3/kappa_3t values to draw (default: 0 0.10 0.18)",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--collider-label", default="HL-LHC")
    parser.add_argument(
        "--m3h-range",
        type=float,
        nargs=2,
        metavar=("LOW", "HIGH"),
        help="fixed m3h plotting range in GeV (default: adaptive)",
    )
    parser.add_argument(
        "--sum-pt-range",
        type=float,
        nargs=2,
        metavar=("LOW", "HIGH"),
        help="fixed sum-pT plotting range in GeV (default: adaptive)",
    )
    parser.add_argument(
        "--separate-panels",
        action="store_true",
        help=(
            "write standalone m3h and sum-pT panels with internal legends "
            "in the publication distribution style"
        ),
    )
    parser.add_argument("--expected-pdlabel")
    parser.add_argument("--expected-lhaid", type=int)
    parser.add_argument("--expected-dynamical-scale-choice", type=int)
    parser.add_argument("--expected-scalefact", type=decimal_argument)
    parser.add_argument("--expected-beam-energy-gev", type=decimal_argument)
    parser.add_argument(
        "--k3",
        type=decimal_argument,
        default=SM_ONE,
        help="fixed physical kappa_3 value to select (default: 1)",
    )
    parser.add_argument(
        "--k4",
        type=decimal_argument,
        default=SM_ONE,
        help="fixed physical kappa_4 value to select (default: 1)",
    )
    parser.add_argument(
        "--sample",
        dest="raw_sample_selections",
        action="append",
        nargs=4,
        metavar=("MANIFEST", "K3", "K4", "CT3"),
        help=(
            "select one benchmark from a manifest; repeat to compare mixed "
            "k3/k4 points (the first sample must be the SM)"
        ),
    )
    args = parser.parse_args()
    args.sample_selections = None
    if args.raw_sample_selections:
        try:
            selections = [
                parse_sample_selection(values)
                for values in args.raw_sample_selections
            ]
        except argparse.ArgumentTypeError as exc:
            parser.error(str(exc))
        if len(selections) < 2:
            parser.error("repeat --sample at least twice")
        first = selections[0]
        if (first.k3, first.k4, first.ct3) != (SM_ONE, SM_ONE, SM_ZERO):
            parser.error("the first --sample must have K3=1 K4=1 CT3=0")
        identities = [
            (selection.manifest, selection.k3, selection.k4, selection.ct3)
            for selection in selections
        ]
        if len(set(identities)) != len(identities):
            parser.error("--sample selections must be unique")
        args.sample_selections = selections
    else:
        if len(args.ct3_values) < 2:
            parser.error("--ct3-values requires at least two samples")
        if len(set(args.ct3_values)) != len(args.ct3_values):
            parser.error("--ct3-values must be unique")
        if args.ct3_values[0] != 0:
            parser.error("the first --ct3-values entry must be 0 (the SM reference)")
    return args


def main() -> int:
    args = parse_args()
    output = args.output.expanduser().resolve()
    if args.sample_selections:
        samples = [
            load_manifest_samples(
                selection.manifest.expanduser().resolve(),
                [selection.ct3],
                selection.k3,
                selection.k4,
            )[0]
            for selection in args.sample_selections
        ]
    else:
        manifest = args.manifest.expanduser().resolve()
        samples = load_manifest_samples(
            manifest, args.ct3_values, args.k3, args.k4
        )
    validate_sample_settings(
        samples,
        expected_pdlabel=args.expected_pdlabel,
        expected_lhaid=args.expected_lhaid,
        expected_dynamical_scale_choice=args.expected_dynamical_scale_choice,
        expected_scalefact=args.expected_scalefact,
        expected_beam_energy_gev=args.expected_beam_energy_gev,
    )
    shapes: list[EventShapes] = []
    for sample in samples:
        print(f"Reading {sample.run_name}: {sample.lhe}", flush=True)
        event_shapes = read_event_shapes(sample.lhe)
        if event_shapes.event_count != sample.generated_events:
            raise PlotError(
                f"{sample.run_name}: parsed {event_shapes.event_count} events, but the "
                f"manifest records {sample.generated_events}"
            )
        shapes.append(event_shapes)
    outputs = plot_shapes(
        samples,
        shapes,
        output,
        args.collider_label,
        m3h_range=args.m3h_range,
        sum_pt_range=args.sum_pt_range,
        separate_panels=args.separate_panels,
    )
    for path in outputs:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlotError as exc:
        raise SystemExit(f"error: {exc}") from exc
