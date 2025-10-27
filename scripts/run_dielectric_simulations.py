#!/usr/bin/env python3
"""Batch LTspice simulations for dielectric parameter estimation decks.

This runner mirrors the workflow in
``Paper/DissertationTeX/chapters/ch05_nonlinear_circuit/dielectric_parameter_estimation/dielectric_parameter_estimation.tex``:

* copy each generated ``JPE_diel_*.net`` file to a temporary working directory,
  injecting a ``.save`` directive for the voltages and currents discussed in the
  dissertation;
* launch Wine-hosted LTspice in batch mode to acquire the transient response;
* parse the resulting RAW file with the in-repo ``cespy`` parser (loaded lazily to
  avoid its heavyweight package initialisation);
* export clean CSV tables, per-case summaries, and quick-look plots that respect the
  repository ``matplotlibrc`` for downstream notebook and manuscript usage.

The script keeps the example netlist folder untouched by moving all artefacts into the
``Data/`` and ``Images/`` destinations requested on the command line.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_ROOT.parent
DEFAULT_SAVE_VARS = (
    "V(Nd)",
    "V(Nc)",
    "V(Nb)",
    "V(Na)",
    "V(T)",
    "I(R_rad)",
    "I(R_gnd)",
)

DEFAULT_OPTIONS_LINE = (
    ".options reltol=2e-2 abstol=1e-8 chgtol=1e-12 trtol=7 method=gear maxord=2 gmin=1e-9"
)


@dataclass(slots=True)
class SimulationResult:
    """Container holding artefacts for a single simulation case."""

    case: str
    data_frame: pd.DataFrame
    summary: dict[str, float]
    raw_file: Path
    log_file: Path
    netlist_file: Path
    exec_log: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LTspice transient simulations for dielectric netlists",
    )
    parser.add_argument(
        "--netlist-dir",
        type=Path,
        default=PROJECT_ROOT / "examples" / "dielectric_netlists",
        help="Directory containing JPE_diel_*.net files",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        help="Subset of cases to run (e.g. 1-1-1 3-16-60)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Destination under Data/ for numeric outputs",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        required=True,
        help="Destination under Images/ for generated plots",
    )
    parser.add_argument(
        "--ltspice-exe",
        type=Path,
        default=None,
        help=(
            "Override LTspice executable (defaults to $LTSPICEFOLDER/$LTSPICEEXECUTABLE)"
        ),
    )
    parser.add_argument(
        "--save-vars",
        nargs="+",
        default=list(DEFAULT_SAVE_VARS),
        help="Signals to persist via .save directive",
    )
    parser.add_argument(
        "--working-root",
        type=Path,
        default=PROJECT_ROOT.parent.parent / "tmp" / "dielectric_runs",
        help="Scratch directory for per-case LTspice outputs",
    )
    parser.add_argument(
        "--keep-working",
        action="store_true",
        help="Keep temporary working directories instead of removing the netlist copy",
    )
    return parser.parse_args()


def resolve_ltspice_executable(cli_value: Path | None) -> Path:
    if cli_value is not None:
        return cli_value

    folder = os.environ.get("LTSPICEFOLDER")
    exe_name = os.environ.get("LTSPICEEXECUTABLE", "XVIIx64.exe")
    if folder is None:
        default_folder = Path.home() / ".wine" / "drive_c" / "Program Files" / "LTC" / "LTspiceXVII"
        candidate = default_folder / exe_name
    else:
        candidate = Path(folder) / exe_name

    if not candidate.exists():
        raise FileNotFoundError(
            f"LTspice executable not found at {candidate}. Set --ltspice-exe or environment variables."
        )
    return candidate


def discover_cases(netlist_dir: Path, explicit: list[str] | None) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for netlist in sorted(netlist_dir.glob("JPE_diel_*.net")):
        case = netlist.stem.removeprefix("JPE_diel_")
        mapping[case] = netlist

    if explicit:
        missing = [case for case in explicit if case not in mapping]
        if missing:
            raise FileNotFoundError(
                f"Cases not found in {netlist_dir}: {', '.join(missing)}"
            )
        return {case: mapping[case] for case in explicit}

    return mapping


def insert_save_directive(
    original: Path,
    save_vars: Iterable[str],
    destination: Path,
) -> None:
    """Copy ``original`` to ``destination`` while injecting a .save directive."""

    content = original.read_text(encoding="utf-8")
    marker = ".tran"
    if marker not in content:
        raise RuntimeError(f"{original} does not contain a .tran directive")

    save_line = ".save " + " ".join(save_vars) + "\n"
    options_line = DEFAULT_OPTIONS_LINE + "\n"

    if ".save" in content:
        content = content.replace(".save", save_line + ".save", 1)
    else:
        prefix, suffix = content.split(marker, 1)
        content = prefix + save_line + options_line + marker + suffix

    if DEFAULT_OPTIONS_LINE not in content:
        content = content.replace(save_line, save_line + options_line, 1)

    destination.write_text(content, encoding="utf-8")


def run_ltspice(netlist: Path, exe: Path, exec_log: Path) -> None:
    absolute_netlist = netlist.resolve()
    netlist_for_wine = "Z:" + absolute_netlist.as_posix()
    cmd = [
        "wine",
        exe.as_posix(),
        "-Run",
        "-b",
        netlist_for_wine,
    ]

    exec_log.parent.mkdir(parents=True, exist_ok=True)
    with exec_log.open("wb") as log_file:
        subprocess.run(cmd, check=True, stdout=log_file, stderr=subprocess.STDOUT)


def convert_log(log_path: Path, destination: Path) -> None:
    data = log_path.read_bytes()
    for encoding in ("utf-16", "utf-8", "cp1252"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")

    destination.write_text(text, encoding="utf-8")


def read_raw_header(raw_path: Path) -> tuple[int, list[str], int]:
    """Return the byte offset of binary data, variable names, and point count."""

    pattern = "Binary:\n".encode("utf-16le")
    with raw_path.open("rb") as handle:
        buffer = bytearray()
        while True:
            chunk = handle.read(4096)
            if not chunk:
                raise RuntimeError(f"Failed to locate Binary marker in {raw_path}")
            buffer.extend(chunk)
            idx = buffer.find(pattern)
            if idx != -1:
                header_end = idx + len(pattern)
                break
        data_offset = header_end
        while data_offset + 1 < len(buffer) and buffer[data_offset : data_offset + 2] == b"\x00\x00":
            data_offset += 2
        header_text = buffer[:header_end].decode("utf-16le")

    lines = [line.strip() for line in header_text.splitlines() if line.strip()]
    num_vars: int | None = None
    num_points: int | None = None
    variable_names: list[str] = []
    parsing_vars = False
    for line in lines:
        if line.startswith("No. Variables"):
            num_vars = int(line.split(":", 1)[1])
        elif line.startswith("No. Points"):
            num_points = int(line.split(":", 1)[1])
        elif line == "Variables:":
            parsing_vars = True
            continue
        elif parsing_vars and (num_vars is None or len(variable_names) < num_vars):
            parts = line.split()
            if len(parts) >= 3:
                variable_names.append(parts[1])

    if num_vars is None or num_points is None or len(variable_names) != num_vars:
        raise RuntimeError(f"Header parsing failed for {raw_path}")

    return data_offset, variable_names, num_points


def extract_waveforms(
    raw_path: Path,
    *,
    target_samples: int = 20_000,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Parse LTspice RAW output into a down-sampled dataframe and summary."""

    data_offset, variable_names, point_count = read_raw_header(raw_path)
    if not variable_names or variable_names[0].lower() != "time":
        raise RuntimeError(f"Unexpected variable ordering in {raw_path}")

    signal_names = variable_names[1:]
    num_signals = len(signal_names)

    dtype = np.dtype([("time", "<f8"), ("values", ("<f4", num_signals))])
    record_size = dtype.itemsize

    sample_stride = max(1, math.ceil(point_count / target_samples))
    mins = np.full(num_signals, np.inf, dtype=np.float64)
    maxs = np.full(num_signals, -np.inf, dtype=np.float64)

    tail_window = min(point_count, max(1000, math.ceil(point_count * 0.1)))
    tail_array = (
        np.empty((tail_window, num_signals), dtype=np.float64)
        if tail_window > 0
        else np.zeros((0, num_signals), dtype=np.float64)
    )
    tail_pos = 0
    tail_filled = 0

    down_time: list[float] = []
    down_values: dict[str, list[float]] = {name: [] for name in signal_names}

    processed = 0
    last_time = 0.0
    chunk_records = 200_000

    leftover = bytearray()

    with raw_path.open("rb") as handle:
        handle.seek(data_offset)

        while processed < point_count:
            to_read = min(chunk_records, point_count - processed)
            buffer = handle.read(to_read * record_size)
            if not buffer and not leftover:
                break
            if buffer:
                leftover.extend(buffer)
            available = len(leftover) // record_size
            if available == 0:
                continue
            block = np.frombuffer(
                memoryview(leftover)[: available * record_size], dtype=dtype, count=available
            )

            times = block["time"].astype(np.float64, copy=False)
            values = block["values"].astype(np.float64)

            mins = np.minimum(mins, values.min(axis=0))
            maxs = np.maximum(maxs, values.max(axis=0))

            count = values.shape[0]
            if tail_window > 0:
                if count >= tail_window:
                    tail_array[:] = values[-tail_window:, :]
                    tail_pos = 0
                    tail_filled = tail_window
                else:
                    end_pos = tail_pos + count
                    if end_pos <= tail_window:
                        tail_array[tail_pos:end_pos] = values
                    else:
                        first = tail_window - tail_pos
                        tail_array[tail_pos:] = values[:first]
                        tail_array[: count - first] = values[first:]
                    tail_pos = (tail_pos + count) % tail_window
                    tail_filled = min(tail_window, tail_filled + count)

            indices = processed + np.arange(count)
            mask = (indices % sample_stride) == 0
            if mask.any():
                down_time.extend(times[mask].tolist())
                sampled = values[mask]
                for idx, name in enumerate(signal_names):
                    down_values[name].extend(sampled[:, idx].tolist())

            processed += count
            last_time = float(times[-1])
            leftover = bytearray(leftover[available * record_size :])

    if processed != point_count:
        raise RuntimeError(
            f"RAW file length mismatch for {raw_path}: expected {point_count}, got {processed}"
        )

    if tail_window > 0 and tail_filled > 0:
        if tail_filled < tail_window:
            steady_block = tail_array[:tail_filled]
        elif tail_pos == 0:
            steady_block = tail_array
        else:
            steady_block = np.vstack((tail_array[tail_pos:], tail_array[:tail_pos]))
        steady_mean = steady_block.mean(axis=0)
    else:
        steady_mean = np.zeros(num_signals, dtype=np.float64)

    summary: dict[str, float] = {
        "time_stop_us": last_time,
        "downsample_stride": float(sample_stride),
        "point_count": float(point_count),
    }
    for idx, name in enumerate(signal_names):
        summary[f"{name}_steady_mean"] = float(steady_mean[idx])
        summary[f"{name}_max"] = float(maxs[idx])
        summary[f"{name}_min"] = float(mins[idx])

    data_dict: dict[str, list[float]] = {"time": down_time}
    for name in signal_names:
        data_dict[name] = down_values[name]
    dataframe = pd.DataFrame(data_dict)

    return dataframe, summary


def render_plot(df: pd.DataFrame, destination: Path, case: str) -> None:
    import matplotlib.pyplot as plt

    destination.parent.mkdir(parents=True, exist_ok=True)

    fig, (ax_top, ax_bottom) = plt.subplots(2, 1, sharex=True, figsize=(7.2, 6.0))
    time_axis = df["time"]

    voltage_columns = [col for col in df.columns if col.startswith("V(")]
    current_columns = [col for col in df.columns if col.startswith("I(")]

    for column in voltage_columns:
        ax_top.plot(time_axis, df[column], label=column)
    ax_top.set_ylabel("Voltage [V]")
    ax_top.set_title(f"Case {case}: node voltages")
    ax_top.legend(loc="best")

    for column in current_columns:
        ax_bottom.plot(time_axis, df[column] * 1e3, label=f"{column} (mA)")
    ax_bottom.set_ylabel("Current [mA]")
    ax_bottom.set_xlabel("t [µs]")
    ax_bottom.set_title("Source branch currents")
    ax_bottom.legend(loc="best")

    fig.tight_layout()
    fig.savefig(destination, dpi=300)
    plt.close(fig)


def run_case(
    case: str,
    netlist_path: Path,
    exe: Path,
    data_dir: Path,
    figure_dir: Path,
    working_root: Path,
    save_vars: list[str],
    keep_working: bool,
) -> SimulationResult:
    work_dir = working_root / case
    work_dir.mkdir(parents=True, exist_ok=True)
    netlist_copy = work_dir / netlist_path.name
    insert_save_directive(netlist_path, save_vars, netlist_copy)

    exec_log = work_dir / f"{case}_ltspice_exec.log"
    run_ltspice(netlist_copy, exe, exec_log)

    raw_path = netlist_copy.with_suffix(".raw")
    log_path = netlist_copy.with_suffix(".log")

    if not raw_path.exists():
        raise FileNotFoundError(f"RAW output not found: {raw_path}")
    if not log_path.exists():
        raise FileNotFoundError(f"Log output not found: {log_path}")

    df, summary_data = extract_waveforms(raw_path)

    case_dir = data_dir / case
    case_dir.mkdir(parents=True, exist_ok=True)

    csv_path = case_dir / f"{netlist_path.stem}_timeseries.csv"
    df.to_csv(csv_path, index=False, quoting=csv.QUOTE_NONNUMERIC)

    summary_path = case_dir / f"{netlist_path.stem}_summary.json"
    enriched_summary = {"case": case, **summary_data}
    summary_path.write_text(json.dumps(enriched_summary, indent=2), encoding="utf-8")

    raw_destination = case_dir / raw_path.name
    log_destination = case_dir / f"{netlist_path.stem}.log"
    netlist_destination = case_dir / netlist_path.name

    raw_path.replace(raw_destination)
    convert_log(log_path, log_destination)
    netlist_copy.replace(netlist_destination)

    op_source = work_dir / f"{netlist_path.stem}.op.raw"
    if op_source.exists():
        op_source.replace(case_dir / op_source.name)

    figure_path = figure_dir / f"{netlist_path.stem}_waveforms.png"
    render_plot(df, figure_path, case)

    exec_dest = case_dir / exec_log.name
    exec_log.replace(exec_dest)

    if not keep_working:
        try:
            work_dir.rmdir()
        except OSError:
            # Residual files (e.g., LTspice lock files) can be ignored.
            pass

    return SimulationResult(
        case=case,
        data_frame=df,
        summary=enriched_summary,
        raw_file=raw_destination,
        log_file=log_destination,
        netlist_file=netlist_destination,
        exec_log=exec_dest,
    )


def main() -> None:
    args = parse_args()
    exe = resolve_ltspice_executable(args.ltspice_exe)
    cases = discover_cases(args.netlist_dir, args.cases)
    data_dir = args.data_dir
    figure_dir = args.figure_dir
    working_root = args.working_root

    data_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    working_root.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, float]] = []

    for case, netlist_path in cases.items():
        print(f"[INFO] Running case {case} using {netlist_path}")
        result = run_case(
            case=case,
            netlist_path=netlist_path,
            exe=exe,
            data_dir=data_dir,
            figure_dir=figure_dir,
            working_root=working_root,
            save_vars=list(dict.fromkeys(args.save_vars)),
            keep_working=args.keep_working,
        )
        summaries.append(result.summary)

    if summaries:
        all_keys = {key for record in summaries for key in record.keys()}
        base_fields = ["case", "time_stop_us", "point_count", "downsample_stride"]
        other_fields = sorted(key for key in all_keys if key not in base_fields)
        fieldnames = base_fields + other_fields
        summary_table = data_dir / "summary.csv"
        with summary_table.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in summaries:
                writer.writerow(row)

    metadata = {
        "netlist_dir": str(args.netlist_dir.resolve()),
        "cases": list(cases.keys()),
        "ltspice_executable": str(exe),
        "save_variables": list(dict.fromkeys(args.save_vars)),
    }
    (data_dir / "run_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
