#!/usr/bin/env python3
"""Run a generated MadEvent process with its MadGraph 3.5 LHAPDF fix."""

from __future__ import annotations

import argparse
import logging
import logging.config
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Sequence


PDLABEL_ASSIGNMENT_RE = re.compile(
    r"^(\s*PDLABEL\s*=\s*)'[^']*'(\s*)$", re.MULTILINE
)


class CompatibilityError(RuntimeError):
    """A generated-process compatibility hook could not be applied safely."""


def repair_lhapdf_include(path: Path) -> None:
    """Force the generated Fortran global PDF label to LHAPDF."""
    text = path.read_text(encoding="utf-8")
    updated, replacements = PDLABEL_ASSIGNMENT_RE.subn(
        r"\1'lhapdf'\2", text
    )
    if replacements != 1:
        raise CompatibilityError(
            f"expected one PDLABEL assignment in {path}, found {replacements}"
        )
    if updated == text:
        return

    mode = path.stat().st_mode
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_madevent(process_dir: Path, arguments: Sequence[str]) -> int:
    process_dir = process_dir.resolve()
    internal_dir = process_dir / "bin" / "internal"
    if not (internal_dir / "madevent_interface.py").is_file():
        raise CompatibilityError(f"invalid generated process: {process_dir}")

    sys.path.insert(0, str(process_dir / "bin"))
    sys.path.insert(1, str(internal_dir))
    import madevent_interface as ME

    original_write = ME.banner_mod.RunCardLO.write_include_file

    def write_include_file(run_card, *args, **kwargs):
        result = original_write(run_card, *args, **kwargs)
        uses_lhapdf = (
            run_card["pdlabel"] == "lhapdf"
            or run_card["pdlabel1"] == "lhapdf"
            or run_card["pdlabel2"] == "lhapdf"
        )
        if uses_lhapdf:
            output_dir = Path(args[0]) if args else Path(kwargs["output_dir"])
            repair_lhapdf_include(output_dir / "run_card.inc")
        return result

    ME.banner_mod.RunCardLO.write_include_file = write_include_file

    import coloring_logging

    logging.config.fileConfig(internal_dir / "me5_logging.conf")
    logging.root.setLevel(logging.INFO)
    logging.getLogger("madevent").setLevel(logging.INFO)
    logging.getLogger("madgraph").setLevel(logging.INFO)

    command = "generate_events " + shlex.join(arguments)
    try:
        with ME.MadEventCmdShell.RunWebHandling(str(process_dir)):
            launch = ME.MadEventCmdShell(me_dir=str(process_dir), force_run=True)
            launch.run_cmd(command)
            launch.run_cmd("quit")
    except ME.MadEventAlreadyRunning as exc:
        logging.getLogger("madgraph").error(str(exc))
        return 1
    except KeyboardInterrupt:
        try:
            launch.run_cmd("quit")
        except Exception:
            pass
        return 130
    except Exception:
        logging.exception("MadEvent failed")
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--process-dir", required=True, type=Path)
    parser.add_argument("madevent_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.madevent_arguments[:1] == ["--"]:
        args.madevent_arguments = args.madevent_arguments[1:]
    if not args.madevent_arguments:
        parser.error("missing MadEvent generate_events arguments")
    return args


def main() -> int:
    args = parse_args()
    try:
        return run_madevent(args.process_dir, args.madevent_arguments)
    except (CompatibilityError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
