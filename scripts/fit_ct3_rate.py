#!/usr/bin/env python3
"""Fit the exact (kappa3, kappa4, kappa3t) gg -> hhh rate polynomial."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


ENERGIES = {
    "13": {"beam_gev": 6500.0, "sm_ab": 42.1},
    "13.6": {"beam_gev": 6800.0, "sm_ab": 47.9},
    "14": {"beam_gev": 7000.0, "sm_ab": 51.0},
}

# Eq. (9) basis evaluated at kappa_t=1 and kappa_2t=0.  These rounded
# coefficients are used only for the independent reproduction diagnostic.
DRAFT_COEFFICIENTS = {
    "13": {
        "c00": 1.007795,
        "c10": -0.869,
        "c20": 0.878,
        "c30": -0.258,
        "c40": 0.0396,
        "c01": -0.0916,
        "c11": -0.1662,
        "c21": 0.0489,
        "c02": 0.0169,
    },
    "13.6": {
        "c00": 1.00186,
        "c10": -0.846,
        "c20": 0.863,
        "c30": -0.253,
        "c40": 0.0388,
        "c01": -0.0920,
        "c11": -0.1639,
        "c21": 0.0480,
        "c02": 0.0167,
    },
    "14": {
        "c00": 0.98912,
        "c10": -0.856,
        "c20": 0.874,
        "c30": -0.255,
        "c40": 0.0391,
        "c01": -0.0933,
        "c11": -0.1652,
        "c21": 0.0484,
        "c02": 0.0169,
    },
}

BASIS_NAMES = (
    "c00",
    "c10",
    "c20",
    "c30",
    "c40",
    "c01",
    "c11",
    "c21",
    "c02",
    "d00",
    "d10",
    "d20",
    "d01",
    "e00",
)

LATEX_MONOMIALS = (
    "",
    "x",
    "x^2",
    "x^3",
    "x^4",
    "y",
    "xy",
    "x^2y",
    "y^2",
    "z",
    "xz",
    "x^2z",
    "yz",
    "z^2",
)


class FitError(RuntimeError):
    pass


@dataclass(frozen=True)
class RatePoint:
    energy: str
    run_name: str
    k3: float
    k4: float
    k3t: float
    cross_section_pb: float
    error_pb: float
    requested_events: int
    source: Path

    @property
    def key(self) -> tuple[float, float, float]:
        return (self.k3, self.k4, self.k3t)


@dataclass(frozen=True)
class FitResult:
    energy: str
    points: tuple[RatePoint, ...]
    absolute_coefficients: np.ndarray
    absolute_covariance: np.ndarray
    normalized_coefficients: np.ndarray
    normalized_covariance: np.ndarray
    chi2: float
    degrees_of_freedom: int
    rank: int
    condition_number: float

    def predict(self, point: RatePoint) -> tuple[float, float]:
        row = basis_vector(point.k3, point.k4, point.k3t)
        value = float(row @ self.absolute_coefficients)
        variance = float(row @ self.absolute_covariance @ row)
        return value, math.sqrt(max(0.0, variance))


def canonical_energy(value: str) -> str:
    normalized = value.strip().lower().replace("tev", "")
    aliases = {"13.0": "13", "13p6": "13.6", "14.0": "14"}
    normalized = aliases.get(normalized, normalized)
    if normalized not in ENERGIES:
        raise FitError(f"unsupported energy {value!r}; expected 13, 13.6, or 14")
    return normalized


def parse_manifest_spec(value: str) -> tuple[str, Path]:
    try:
        energy, raw_path = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("manifest must be ENERGY=PATH") from exc
    try:
        return canonical_energy(energy), Path(raw_path).expanduser().resolve()
    except FitError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def basis_vector(k3: float, k4: float, k3t: float) -> np.ndarray:
    x = k3 - 1.0
    y = k4 - 1.0
    z = k3t
    return np.asarray(
        (
            1.0,
            x,
            x**2,
            x**3,
            x**4,
            y,
            x * y,
            x**2 * y,
            y**2,
            z,
            x * z,
            x**2 * z,
            y * z,
            z**2,
        ),
        dtype=float,
    )


def draft_ratio(energy: str, k3: float, k4: float) -> float:
    row = basis_vector(k3, k4, 0.0)[:9]
    coefficients = np.asarray(
        [DRAFT_COEFFICIENTS[energy][name] for name in BASIS_NAMES[:9]], dtype=float
    )
    raw = float(row @ coefficients)
    return raw / DRAFT_COEFFICIENTS[energy]["c00"]


def _as_float(record: dict[str, object], name: str) -> float:
    value = record.get(name)
    if value is None:
        raise FitError(f"manifest record {record.get('run_name')} has no {name}")
    try:
        result = float(str(value))
    except ValueError as exc:
        raise FitError(f"invalid {name} in {record.get('run_name')}: {value}") from exc
    if not math.isfinite(result):
        raise FitError(f"non-finite {name} in {record.get('run_name')}")
    return result


def validate_record_configuration(record: dict[str, object], energy: str) -> None:
    run_name = str(record.get("run_name", "<unknown>"))
    expected_beam = ENERGIES[energy]["beam_gev"]
    if not math.isclose(_as_float(record, "beam_energy_gev"), expected_beam):
        raise FitError(f"{run_name}: wrong beam energy for {energy} TeV")
    if str(record.get("lhaid")) != "93100":
        raise FitError(f"{run_name}: expected PDF4LHC21_40 member 0 (LHAID 93100)")
    if str(record.get("dynamical_scale_choice")) != "4":
        raise FitError(f"{run_name}: expected dynamical_scale_choice=4")
    if not math.isclose(_as_float(record, "scalefact"), 0.5):
        raise FitError(f"{run_name}: expected scalefact=0.5")
    couplings = record.get("couplings")
    kappas = record.get("kappas")
    if not isinstance(couplings, dict) or not isinstance(kappas, dict):
        raise FitError(f"{run_name}: missing coupling dictionaries")
    k3 = float(str(kappas["k3"]))
    k4 = float(str(kappas["k4"]))
    expected = {
        "ct1": 0.0,
        "ct2": 0.0,
        "d3": k3 - 1.0,
        "d4": k4 - 1.0,
    }
    for name, value in expected.items():
        if not math.isclose(float(str(couplings[name])), value, abs_tol=1e-12):
            raise FitError(f"{run_name}: inconsistent {name}")


def read_manifest(path: Path, energy: str) -> list[RatePoint]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FitError(f"cannot read {path}: {exc}") from exc
    points: list[RatePoint] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FitError(f"{path}:{line_number}: invalid JSON") from exc
        validate_record_configuration(record, energy)
        couplings = record["couplings"]
        kappas = record["kappas"]
        cross_section = _as_float(record, "cross_section_pb")
        error = _as_float(record, "cross_section_error_pb")
        if cross_section <= 0 or error <= 0:
            raise FitError(f"{record.get('run_name')}: rate and error must be positive")
        points.append(
            RatePoint(
                energy=energy,
                run_name=str(record["run_name"]),
                k3=float(str(kappas["k3"])),
                k4=float(str(kappas["k4"])),
                k3t=float(str(couplings["ct3"])),
                cross_section_pb=cross_section,
                error_pb=error,
                requested_events=int(record["requested_events"]),
                source=path,
            )
        )
    if not points:
        raise FitError(f"manifest contains no records: {path}")
    return points


def combine_replicates(points: Iterable[RatePoint]) -> list[RatePoint]:
    grouped: dict[tuple[str, tuple[float, float, float]], list[RatePoint]] = {}
    for point in points:
        grouped.setdefault((point.energy, point.key), []).append(point)
    combined: list[RatePoint] = []
    for (_, _), replicates in grouped.items():
        if len(replicates) == 1:
            combined.append(replicates[0])
            continue
        weights = np.asarray([1.0 / point.error_pb**2 for point in replicates])
        values = np.asarray([point.cross_section_pb for point in replicates])
        reference = replicates[-1]
        combined.append(
            RatePoint(
                energy=reference.energy,
                run_name="+".join(point.run_name for point in replicates),
                k3=reference.k3,
                k4=reference.k4,
                k3t=reference.k3t,
                cross_section_pb=float(np.average(values, weights=weights)),
                error_pb=float(math.sqrt(1.0 / weights.sum())),
                requested_events=sum(point.requested_events for point in replicates),
                source=reference.source,
            )
        )
    return sorted(combined, key=lambda point: (point.k4, point.k3, point.k3t))


def fit_points(energy: str, points: Sequence[RatePoint]) -> FitResult:
    if len(points) < len(BASIS_NAMES):
        raise FitError(
            f"{energy} TeV has {len(points)} unique points; at least {len(BASIS_NAMES)} are required"
        )
    design = np.vstack([basis_vector(point.k3, point.k4, point.k3t) for point in points])
    values = np.asarray([point.cross_section_pb for point in points])
    errors = np.asarray([point.error_pb for point in points])
    weighted_design = design / errors[:, None]
    weighted_values = values / errors
    column_scale = np.linalg.norm(weighted_design, axis=0)
    if np.any(column_scale == 0):
        raise FitError(f"{energy} TeV design has an empty polynomial column")
    scaled_design = weighted_design / column_scale
    scaled_coefficients, _, rank, singular_values = np.linalg.lstsq(
        scaled_design, weighted_values, rcond=None
    )
    if rank != len(BASIS_NAMES):
        raise FitError(f"{energy} TeV design rank is {rank}, expected {len(BASIS_NAMES)}")
    coefficients = scaled_coefficients / column_scale
    scaled_covariance = np.linalg.inv(scaled_design.T @ scaled_design)
    unscale = np.diag(1.0 / column_scale)
    covariance = unscale @ scaled_covariance @ unscale
    residuals = (values - design @ coefficients) / errors
    chi2 = float(residuals @ residuals)
    dof = len(points) - len(BASIS_NAMES)
    a0 = coefficients[0]
    if a0 <= 0:
        raise FitError(f"{energy} TeV fitted SM cross section is non-positive")
    normalized = coefficients / a0
    normalized[0] = 1.0
    jacobian = np.zeros((len(BASIS_NAMES), len(BASIS_NAMES)))
    for index in range(1, len(BASIS_NAMES)):
        jacobian[index, index] = 1.0 / a0
        jacobian[index, 0] = -coefficients[index] / a0**2
    normalized_covariance = jacobian @ covariance @ jacobian.T
    return FitResult(
        energy=energy,
        points=tuple(points),
        absolute_coefficients=coefficients,
        absolute_covariance=covariance,
        normalized_coefficients=normalized,
        normalized_covariance=normalized_covariance,
        chi2=chi2,
        degrees_of_freedom=dof,
        rank=int(rank),
        condition_number=float(singular_values[0] / singular_values[-1]),
    )


def validation_rows(
    result: FitResult, points: Sequence[RatePoint]
) -> list[dict[str, float | str | int]]:
    rows: list[dict[str, float | str | int]] = []
    for point in points:
        prediction, prediction_error = result.predict(point)
        difference = point.cross_section_pb - prediction
        combined_error = math.hypot(point.error_pb, prediction_error)
        rows.append(
            {
                "energy_tev": result.energy,
                "run_name": point.run_name,
                "k3": point.k3,
                "k4": point.k4,
                "k3t": point.k3t,
                "cross_section_pb": point.cross_section_pb,
                "cross_section_error_pb": point.error_pb,
                "prediction_pb": prediction,
                "prediction_error_pb": prediction_error,
                "relative_residual": difference / point.cross_section_pb,
                "pull": difference / combined_error,
                "requested_events": point.requested_events,
            }
        )
    return rows


def write_matrix(path: Path, matrix: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["coefficient", *BASIS_NAMES])
        for name, row in zip(BASIS_NAMES, matrix):
            writer.writerow([name, *(f"{value:.12e}" for value in row)])


def write_candidate_csv(path: Path, energy: str, points: Sequence[RatePoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_energy = energy.replace(".", "p")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["name", "k3", "k4", "ct3"])
        for index, point in enumerate(points, start=1):
            writer.writerow(
                [
                    f"ratefit{safe_energy}_highstat_{index:03d}",
                    f"{point.k3:g}",
                    f"{point.k4:g}",
                    f"{point.k3t:g}",
                ]
            )


def write_outputs(
    output: Path,
    results: dict[str, FitResult],
    validations: dict[str, list[RatePoint]],
    *,
    candidate_dir: Path | None,
    candidate_error_threshold: float,
) -> tuple[float, float]:
    output.mkdir(parents=True, exist_ok=True)
    coefficient_rows: list[dict[str, object]] = []
    payload: dict[str, object] = {"basis": list(BASIS_NAMES), "energies": {}}
    latex_lines = [
        r"% x=\Delta\kappa_3, y=\Delta\kappa_4, z=\kappa_{3t}",
        r"\begin{align}",
    ]
    all_validation_rows: list[dict[str, object]] = []
    all_fit_rows: list[dict[str, object]] = []
    eq9_rows: list[dict[str, object]] = []
    max_relative_residual = 0.0
    max_pull = 0.0

    for energy, result in results.items():
        normalized_errors = np.sqrt(np.maximum(0.0, np.diag(result.normalized_covariance)))
        absolute_errors = np.sqrt(np.maximum(0.0, np.diag(result.absolute_covariance)))
        coefficient_payload = {
            name: {
                "value": float(result.normalized_coefficients[index]),
                "error": float(normalized_errors[index]),
            }
            for index, name in enumerate(BASIS_NAMES)
        }
        payload["energies"][energy] = {
            "sigma_sm_pb": float(result.absolute_coefficients[0]),
            "sigma_sm_error_pb": float(absolute_errors[0]),
            "chi2": result.chi2,
            "degrees_of_freedom": result.degrees_of_freedom,
            "rank": result.rank,
            "condition_number": result.condition_number,
            "coefficients": coefficient_payload,
        }
        for index, name in enumerate(BASIS_NAMES):
            coefficient_rows.append(
                {
                    "energy_tev": energy,
                    "coefficient": name,
                    "value": result.normalized_coefficients[index],
                    "error": normalized_errors[index],
                }
            )
        equation_terms = []
        for index, monomial in enumerate(LATEX_MONOMIALS):
            value = result.normalized_coefficients[index]
            if index == 0:
                equation_terms.append(f"{value:.8g}")
            else:
                equation_terms.append(f"{value:+.8g}{monomial}")
        latex_lines.append(
            rf"\frac{{\sigma_{{{energy}\,\mathrm{{TeV}}}}}}{{\sigma^{{\rm SM}}_{{{energy}\,\mathrm{{TeV}}}}}} &= "
            + " ".join(equation_terms)
            + r" \\"
        )
        write_matrix(output / f"covariance-{energy.replace('.', 'p')}tev.csv", result.normalized_covariance)
        diagonal = np.sqrt(np.maximum(0.0, np.diag(result.normalized_covariance)))
        denominator = np.outer(diagonal, diagonal)
        correlation = np.divide(
            result.normalized_covariance,
            denominator,
            out=np.zeros_like(result.normalized_covariance),
            where=denominator > 0,
        )
        write_matrix(output / f"correlation-{energy.replace('.', 'p')}tev.csv", correlation)

        rows = validation_rows(result, validations.get(energy, []))
        all_validation_rows.extend(rows)
        if rows:
            max_relative_residual = max(
                max_relative_residual,
                max(abs(float(row["relative_residual"])) for row in rows),
            )
            max_pull = max(max_pull, max(abs(float(row["pull"])) for row in rows))

        for point in result.points:
            prediction, prediction_error = result.predict(point)
            difference = point.cross_section_pb - prediction
            all_fit_rows.append(
                {
                    "energy_tev": energy,
                    "run_name": point.run_name,
                    "k3": point.k3,
                    "k4": point.k4,
                    "k3t": point.k3t,
                    "cross_section_pb": point.cross_section_pb,
                    "cross_section_error_pb": point.error_pb,
                    "prediction_pb": prediction,
                    "prediction_error_pb": prediction_error,
                    "relative_residual": difference / point.cross_section_pb,
                    "pull": difference / point.error_pb,
                    "requested_events": point.requested_events,
                }
            )
            if point.k3t == 0.0:
                actual_ratio = point.cross_section_pb / result.absolute_coefficients[0]
                expected_ratio = draft_ratio(energy, point.k3, point.k4)
                eq9_rows.append(
                    {
                        "energy_tev": energy,
                        "run_name": point.run_name,
                        "k3": point.k3,
                        "k4": point.k4,
                        "fit_ratio": actual_ratio,
                        "draft_eq9_ratio": expected_ratio,
                        "relative_difference": actual_ratio / expected_ratio - 1.0,
                    }
                )

        if candidate_dir is not None:
            fit_candidates = [
                point
                for point in result.points
                if point.error_pb / point.cross_section_pb > candidate_error_threshold
            ]
            validation_candidates = [
                point
                for point in validations.get(energy, [])
                if point.error_pb / point.cross_section_pb > candidate_error_threshold
            ]
            prediction_uncertainties = []
            for point in (*result.points, *validations.get(energy, [])):
                prediction, prediction_error = result.predict(point)
                prediction_uncertainties.append(prediction_error / prediction)
            if prediction_uncertainties and max(prediction_uncertainties) > 0.005:
                fit_candidates.extend(
                    sorted(
                        result.points,
                        key=lambda point: point.error_pb / point.cross_section_pb,
                        reverse=True,
                    )[: len(BASIS_NAMES)]
                )
            write_candidate_csv(
                candidate_dir
                / f"ct3.rate-fit-{energy.replace('.', 'p')}tev-fit-highstat.csv",
                energy,
                combine_replicates(fit_candidates),
            )
            write_candidate_csv(
                candidate_dir
                / f"ct3.rate-fit-{energy.replace('.', 'p')}tev-validation-highstat.csv",
                energy,
                combine_replicates(validation_candidates),
            )

    with (output / "coefficients.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coefficient_rows[0]))
        writer.writeheader()
        writer.writerows(coefficient_rows)
    (output / "coefficients.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    latex_lines.append(r"\end{align}")
    (output / "equations.tex").write_text("\n".join(latex_lines) + "\n", encoding="utf-8")

    fit_fields = [
        "energy_tev",
        "run_name",
        "k3",
        "k4",
        "k3t",
        "cross_section_pb",
        "cross_section_error_pb",
        "prediction_pb",
        "prediction_error_pb",
        "relative_residual",
        "pull",
        "requested_events",
    ]
    with (output / "fit-points.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fit_fields)
        writer.writeheader()
        writer.writerows(all_fit_rows)

    eq9_fields = [
        "energy_tev",
        "run_name",
        "k3",
        "k4",
        "fit_ratio",
        "draft_eq9_ratio",
        "relative_difference",
    ]
    with (output / "eq9-comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=eq9_fields)
        writer.writeheader()
        writer.writerows(eq9_rows)

    validation_fields = [
        "energy_tev",
        "run_name",
        "k3",
        "k4",
        "k3t",
        "cross_section_pb",
        "cross_section_error_pb",
        "prediction_pb",
        "prediction_error_pb",
        "relative_residual",
        "pull",
        "requested_events",
    ]
    with (output / "validation.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=validation_fields)
        writer.writeheader()
        writer.writerows(all_validation_rows)

    make_diagnostic_plot(output, results, validations)
    return max_relative_residual, max_pull


def make_diagnostic_plot(
    output: Path, results: dict[str, FitResult], validations: dict[str, list[RatePoint]]
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(len(results), 2, figsize=(10.5, 3.2 * len(results)))
    if len(results) == 1:
        axes = np.asarray([axes])
    for row_index, (energy, result) in enumerate(results.items()):
        fit_predictions = np.asarray([result.predict(point)[0] for point in result.points])
        fit_values = np.asarray([point.cross_section_pb for point in result.points])
        fit_errors = np.asarray([point.error_pb for point in result.points])
        axes[row_index, 0].errorbar(
            fit_predictions, fit_values, yerr=fit_errors, fmt="o", ms=3, label="fit points"
        )
        validation = validations.get(energy, [])
        if validation:
            validation_predictions = np.asarray([result.predict(point)[0] for point in validation])
            validation_values = np.asarray([point.cross_section_pb for point in validation])
            validation_errors = np.asarray([point.error_pb for point in validation])
            axes[row_index, 0].errorbar(
                validation_predictions,
                validation_values,
                yerr=validation_errors,
                fmt="s",
                ms=4,
                label="validation",
            )
        limits = axes[row_index, 0].get_xlim()
        axes[row_index, 0].plot(limits, limits, color="black", linewidth=1)
        axes[row_index, 0].set(xlabel="fit prediction [pb]", ylabel="MadGraph [pb]")
        axes[row_index, 0].set_title(f"{energy} TeV")
        axes[row_index, 0].legend(frameon=False)

        residuals = (fit_values - fit_predictions) / fit_values * 100.0
        axes[row_index, 1].axhline(0.0, color="black", linewidth=1)
        axes[row_index, 1].plot(np.arange(len(residuals)), residuals, "o", ms=3)
        if validation:
            validation_residuals = (
                (validation_values - validation_predictions) / validation_values * 100.0
            )
            start = len(residuals)
            axes[row_index, 1].plot(
                start + np.arange(len(validation_residuals)),
                validation_residuals,
                "s",
                ms=4,
            )
        axes[row_index, 1].set(xlabel="point index", ylabel="relative residual [%]")
    figure.tight_layout()
    figure.savefig(output / "fit-diagnostics.pdf")
    figure.savefig(output / "fit-diagnostics.png", dpi=180)
    plt.close(figure)


def grouped_points(specs: Sequence[tuple[str, Path]]) -> dict[str, list[RatePoint]]:
    grouped: dict[str, list[RatePoint]] = {energy: [] for energy in ENERGIES}
    for energy, path in specs:
        grouped[energy].extend(read_manifest(path, energy))
    return {energy: combine_replicates(points) for energy, points in grouped.items() if points}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-manifest", action="append", type=parse_manifest_spec, required=True)
    parser.add_argument("--validation-manifest", action="append", type=parse_manifest_spec, default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path)
    parser.add_argument("--candidate-error-threshold", type=float, default=0.0025)
    parser.add_argument("--max-validation-residual", type=float, default=0.01)
    parser.add_argument("--max-validation-pull", type=float, default=3.0)
    parser.add_argument("--skip-acceptance", action="store_true")
    args = parser.parse_args()
    if args.candidate_error_threshold <= 0:
        parser.error("--candidate-error-threshold must be positive")
    return args


def main() -> int:
    args = parse_args()
    fit_by_energy = grouped_points(args.fit_manifest)
    validation_by_energy = grouped_points(args.validation_manifest)
    missing = sorted(set(ENERGIES) - set(fit_by_energy))
    if missing:
        raise FitError("missing fit manifests for energies: " + ", ".join(missing))
    results = {
        energy: fit_points(energy, fit_by_energy[energy]) for energy in ENERGIES
    }
    output = args.output.expanduser().resolve()
    candidate_dir = (
        args.candidate_dir.expanduser().resolve() if args.candidate_dir else None
    )
    max_residual, max_pull = write_outputs(
        output,
        results,
        validation_by_energy,
        candidate_dir=candidate_dir,
        candidate_error_threshold=args.candidate_error_threshold,
    )
    for energy, result in results.items():
        print(
            f"{energy} TeV: {len(result.points)} points, rank={result.rank}, "
            f"chi2/dof={result.chi2:.2f}/{result.degrees_of_freedom}, "
            f"sigma_SM={result.absolute_coefficients[0]:.8e} pb"
        )
    if not args.skip_acceptance:
        for energy in ENERGIES:
            if len(validation_by_energy.get(energy, [])) != 6:
                raise FitError(f"{energy} TeV requires exactly six validation points")
        if max_residual > args.max_validation_residual:
            raise FitError(
                f"maximum validation residual {max_residual:.3%} exceeds "
                f"{args.max_validation_residual:.3%}"
            )
        if max_pull > args.max_validation_pull:
            raise FitError(
                f"maximum validation pull {max_pull:.2f} exceeds {args.max_validation_pull:.2f}"
            )
    print(f"Wrote fit artifacts to {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FitError as error:
        raise SystemExit(f"error: {error}") from error
