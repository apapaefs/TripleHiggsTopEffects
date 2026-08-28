#!/usr/bin/env python3
"""Fail closed unless the corrected 13 TeV campaign and process are exact."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.run_parallel_scan import load_campaign_points
from scripts.run_scan import DEFAULT_CT1, LHA_CODES, CampaignError, extract_slha_parameters


DEFAULT_PROCESS_DIR = REPOSITORY_ROOT / "MG5_aMC_v3_5_16" / "gg_hhh_restricted5"
CT2_FILES = (
    REPOSITORY_ROOT / "scans" / "ct2.13tev.csv",
    REPOSITORY_ROOT / "scans" / "ct2.13tev-additional.csv",
)
CT3_FILES = (
    REPOSITORY_ROOT / "scans" / "ct3.13tev.csv",
    REPOSITORY_ROOT / "scans" / "ct3.13tev-additional.csv",
)
EXPECTED_KAPPAS = {
    (Decimal("-8"), Decimal("50")),
    (Decimal("6"), Decimal("50")),
    (Decimal("-5"), Decimal("-50")),
    (Decimal("3"), Decimal("-50")),
    (Decimal("1"), Decimal("1")),
}
EXPECTED_CT2 = {
    Decimal("-4"),
    Decimal("-0.3"),
    Decimal("-0.1"),
    Decimal("0"),
    Decimal("0.1"),
    Decimal("0.6"),
    Decimal("4"),
}
EXPECTED_CT3 = {
    Decimal("-5"),
    Decimal("-0.5"),
    Decimal("0.5"),
    Decimal("5"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_grid() -> tuple[list[object], dict[str, object]]:
    points = load_campaign_points(list(CT2_FILES), list(CT3_FILES))
    if len(points) != 55:
        raise CampaignError(f"corrected campaign must contain 55 points, found {len(points)}")

    by_scan_and_kappa: dict[tuple[str, Decimal, Decimal], set[Decimal]] = defaultdict(set)
    for point in points:
        by_scan_and_kappa[(point.scan, point.k3, point.k4)].add(point.active_contact)
        couplings = point.card_couplings(DEFAULT_CT1)
        expected = {
            "ct1": Decimal("0"),
            "ct2": point.active_contact if point.scan == "ct2" else Decimal("0"),
            "ct3": point.active_contact if point.scan == "ct3" else Decimal("0"),
            "d3": point.k3 - Decimal("1"),
            "d4": point.k4 - Decimal("1"),
        }
        if couplings != expected:
            raise CampaignError(
                f"incorrect card mapping for {point.run_name}: {couplings} != {expected}"
            )

    actual_kappas = {(point.k3, point.k4) for point in points}
    if actual_kappas != EXPECTED_KAPPAS:
        raise CampaignError(f"incorrect kappa benchmarks: {sorted(actual_kappas)}")
    for k3, k4 in EXPECTED_KAPPAS:
        actual_ct2 = by_scan_and_kappa[("ct2", k3, k4)]
        actual_ct3 = by_scan_and_kappa[("ct3", k3, k4)]
        if actual_ct2 != EXPECTED_CT2:
            raise CampaignError(
                f"incorrect ct2 values for kappa=({k3},{k4}): {sorted(actual_ct2)}"
            )
        if actual_ct3 != EXPECTED_CT3:
            raise CampaignError(
                f"incorrect ct3 values for kappa=({k3},{k4}): {sorted(actual_ct3)}"
            )

    return points, {
        "point_count": len(points),
        "kappa_benchmark_count": len(EXPECTED_KAPPAS),
        "ct2_values_per_benchmark": [str(value) for value in sorted(EXPECTED_CT2)],
        "ct3_values_per_benchmark": [str(value) for value in sorted(EXPECTED_CT3)],
        "card_convention": "D3=k3-1,D4=k4-1",
        "ct1": "0",
    }


def validate_process(process_dir: Path) -> dict[str, object]:
    executable = process_dir / "bin" / "generate_events"
    param_card = process_dir / "Cards" / "param_card.dat"
    coupling_source = process_dir / "Source" / "MODEL" / "couplings1.f"
    proc_card = process_dir / "Cards" / "proc_card_mg5.dat"
    for path in (executable, param_card, coupling_source, proc_card):
        if not path.is_file():
            raise CampaignError(f"required generated-process file is missing: {path}")

    param_text = param_card.read_text(encoding="utf-8", errors="replace")
    expected_codes = list(LHA_CODES.values())
    parameters = extract_slha_parameters(param_text, expected_codes)
    if set(parameters) != set(expected_codes):
        raise CampaignError(
            f"generated parameter card does not expose LHA codes {expected_codes}"
        )

    source_text = coupling_source.read_text(encoding="utf-8", errors="replace").upper()
    required_formula_pairs = (
        ("GC_HHH_MHEFT", "MDL_D3"),
        ("GC_HHHH_MHEFT", "MDL_D4"),
    )
    for coupling, parameter in required_formula_pairs:
        if not re.search(rf"{coupling}\s*=.*{parameter}", source_text):
            raise CampaignError(f"{coupling} is not generated as a function of {parameter}")
    for coupling in ("GC_30", "GC_HHHH"):
        if not re.search(rf"{coupling}\s*=", source_text):
            raise CampaignError(f"ordinary SM coupling {coupling} is absent")

    required_calls = {"GC_HHH_MHEFT", "GC_HHHH_MHEFT", "GC_30", "GC_HHHH"}
    found_calls: set[str] = set()
    for path in (process_dir / "SubProcesses").rglob("*helas_calls*.f"):
        text = path.read_text(encoding="utf-8", errors="replace").upper()
        found_calls.update(coupling for coupling in required_calls if coupling in text)
        if found_calls == required_calls:
            break
    if found_calls != required_calls:
        raise CampaignError(
            "generated matrix element does not call all SM/anomalous self-couplings: "
            f"missing {sorted(required_calls - found_calls)}"
        )

    process_text = proc_card.read_text(encoding="utf-8", errors="replace").lower()
    if not re.search(r"generate\s+g\s+g\s*>\s*h\s+h\s+h", process_text):
        raise CampaignError("process card is not g g > h h h")
    if "noborn=qcd" not in process_text:
        raise CampaignError("process card is not the requested loop-induced QCD process")

    return {
        "process_dir": str(process_dir.resolve()),
        "template_card_inputs_before_runtime_overwrite": {
            str(code): str(parameters[code]) for code in expected_codes
        },
        "coupling_source_sha256": sha256(coupling_source),
        "subprocess_index_sha256": sha256(process_dir / "SubProcesses" / "subproc.mg"),
        "matrix_element_couplings": sorted(found_calls),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-dir", type=Path, default=DEFAULT_PROCESS_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _, grid = validate_grid()
    process = validate_process(args.process_dir.expanduser().resolve())
    print(json.dumps({"status": "validated", "grid": grid, "process": process}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        raise SystemExit(f"campaign validation failed: {exc}") from exc
