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
        by_ct3[ct3] = ManifestSample(
            run_name=run_name,
            ct3=ct3,
            k3=k3,
            k4=k4,
            cross_section_pb=cross_section_pb,
            generated_events=generated_events,
            lhe=lhe.resolve(),
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
        if len(higgs) != 3:
            raise PlotError(
                f"{path}: event {event_number} has {len(higgs)} final-state Higgs "
                "bosons; expected exactly 3"
            )
        px = sum(momentum[0] for momentum in higgs)
        py = sum(momentum[1] for momentum in higgs)
        pz = sum(momentum[2] for momentum in higgs)
        energy = sum(momentum[3] for momentum in higgs)
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


def sample_label(ct3: Decimal, k3: Decimal, k4: Decimal) -> str:
    """Label a curve without repeating self-couplings fixed to their SM values."""
    if ct3 == SM_ZERO and k3 == SM_ONE and k4 == SM_ONE:
        return "SM"
    entries: list[str] = []
    if k3 != SM_ONE:
        entries.append(rf"\kappa_3={k3}")
    if k4 != SM_ONE:
        entries.append(rf"\kappa_4={k4}")
    entries.append(rf"\kappa_{{3t}}={ct3}")
    return "$" + r",\quad ".join(entries) + "$"


def write_summary(
    path: Path,
    samples: Sequence[ManifestSample],
    shapes: Sequence[EventShapes],
) -> None:
    sm_cross_section = samples[0].cross_section_pb
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "ct3",
                "k3",
                "k4",
                "run_name",
                "events",
                "cross_section_pb",
                "cross_section_over_sm",
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
                    str(sample.lhe),
                ]
            )


def plot_shapes(
    samples: Sequence[ManifestSample],
    shapes: Sequence[EventShapes],
    output: Path,
    collider_label: str,
) -> tuple[Path, Path, Path, Path, Path]:
    cache = Path(tempfile.gettempdir()) / f"triple-higgs-mpl-{os.getuid()}"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    output.parent.mkdir(parents=True, exist_ok=True)
    m3h_edges = np.arange(400.0, 1200.0 + 40.0, 40.0)
    sum_pt_edges = np.arange(0.0, 1200.0 + 40.0, 40.0)
    styles = (
        {"color": "black", "linestyle": "-", "linewidth": 1.6},
        {"color": "#d62728", "linestyle": "--", "linewidth": 1.6},
        {"color": "#1756d1", "linestyle": ":", "linewidth": 1.8},
        {"color": "#2ca02c", "linestyle": "-.", "linewidth": 1.5},
    )

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "mathtext.fontset": "cm",
            "axes.linewidth": 0.9,
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

    def render(*, absolute: bool, destination: Path) -> tuple[Path, Path]:
        figure, axes = plt.subplots(1, 2, figsize=(8.2, 3.65))
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
            axis.legend(frameon=False, fontsize=9, loc="lower left")
        axes[0].set_xlim(400, 1200)
        axes[0].set_xlabel(r"$m_{3h}\;[\mathrm{GeV}]$")
        axes[1].set_xlim(0, 1200)
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
            axes[0].set_ylim(8e-4, 3e-1)
            axes[0].set_ylabel(
                r"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}m_{3h}"
                r"\;[1/(40\,\mathrm{GeV})]$"
            )
            axes[1].set_ylim(3e-5, 3e-1)
            axes[1].set_ylabel(
                r"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}\sum p_{T,h}"
                r"\;[1/(40\,\mathrm{GeV})]$"
            )

        # Leave enough room for the centered 1200 tick label on the right.
        figure.subplots_adjust(
            left=0.105, right=0.965, bottom=0.17, top=0.89, wspace=0.30
        )
        pdf = destination.with_suffix(".pdf")
        png = destination.with_suffix(".png")
        figure.savefig(pdf, bbox_inches="tight", pad_inches=0.04)
        figure.savefig(png, dpi=240, bbox_inches="tight", pad_inches=0.04)
        plt.close(figure)
        return pdf, png

    normalized_pdf, normalized_png = render(absolute=False, destination=output)
    unnormalized_output = output.with_name(f"{output.name}-unnormalized")
    unnormalized_pdf, unnormalized_png = render(
        absolute=True, destination=unnormalized_output
    )
    summary = output.with_suffix(".csv")
    write_summary(summary, samples, shapes)
    return (
        normalized_pdf,
        normalized_png,
        unnormalized_pdf,
        unnormalized_png,
        summary,
    )


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
    outputs = plot_shapes(samples, shapes, output, args.collider_label)
    for path in outputs:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlotError as exc:
        raise SystemExit(f"error: {exc}") from exc
