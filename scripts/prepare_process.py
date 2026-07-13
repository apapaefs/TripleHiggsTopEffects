#!/usr/bin/env python3
"""Prepare the restricted-model g g > h h h MadGraph process."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MG5_ROOT = REPOSITORY_ROOT / "MG5_aMC_v3_5_16"
DEFAULT_MODEL_SOURCE = (
    REPOSITORY_ROOT / "multihiggs_loop_sm" / "heft_loop_sm_restricted5"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mg5-root", type=Path, default=DEFAULT_MG5_ROOT)
    parser.add_argument("--model-source", type=Path, default=DEFAULT_MODEL_SOURCE)
    parser.add_argument("--process-dir", type=Path)
    parser.add_argument(
        "--install-collier",
        action="store_true",
        help="ask MadGraph to install Collier before writing the process",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the copy action and MadGraph command deck without changing files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mg5_root = args.mg5_root.expanduser().resolve()
    model_source = args.model_source.expanduser().resolve()
    process_dir = (
        args.process_dir.expanduser().resolve()
        if args.process_dir
        else mg5_root / "gg_hhh_restricted5"
    )
    model_target = mg5_root / "models" / "heft_loop_sm_restricted5"
    mg5 = mg5_root / "bin" / "mg5_aMC"
    generate_events = process_dir / "bin" / "generate_events"

    if generate_events.is_file():
        print(f"Process already prepared: {process_dir}")
        return 0
    if process_dir.exists():
        raise SystemExit(
            f"Refusing to replace incomplete existing process directory: {process_dir}"
        )
    if not mg5.is_file():
        raise SystemExit(f"MadGraph executable not found: {mg5}")

    if not model_target.is_dir():
        if not model_source.is_dir():
            raise SystemExit(f"Restricted UFO source not found: {model_source}")
        print(f"Copy model: {model_source} -> {model_target}")
        if not args.dry_run:
            shutil.copytree(model_source, model_target)
    else:
        print(f"Using installed model: {model_target}")

    commands = [
        "set automatic_html_opening False",
        f"import model {model_target}",
        "generate g g > h h h [noborn=QCD MHEFT] MHEFT^2<=6",
    ]
    if args.install_collier:
        commands.append("install collier")
    commands.append(f"output {process_dir}")
    deck = "\n".join(commands) + "\n"

    print("MadGraph command deck:")
    print(deck, end="")
    if args.dry_run:
        return 0

    deck_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".mg5", delete=False
        ) as handle:
            handle.write(deck)
            deck_path = Path(handle.name)
        subprocess.run([str(mg5), str(deck_path)], cwd=mg5_root, check=True)
    finally:
        if deck_path is not None:
            deck_path.unlink(missing_ok=True)

    if not generate_events.is_file():
        raise SystemExit(f"MadGraph did not create the expected process: {process_dir}")
    print(f"Prepared process: {process_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
