#!/usr/bin/env python3
"""Set an already-generated process's runtime card templates to the SM point."""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.run_scan import (  # noqa: E402
    LHA_CODES,
    CampaignError,
    atomic_write,
    extract_slha_parameters,
    replace_slha_parameters,
)


CARD_NAMES = ("param_card.dat", "param_card_default.dat")
SM_INPUTS = {code: Decimal("0") for code in LHA_CODES.values()}


def set_sm_defaults(process_dir: Path) -> list[Path]:
    replacements: list[tuple[Path, bytes]] = []
    for name in CARD_NAMES:
        card = process_dir / "Cards" / name
        if not card.is_file():
            raise CampaignError(f"generated-process card is missing: {card}")
        original = card.read_text(encoding="utf-8")
        replacement = replace_slha_parameters(original, SM_INPUTS)
        actual = extract_slha_parameters(replacement, list(SM_INPUTS))
        if actual != SM_INPUTS:
            raise CampaignError(f"failed to construct SM defaults for {card}")
        replacements.append((card, replacement.encode("utf-8")))
    for card, replacement in replacements:
        atomic_write(card, replacement)
    return [card for card, _ in replacements]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    process_dir = args.process_dir.expanduser().resolve()
    for card in set_sm_defaults(process_dir):
        print(f"Set CT1=CT2=CT3=D3=D4=0 in {card}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CampaignError as exc:
        raise SystemExit(f"failed to set generated-process SM defaults: {exc}") from exc
