#!/usr/bin/env python3
"""Run an LTspice simulation directly from a legacy `.asc` schematic.

This helper mirrors the batch-processing pipeline implemented for the synthetic
dielectric netlists while preserving the original schematic directives found in
``examples/JPE_3stacks.asc``. It reuses the data extraction utilities from
``run_dielectric_simulations.py`` so that downstream analysis receives the same
CSV/JSON artefacts and quick-look plots.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parent

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

_RUNNER_SPEC = importlib.util.spec_from_file_location(
    "_dielectric_runner", SCRIPT_ROOT / "run_dielectric_simulations.py"
)
if _RUNNER_SPEC is None or _RUNNER_SPEC.loader is None:
    raise RuntimeError("Failed to load run_dielectric_simulations module")  # noqa: TRY003 - recoverable configuration issue

_dielectric = importlib.util.module_from_spec(_RUNNER_SPEC)
sys.modules["_dielectric_runner"] = _dielectric
_RUNNER_SPEC.loader.exec_module(_dielectric)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LTspice on a legacy schematic (.asc) and export CSV/plots."
    )
    parser.add_argument(
        "--asc-path",
        type=Path,
        default=PROJECT_ROOT / "examples" / "JPE_3stacks.asc",
        help="Path to the LTspice schematic (.asc) to simulate.",
    )
    parser.add_argument(
        "--case-name",
        help="Override case label used for output folders/files (defaults to schematic stem).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Destination under Data/ for numeric outputs.",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        required=True,
        help="Destination under Images/ for generated plots.",
    )
    parser.add_argument(
        "--ltspice-exe",
        type=Path,
        default=None,
        help="Optional override for the LTspice executable path.",
    )
    parser.add_argument(
        "--save-vars",
        nargs="+",
        default=list(_dielectric.DEFAULT_SAVE_VARS),
        help="Signals to persist via .save directive (injected before .tran).",
    )
    parser.add_argument(
        "--omit-default-options",
        action="store_true",
        help="Skip injecting the dielectric runner's default .options line.",
    )
    parser.add_argument(
        "--working-root",
        type=Path,
        default=PROJECT_ROOT.parent.parent / "tmp" / "legacy_asc_runs",
        help="Scratch directory for per-run LTspice working files.",
    )
    parser.add_argument(
        "--keep-working",
        action="store_true",
        help="Keep temporary working directories instead of cleaning them up.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asc_path = args.asc_path.resolve()
    if not asc_path.exists():
        raise FileNotFoundError(f"Schematic not found: {asc_path}")  # noqa: TRY003 - include missing path

    case = args.case_name or asc_path.stem
    data_dir = args.data_dir.resolve()
    figure_dir = args.figure_dir.resolve()
    working_root = args.working_root.resolve()

    data_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    working_root.mkdir(parents=True, exist_ok=True)

    exe = _dielectric.resolve_ltspice_executable(args.ltspice_exe)

    logger.info("Running schematic %s as case '%s' via %s", asc_path, case, exe)
    _dielectric.run_case(
        case=case,
        netlist_path=asc_path,
        exe=exe,
        data_dir=data_dir,
        figure_dir=figure_dir,
        working_root=working_root,
        save_vars=list(dict.fromkeys(args.save_vars)),
        keep_working=args.keep_working,
        inject_options=not args.omit_default_options,
    )


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
