#!/usr/bin/env python3
"""Plot rate-only constraints in the kappa3--kappa3t and kappa4--kappa3t planes."""

from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIT = REPOSITORY_ROOT / "artifacts/fits/ct3-rate/coefficients.json"
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "artifacts/figures"

# Fixed-coupling projections of the tree-level hh -> hh perturbative-unitarity
# region used in the draft.  The first applies at kappa4=1 and the second at
# kappa3=1.  No kappa3t unitarity condition is imposed in these plots.
K3_UNITARITY_BOUND = 6.4623
K4_UNITARITY_BOUND = 64.8933


class ConstraintPlotError(RuntimeError):
    """A user-actionable fit or plotting error."""


@dataclass(frozen=True)
class LimitEllipse:
    """Axis-aligned bounds of the kappa4--kappa3t rate-limit ellipse."""

    center_k4: float
    center_k3t: float
    minimum_ratio: float
    k4_min: float
    k4_max: float
    k3t_min: float
    k3t_max: float


def load_coefficients(path: Path) -> dict[str, dict[str, float]]:
    """Load the central fit coefficients, keyed by collider energy."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConstraintPlotError(f"cannot read fit coefficients from {path}: {exc}") from exc

    energies = payload.get("energies")
    if not isinstance(energies, dict):
        raise ConstraintPlotError(f"{path}: missing energies object")
    result: dict[str, dict[str, float]] = {}
    for energy, record in energies.items():
        if not isinstance(record, dict) or not isinstance(record.get("coefficients"), dict):
            raise ConstraintPlotError(f"{path}: malformed fit record for {energy} TeV")
        result[str(energy)] = {
            name: float(value["value"])
            for name, value in record["coefficients"].items()
        }
    for required_energy in ("13", "14"):
        if required_energy not in result:
            raise ConstraintPlotError(f"{path}: missing {required_energy} TeV fit")
    return result


def cross_section_ratio(
    coefficients: Mapping[str, float], k3, k4, k3t
):
    """Evaluate sigma/sigma_SM for x=kappa3-1, y=kappa4-1, z=kappa3t."""
    x = k3 - 1.0
    y = k4 - 1.0
    z = k3t
    return (
        coefficients["c00"]
        + coefficients["c10"] * x
        + coefficients["c20"] * x**2
        + coefficients["c30"] * x**3
        + coefficients["c40"] * x**4
        + coefficients["c01"] * y
        + coefficients["c11"] * x * y
        + coefficients["c21"] * x**2 * y
        + coefficients["c02"] * y**2
        + coefficients["d00"] * z
        + coefficients["d10"] * x * z
        + coefficients["d20"] * x**2 * z
        + coefficients["d01"] * y * z
        + coefficients["e00"] * z**2
    )


def single_parameter_k3t_interval(
    coefficients: Mapping[str, float], signal_strength_limit: float
) -> tuple[float, float]:
    """Solve R(kappa3=1,kappa4=1,kappa3t)=limit for the two roots."""
    import math

    linear = coefficients["d00"]
    quadratic = coefficients["e00"]
    constant = coefficients["c00"] - signal_strength_limit
    discriminant = linear * linear - 4.0 * quadratic * constant
    if quadratic <= 0.0 or discriminant < 0.0:
        raise ConstraintPlotError("the fitted kappa3t parabola has no bounded interval")
    roots = (
        (-linear - math.sqrt(discriminant)) / (2.0 * quadratic),
        (-linear + math.sqrt(discriminant)) / (2.0 * quadratic),
    )
    return tuple(sorted(roots))


def rate_degenerate_k3t(coefficients: Mapping[str, float]) -> float:
    """Return the nonzero kappa3t solution with the SM inclusive rate."""
    return -coefficients["d00"] / coefficients["e00"]


def k4_k3t_limit_ellipse(
    coefficients: Mapping[str, float], signal_strength_limit: float
) -> LimitEllipse:
    """Return the exact bounds of R(kappa3=1)=signal_strength_limit."""
    a = coefficients["c02"]
    b = coefficients["d01"]
    c = coefficients["e00"]
    p = coefficients["c01"]
    q = coefficients["d00"]
    determinant = 4.0 * a * c - b * b
    if a <= 0.0 or c <= 0.0 or determinant <= 0.0:
        raise ConstraintPlotError("the kappa4--kappa3t contour is not an ellipse")

    center_y = (b * q - 2.0 * c * p) / determinant
    center_k3t = (b * p - 2.0 * a * q) / determinant
    minimum_ratio = (
        coefficients["c00"]
        + p * center_y
        + q * center_k3t
        + a * center_y**2
        + b * center_y * center_k3t
        + c * center_k3t**2
    )
    delta = signal_strength_limit - minimum_ratio
    if delta <= 0.0:
        raise ConstraintPlotError("the requested rate limit does not enclose the minimum")

    quadratic_determinant = a * c - 0.25 * b * b
    k4_extent = math.sqrt(delta * c / quadratic_determinant)
    k3t_extent = math.sqrt(delta * a / quadratic_determinant)
    center_k4 = center_y + 1.0
    return LimitEllipse(
        center_k4=center_k4,
        center_k3t=center_k3t,
        minimum_ratio=minimum_ratio,
        k4_min=center_k4 - k4_extent,
        k4_max=center_k4 + k4_extent,
        k3t_min=center_k3t - k3t_extent,
        k3t_max=center_k3t + k3t_extent,
    )


def padded_symmetric_range(
    lower: float,
    upper: float,
    *,
    padding_fraction: float = 0.08,
    quantum: float = 0.5,
) -> tuple[float, float]:
    """Build a symmetric plotting range with rounded outward padding."""
    if not lower < upper or padding_fraction < 0.0 or quantum <= 0.0:
        raise ValueError("invalid axis-range parameters")
    magnitude = max(abs(lower), abs(upper)) * (1.0 + padding_fraction)
    rounded = math.ceil(magnitude / quantum) * quantum
    return -rounded, rounded


def plot_plane(
    *,
    coefficients_by_energy: Mapping[str, Mapping[str, float]],
    horizontal_coupling: str,
    output: Path,
) -> tuple[Path, Path]:
    cache = Path(tempfile.gettempdir()) / f"triple-higgs-mpl-{os.getuid()}"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    if horizontal_coupling == "k3":
        horizontal_ranges = ((-25.0, 25.0), (-15.0, 15.0))
        unitarity_bound = K3_UNITARITY_BOUND
        horizontal_label = r"$\kappa_3$"
    elif horizontal_coupling == "k4":
        horizontal_ranges = ((-400.0, 400.0), (-200.0, 200.0))
        unitarity_bound = K4_UNITARITY_BOUND
        horizontal_label = r"$\kappa_4$"
    else:
        raise ConstraintPlotError(f"unsupported plane: {horizontal_coupling}")

    panels = (
        ("13", "LHC Run 2", 588.0),
        ("14", "HL-LHC", 125.0),
    )
    k3_vertical_ranges = {"13": (-8.0, 8.0), "14": (-4.0, 4.0)}
    red = "#c9252d"
    yellow = "#f3d44e"
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 11,
            "mathtext.fontset": "cm",
            "axes.linewidth": 1.0,
        }
    )
    figure, axes = plt.subplots(1, 2, figsize=(8.2, 3.7))
    for axis, panel, horizontal_range in zip(axes, panels, horizontal_ranges):
        energy, title, signal_strength_limit = panel
        if horizontal_coupling == "k4":
            ellipse = k4_k3t_limit_ellipse(
                coefficients_by_energy[energy], signal_strength_limit
            )
            vertical_range = padded_symmetric_range(
                ellipse.k3t_min, ellipse.k3t_max
            )
        else:
            vertical_range = k3_vertical_ranges[energy]
        horizontal = np.linspace(*horizontal_range, 901)
        k3t = np.linspace(*vertical_range, 901)
        horizontal_grid, k3t_grid = np.meshgrid(horizontal, k3t)
        if horizontal_coupling == "k3":
            ratio = cross_section_ratio(
                coefficients_by_energy[energy], horizontal_grid, 1.0, k3t_grid
            )
            sm_horizontal = 1.0
        else:
            ratio = cross_section_ratio(
                coefficients_by_energy[energy], 1.0, horizontal_grid, k3t_grid
            )
            sm_horizontal = 1.0

        allowed = np.logical_and(ratio >= 0.0, ratio <= signal_strength_limit)
        axis.contourf(
            horizontal_grid,
            k3t_grid,
            allowed.astype(float),
            levels=(0.5, 1.5),
            colors=(red,),
            alpha=0.28,
            zorder=1,
        )
        axis.axvspan(
            -unitarity_bound,
            unitarity_bound,
            facecolor=yellow,
            alpha=0.58,
            zorder=2,
        )
        axis.axvline(-unitarity_bound, color="black", linestyle=":", linewidth=1.2, zorder=3)
        axis.axvline(unitarity_bound, color="black", linestyle=":", linewidth=1.2, zorder=3)
        axis.contour(
            horizontal_grid,
            k3t_grid,
            ratio,
            levels=(signal_strength_limit,),
            colors=(red,),
            linewidths=1.8,
            zorder=4,
        )
        axis.plot(sm_horizontal, 0.0, "o", color="black", markersize=4.5, zorder=5)
        axis.set_title(title, fontsize=14)
        axis.set_xlim(*horizontal_range)
        axis.set_ylim(*vertical_range)
        axis.set_xlabel(horizontal_label)
        axis.set_ylabel(r"$\kappa_{3t}$")
        axis.tick_params(which="both", direction="in", top=True, right=True)
        axis.minorticks_on()
        axis.text(
            0.04,
            0.95,
            rf"$\mu_{{3h}}<{signal_strength_limit:g}$",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=10,
        )
        handles = (
            Patch(facecolor=red, edgecolor=red, alpha=0.28, label="triple-Higgs"),
            Patch(facecolor=yellow, edgecolor="black", linestyle=":", alpha=0.58, label="unitarity"),
            Line2D([], [], marker="o", linestyle="none", color="black", markersize=4.5, label="SM"),
        )
        axis.legend(handles=handles, frameon=False, loc="lower right", fontsize=9)

    figure.subplots_adjust(left=0.095, right=0.985, bottom=0.17, top=0.88, wspace=0.25)
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = output.with_suffix(".pdf")
    png = output.with_suffix(".png")
    figure.savefig(pdf, bbox_inches="tight", pad_inches=0.04)
    figure.savefig(png, dpi=240, bbox_inches="tight", pad_inches=0.04)
    plt.close(figure)
    return pdf, png


def write_summary(
    path: Path,
    fit_path: Path,
    coefficients_by_energy: Mapping[str, Mapping[str, float]],
) -> None:
    limits = {"13": 588.0, "14": 125.0}
    ellipses = {
        energy: k4_k3t_limit_ellipse(coefficients_by_energy[energy], limits[energy])
        for energy in limits
    }
    payload = {
        "fit": str(fit_path.resolve()),
        "convention": {
            "x": "kappa3 - 1",
            "y": "kappa4 - 1",
            "z": "kappa3t",
            "sm": {"kappa3": 1.0, "kappa4": 1.0, "kappa3t": 0.0},
        },
        "unitarity_projection": {
            "abs_kappa3_at_kappa4_1": K3_UNITARITY_BOUND,
            "abs_kappa4_at_kappa3_1": K4_UNITARITY_BOUND,
            "kappa3t_bound_imposed": False,
        },
        "single_parameter_kappa3t": {
            energy: {
                "signal_strength_limit": limits[energy],
                "allowed_interval": list(
                    single_parameter_k3t_interval(coefficients_by_energy[energy], limits[energy])
                ),
                "nonzero_sm_rate_solution": rate_degenerate_k3t(
                    coefficients_by_energy[energy]
                ),
            }
            for energy in limits
        },
        "kappa4_kappa3t_limit_ellipse": {
            energy: {
                "signal_strength_limit": limits[energy],
                "center": [ellipse.center_k4, ellipse.center_k3t],
                "minimum_ratio": ellipse.minimum_ratio,
                "kappa4_bounds": [ellipse.k4_min, ellipse.k4_max],
                "kappa3t_bounds": [ellipse.k3t_min, ellipse.k3t_max],
                "plot_kappa3t_range": list(
                    padded_symmetric_range(ellipse.k3t_min, ellipse.k3t_max)
                ),
            }
            for energy, ellipse in ellipses.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", type=Path, default=DEFAULT_FIT)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fit = args.fit.expanduser().resolve()
    output_directory = args.output_directory.expanduser().resolve()
    coefficients = load_coefficients(fit)
    outputs = []
    for coupling in ("k3", "k4"):
        outputs.extend(
            plot_plane(
                coefficients_by_energy=coefficients,
                horizontal_coupling=coupling,
                output=output_directory / f"ct3-{coupling}-k3t-constraints",
            )
        )
    summary = output_directory / "ct3-constraint-summary.json"
    write_summary(summary, fit, coefficients)
    outputs.append(summary)
    for output in outputs:
        print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConstraintPlotError as exc:
        raise SystemExit(f"error: {exc}") from exc
