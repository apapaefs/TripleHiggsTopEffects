#!/usr/bin/env python3
"""Validate the PDF4LHC21 SM and kappa3/kappa4 reproduction gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.fit_ct3_rate import (
    ENERGIES,
    FitError,
    draft_ratio,
    grouped_points,
    parse_manifest_spec,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", action="append", type=parse_manifest_spec, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-sm-deviation", type=float, default=0.02)
    parser.add_argument("--max-baseline-deviation", type=float, default=0.05)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    grouped = grouped_points(args.manifest)
    summary: dict[str, object] = {"energies": {}}
    for energy in ENERGIES:
        points = grouped.get(energy, [])
        if len(points) != 15:
            raise FitError(f"{energy} TeV baseline gate requires 15 unique points")
        sm_matches = [point for point in points if point.key == (1.0, 1.0, 0.0)]
        if len(sm_matches) != 1:
            raise FitError(f"{energy} TeV baseline gate requires one SM point")
        sm = sm_matches[0]
        draft_sm_pb = ENERGIES[energy]["sm_ab"] * 1e-6
        sm_deviation = abs(sm.cross_section_pb / draft_sm_pb - 1.0)
        if sm_deviation > args.max_sm_deviation:
            raise FitError(
                f"{energy} TeV SM deviation {sm_deviation:.3%} exceeds "
                f"{args.max_sm_deviation:.3%}"
            )
        rows = []
        maximum = 0.0
        for point in points:
            actual_ratio = point.cross_section_pb / sm.cross_section_pb
            expected_ratio = draft_ratio(energy, point.k3, point.k4)
            relative = abs(actual_ratio / expected_ratio - 1.0)
            maximum = max(maximum, relative)
            rows.append(
                {
                    "run_name": point.run_name,
                    "k3": point.k3,
                    "k4": point.k4,
                    "actual_ratio": actual_ratio,
                    "draft_ratio": expected_ratio,
                    "relative_deviation": relative,
                }
            )
        if maximum > args.max_baseline_deviation:
            raise FitError(
                f"{energy} TeV baseline deviation {maximum:.3%} exceeds "
                f"{args.max_baseline_deviation:.3%}"
            )
        summary["energies"][energy] = {
            "sm_cross_section_pb": sm.cross_section_pb,
            "draft_sm_cross_section_pb": draft_sm_pb,
            "sm_relative_deviation": sm_deviation,
            "maximum_baseline_relative_deviation": maximum,
            "points": rows,
        }
        print(
            f"{energy} TeV gate passed: SM deviation={sm_deviation:.3%}, "
            f"max baseline deviation={maximum:.3%}"
        )
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FitError as error:
        raise SystemExit(f"error: {error}") from error
