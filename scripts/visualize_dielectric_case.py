#!/usr/bin/env python3
"""Visualise LTspice dielectric simulations in the DailyNote style.

This helper consumes the down-sampled CSV files produced by
``run_dielectric_simulations.py`` and re-creates the figure set used in
``DailyNote/20251001/JPE_circuit_analysis.qmd``: time traces for radiated power,
ground return current, terminal voltage, temperature, and the DC-style scatter
plot. The script keeps all artefacts under ``Data/`` and ``Images/`` so that the
workflow remains reproducible inside the repository.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from .run_dielectric_simulations import read_raw_header
except ImportError:  # pragma: no cover - allow direct execution
    from run_dielectric_simulations import read_raw_header


def read_netlist_with_fallback(path: Path) -> str:
    """Return netlist text handling legacy encodings such as CP1252."""

    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate DailyNote-style visualisations for dielectric runs",
    )
    parser.add_argument(
        "case",
        help="Case identifier, e.g. 1-1-1",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Directory under Data/holding <case>/<netlist>_timeseries.csv",
    )
    parser.add_argument(
        "--netlist-dir",
        type=Path,
        help="Directory containing the source JPE_diel_*.net files (optional).",
    )
    parser.add_argument(
        "--output-data",
        type=Path,
        required=True,
        help="Destination under Data/ for processed CSV/JSON outputs.",
    )
    parser.add_argument(
        "--figure-dir",
        type=Path,
        required=True,
        help="Destination under Images/ for generated figures.",
    )
    parser.add_argument(
        "--resample",
        default="1ms",
        help="Pandas offset for time averaging (default: 1ms).",
    )
    parser.add_argument(
        "--power-resistance",
        type=float,
        help="Override radiation resistance instead of parsing the netlist.",
    )
    parser.add_argument(
        "--time-unit",
        default="s",
        help="Unit of the 'time' column (pandas-compatible, default seconds).",
    )
    return parser.parse_args()


SI_SUFFIXES = {
    "T": 1e12,
    "G": 1e9,
    "MEG": 1e6,
    "K": 1e3,
    "M": 1e-3,
    "U": 1e-6,
    "N": 1e-9,
    "P": 1e-12,
    "F": 1e-15,
    "A": 1e-18,
}


class NetlistParseError(RuntimeError):
    """Raised when a required value cannot be extracted from the netlist."""


def parse_spice_number(token: str) -> float:
    """Convert a SPICE numeric literal (including suffix) into a float."""

    token = token.strip()
    try:
        return float(token)
    except ValueError:
        upper = token.upper()
        if upper.endswith("MEG"):
            return float(upper[:-3]) * SI_SUFFIXES["MEG"]
        if len(upper) < 2:
            raise
        suffix = upper[-1]
        if suffix not in SI_SUFFIXES:
            raise
        return float(upper[:-1]) * SI_SUFFIXES[suffix]


def resolve_radiation_resistance(
    case: str,
    data_root: Path,
    netlist_dir: Path | None,
    override: float | None,
) -> tuple[float, Path]:
    if override is not None:
        netlist_path = (netlist_dir or data_root / case) / f"JPE_diel_{case}.net"
        return override, netlist_path

    candidate_paths: list[Path] = []
    case_dir = data_root / case
    candidate_paths.append(case_dir / f"JPE_diel_{case}.net")
    if netlist_dir is not None:
        candidate_paths.append(netlist_dir / f"JPE_diel_{case}.net")

    for candidate in candidate_paths:
        if candidate.exists():
            value = extract_radiation_resistance(candidate)
            return value, candidate

    raise NetlistParseError(
        f"Unable to locate netlist for case {case} in {candidate_paths}."
    )


def extract_radiation_resistance(netlist: Path) -> float:
    pattern = re.compile(r"^R_rad\b\s+\S+\s+\S+\s+(\S+)", re.IGNORECASE)
    for line in read_netlist_with_fallback(netlist).splitlines():
        match = pattern.match(line.strip())
        if match:
            try:
                return parse_spice_number(match.group(1))
            except Exception as exc:  # noqa: BLE001 - surface parsing issue
                raise NetlistParseError(
                    f"Failed to parse R_rad value from {netlist}: {line.strip()}"
                ) from exc
    raise NetlistParseError(f"R_rad definition not found in {netlist}")


@dataclass(slots=True)
class ProcessedData:
    case: str
    raw: pd.DataFrame
    resampled: pd.DataFrame
    power_resistance: float
    netlist_path: Path
    raw_path: Path


def load_timeseries(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    df = pd.read_csv(csv_path)
    if "time" not in df.columns:
        raise KeyError("time")
    return df


def enrich_dataframe(
    df: pd.DataFrame,
    resistance: float,
    time_unit: str,
) -> pd.DataFrame:
    df_sorted = df.drop_duplicates(subset=["time"], keep="last").sort_values("time")
    df_sorted = df_sorted.reset_index(drop=True)

    df_sorted["time_seconds"] = pd.to_numeric(df_sorted["time"], errors="coerce")
    if df_sorted["time_seconds"].isna().any():
        raise ValueError("Encountered non-numeric entries in time column")

    df_sorted["delta_v"] = df_sorted["V(nd)"] - df_sorted["V(na)"]
    df_sorted["i_rad"] = df_sorted["I(R_rad)"]
    df_sorted["i_return"] = df_sorted["I(R_gnd)"]
    df_sorted["power_w"] = (df_sorted["i_rad"] ** 2) * resistance
    df_sorted["power_uW"] = df_sorted["power_w"] * 1e6
    df_sorted["current_mA"] = df_sorted["i_return"] * 1e3

    time_index = pd.to_timedelta(df_sorted["time_seconds"], unit=time_unit)
    df_sorted = df_sorted.assign(time_td=time_index)
    df_sorted = df_sorted.set_index("time_td", drop=False)

    return df_sorted


def resample_dataframe(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg_columns = {
        "delta_v": "mean",
        "power_w": "mean",
        "power_uW": "mean",
        "current_mA": "mean",
        "V(t)": "mean",
        "V(nd)": "mean",
        "V(na)": "mean",
        "I(R_rad)": "mean",
        "I(R_gnd)": "mean",
        "time_seconds": "mean",
    }
    resampled = df.resample(rule).agg(agg_columns).dropna(how="all")
    resampled = resampled.reset_index(drop=False)
    resampled["time_seconds"] = resampled["time_seconds"].fillna(
        resampled["time_td"].dt.total_seconds()
    )
    return resampled


def save_dataframe(df: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destination, index=False)


def save_summary(stats: dict[str, float], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def _configure_figure_defaults() -> None:
    plt.rcParams.setdefault("axes.grid", True)
    plt.rcParams.setdefault("text.usetex", False)


def plot_time_series(
    time_axis: Iterable[float],
    values: Iterable[float],
    ylabel: str,
    title: str,
    destination: Path,
) -> None:
    _configure_figure_defaults()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    ax.plot(time_axis, values, linewidth=1.2)
    ax.set_xlabel("Time [ms]")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(destination, dpi=300)
    plt.close(fig)


def plot_dc_scatter(df: pd.DataFrame, destination: Path) -> None:
    _configure_figure_defaults()
    destination.parent.mkdir(parents=True, exist_ok=True)

    delta_v = df["delta_v"].to_numpy()
    power_uW = df["power_uW"].to_numpy()
    current_mA = df["current_mA"].to_numpy()

    color_data = df["power_w"].to_numpy()

    fig = plt.figure(figsize=(8.0, 8.0))
    grid = fig.add_gridspec(nrows=2, ncols=2, height_ratios=[1, 3], width_ratios=[3, 1])

    ax_power = fig.add_subplot(grid[0, 0])
    ax_joint = fig.add_subplot(grid[1, 0], sharex=ax_power)
    ax_current = fig.add_subplot(grid[1, 1], sharey=ax_joint)

    size = max(5, int(math.sqrt(len(delta_v))))
    scatter_kwargs = {
        "c": color_data,
        "cmap": "viridis",
        "s": size,
        "alpha": 0.8,
        "linewidths": 0,
    }

    ax_power.scatter(delta_v, power_uW, **scatter_kwargs)
    ax_power.set_ylabel("Radiated Power [µW]")
    ax_power.set_xticklabels([])

    ax_joint.scatter(delta_v, current_mA, **scatter_kwargs)
    ax_joint.set_xlabel("Differential Voltage [V]")
    ax_joint.set_ylabel("Return Current [mA]")

    ax_current.scatter(power_uW, current_mA, **scatter_kwargs)
    ax_current.set_xlabel("Radiated Power [µW]")
    ax_current.set_yticklabels([])

    fig.tight_layout()
    fig.savefig(destination, dpi=300)
    plt.close(fig)


def plot_waveforms(sample_df: pd.DataFrame, destination: Path, case: str) -> None:
    _configure_figure_defaults()
    destination.parent.mkdir(parents=True, exist_ok=True)

    fig, (ax_top, ax_bottom) = plt.subplots(2, 1, sharex=True, figsize=(7.2, 6.0))
    time_axis = sample_df["time"]

    voltage_columns = [col for col in sample_df.columns if col.startswith("V(")]
    current_columns = [col for col in sample_df.columns if col.startswith("I(")]

    for column in voltage_columns:
        values = sample_df[column].to_numpy()
        mask = np.isfinite(values)
        if not np.any(mask):
            continue
        ax_top.plot(time_axis[mask], values[mask], label=column)
    ax_top.set_ylabel("Voltage [V]")
    ax_top.set_title(f"Case {case}: node voltages")
    ax_top.legend(loc="best")

    for column in current_columns:
        values = (sample_df[column] * 1e3).to_numpy()
        mask = np.isfinite(values)
        if not np.any(mask):
            continue
        ax_bottom.plot(time_axis[mask], values[mask], label=f"{column} (mA)")
    ax_bottom.set_ylabel("Current [mA]")
    ax_bottom.set_xlabel("t [µs]")
    ax_bottom.set_title("Source branch currents")
    ax_bottom.legend(loc="best")

    fig.tight_layout()
    fig.savefig(destination, dpi=300)
    plt.close(fig)


def _locate_raw_file(case_dir: Path) -> Path:
    candidates = sorted(
        p for p in case_dir.glob("*.raw") if not p.name.lower().endswith(".op.raw")
    )
    if not candidates:
        raise FileNotFoundError(f"No transient RAW file found under {case_dir}")
    if len(candidates) > 1:
        raise RuntimeError(f"Multiple RAW files found under {case_dir}: {candidates}")
    return candidates[0]


def aggregate_raw_waveforms(
    raw_path: Path,
    *,
    resample_rule: str,
    signals: Iterable[str],
    resistance: float,
    sample_target: int = 20_000,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    resample_seconds = pd.Timedelta(resample_rule).total_seconds()
    if resample_seconds <= 0:
        raise ValueError(f"Invalid resample rule {resample_rule!r}")

    data_offset, variable_names, point_count = read_raw_header(raw_path)
    if not variable_names or variable_names[0].lower() != "time":
        raise RuntimeError(f"{raw_path} does not expose a leading time column")
    value_names = variable_names[1:]
    name_lookup = {name.lower(): idx for idx, name in enumerate(value_names)}

    signal_list = list(signals)
    required = {"V(nd)", "V(na)", "I(R_rad)", "I(R_gnd)", "V(t)"}
    missing_required = [name for name in required if name.lower() not in {s.lower() for s in signal_list}]
    if missing_required:
        raise ValueError(f"Missing required signals for aggregation: {missing_required}")

    idx_irad = signal_list.index("I(R_rad)")
    idx_ignd = signal_list.index("I(R_gnd)")
    idx_vnd = signal_list.index("V(nd)")
    idx_vna = signal_list.index("V(na)")
    signal_indices: list[int] = []
    for name in signal_list:
        idx = name_lookup.get(name.lower())
        if idx is None:
            raise KeyError(f"{raw_path} does not contain signal {name}")
        signal_indices.append(idx)

    dtype = np.dtype([("time", "<f8"), ("values", ("<f4", len(value_names)))])
    record_size = dtype.itemsize

    bin_offset = 0
    counts = np.zeros(0, dtype=np.float64)
    sum_time_rel = np.zeros(0, dtype=np.float64)
    sum_signals: dict[str, np.ndarray] = {
        name: np.zeros(0, dtype=np.float64) for name in signal_list
    }
    sum_irad_sq = np.zeros(0, dtype=np.float64)

    chunk_points = 1 << 14  # 16384 records per chunk

    def compute_time_bounds() -> tuple[float, float, int]:
        min_time = math.inf
        max_time = -math.inf
        kept_points = 0
        with raw_path.open("rb") as handle_bounds:
            handle_bounds.seek(data_offset)
            leftover_bounds = bytearray()
            while True:
                chunk_bytes = handle_bounds.read(chunk_points * record_size)
                if not chunk_bytes and not leftover_bounds:
                    break
                leftover_bounds.extend(chunk_bytes)
                available_bounds = len(leftover_bounds) // record_size
                if available_bounds == 0:
                    continue
                block_bounds = np.frombuffer(
                    memoryview(leftover_bounds)[: available_bounds * record_size],
                    dtype=dtype,
                    count=available_bounds,
                )
                leftover_bounds = bytearray(
                    leftover_bounds[available_bounds * record_size :]
                )
                times_bounds = block_bounds["time"].astype(np.float64, copy=False)
                if times_bounds.size:
                    min_time = min(min_time, float(np.min(times_bounds)))
                    max_time = max(max_time, float(np.max(times_bounds)))
                    kept_points += int(np.count_nonzero(times_bounds >= 0.0))
        if not math.isfinite(min_time) or not math.isfinite(max_time):
            raise RuntimeError(f"Failed to determine time bounds for {raw_path}")
        return min_time, max_time, kept_points

    min_time, max_time, kept_points = compute_time_bounds()
    reference_time = 0.0

    target_count = min(kept_points if kept_points else point_count, sample_target)
    sample_indices = (
        np.linspace(0, max(kept_points, 1) - 1, num=target_count, dtype=np.int64)
        if kept_points
        else np.zeros(0, dtype=np.int64)
    )
    sample_pos = 0
    down_time: list[float] = []
    down_values: dict[str, list[float]] = {name: [] for name in signal_list}

    chunk_points = 1 << 14  # 16384 records per chunk

    def ensure_bin_range(min_bin: int, max_bin: int) -> None:
        nonlocal counts, sum_time_rel, sum_irad_sq, sum_signals, bin_offset
        if counts.size == 0:
            size = max_bin - min_bin + 1
            bin_offset = min_bin
            counts = np.zeros(size, dtype=np.float64)
            sum_time_rel = np.zeros(size, dtype=np.float64)
            sum_irad_sq = np.zeros(size, dtype=np.float64)
            for key in signal_list:
                sum_signals[key] = np.zeros(size, dtype=np.float64)
            return
        if min_bin < bin_offset:
            prepend = bin_offset - min_bin
            counts = np.pad(counts, (prepend, 0))
            sum_time_rel = np.pad(sum_time_rel, (prepend, 0))
            sum_irad_sq = np.pad(sum_irad_sq, (prepend, 0))
            for key in signal_list:
                sum_signals[key] = np.pad(sum_signals[key], (prepend, 0))
            bin_offset = min_bin
        if max_bin >= bin_offset + counts.size:
            append = max_bin - (bin_offset + counts.size - 1)
            counts = np.pad(counts, (0, append))
            sum_time_rel = np.pad(sum_time_rel, (0, append))
            sum_irad_sq = np.pad(sum_irad_sq, (0, append))
            for key in signal_list:
                sum_signals[key] = np.pad(sum_signals[key], (0, append))

    total_points = 0
    total_irad_sq = 0.0
    total_ignd = 0.0
    total_delta_v = 0.0

    mins = {name: np.inf for name in signal_list}
    maxs = {name: -np.inf for name in signal_list}

    first_time: float | None = None
    last_time: float | None = None

    with raw_path.open("rb") as handle:
        handle.seek(data_offset)
        leftover = bytearray()
        processed_kept = 0
        while True:
            chunk = handle.read(chunk_points * record_size)
            if not chunk and not leftover:
                break
            leftover.extend(chunk)
            available = len(leftover) // record_size
            if available == 0:
                continue

            block = np.frombuffer(
                memoryview(leftover)[: available * record_size],
                dtype=dtype,
                count=available,
            )
            leftover = bytearray(leftover[available * record_size :])

            times = block["time"].astype(np.float64, copy=False)
            values = block["values"].astype(np.float64, copy=False)
            selected = values[:, signal_indices]

            mask = (times >= 0.0) & (times <= max_time + 1e-12)
            if not np.any(mask):
                continue
            times = times[mask]
            values = values[mask]
            selected = selected[mask]
            rel_time = times - reference_time

            bins = np.floor_divide(rel_time, resample_seconds).astype(np.int64)
            if bins.size == 0:
                continue
            min_bin = int(np.floor(np.min(bins)))
            max_bin = int(np.floor(np.max(bins)))
            ensure_bin_range(min_bin, max_bin)
            adjusted_bins = bins - bin_offset

            np.add.at(counts, adjusted_bins, 1)
            np.add.at(sum_time_rel, adjusted_bins, rel_time)

            for column_idx, name in enumerate(signal_list):
                column_values = selected[:, column_idx]
                np.add.at(sum_signals[name], adjusted_bins, column_values)
                mins[name] = min(mins[name], float(np.min(column_values)))
                maxs[name] = max(maxs[name], float(np.max(column_values)))

            irad = selected[:, idx_irad]
            ignd = selected[:, idx_ignd]
            vnd = selected[:, idx_vnd]
            vna = selected[:, idx_vna]

            np.add.at(sum_irad_sq, adjusted_bins, irad * irad)

            total_points += irad.size
            total_irad_sq += float(np.sum(irad * irad))
            total_ignd += float(np.sum(ignd))
            total_delta_v += float(np.sum(vnd - vna))

            if target_count:
                upper = processed_kept + irad.size
                while sample_pos < target_count and sample_indices[sample_pos] < upper:
                    local_idx = int(sample_indices[sample_pos] - processed_kept)
                    down_time.append(float(times[local_idx]))
                    for column_idx, name in enumerate(signal_list):
                        down_values[name].append(float(selected[local_idx, column_idx]))
                    sample_pos += 1

            processed_kept += irad.size
            if last_time is None:
                last_time = float(np.max(times))
            else:
                last_time = max(last_time, float(np.max(times)))
            if first_time is None:
                first_time = float(np.min(times))
            else:
                first_time = min(first_time, float(np.min(times)))

        if processed_kept != kept_points:
            raise RuntimeError(
                f"RAW length mismatch for {raw_path}: expected {kept_points}, processed {processed_kept}"
            )

    if counts.size == 0 or np.all(counts == 0):
        raise RuntimeError(f"No samples aggregated from {raw_path}")

    nonzero_indices = np.nonzero(counts)[0]
    start_idx = int(nonzero_indices[0])
    end_idx = int(nonzero_indices[-1]) + 1
    counts = counts[start_idx:end_idx]
    sum_time_rel = sum_time_rel[start_idx:end_idx]
    sum_irad_sq = sum_irad_sq[start_idx:end_idx]
    for name in signal_list:
        sum_signals[name] = sum_signals[name][start_idx:end_idx]
    bin_offset += start_idx

    valid_mask = counts > 0
    counts_nz = counts[valid_mask]
    sum_time_rel = sum_time_rel[valid_mask]
    for name in signal_list:
        sum_signals[name] = sum_signals[name][valid_mask]
    sum_irad_sq = sum_irad_sq[valid_mask]

    time_seconds = sum_time_rel / counts_nz
    time_seconds = time_seconds - time_seconds.min()

    resampled_dict: dict[str, np.ndarray] = {
        "time_seconds": time_seconds,
        "V(nd)": sum_signals["V(nd)"] / counts_nz,
        "V(na)": sum_signals["V(na)"] / counts_nz,
        "V(t)": sum_signals["V(t)"] / counts_nz,
        "I(R_rad)": sum_signals["I(R_rad)"] / counts_nz,
        "I(R_gnd)": sum_signals["I(R_gnd)"] / counts_nz,
    }
    resampled_dict["delta_v"] = (
        resampled_dict["V(nd)"] - resampled_dict["V(na)"]
    )
    resampled_dict["power_w"] = (
        sum_irad_sq / counts_nz * resistance
    )
    resampled_dict["power_uW"] = resampled_dict["power_w"] * 1e6
    resampled_dict["current_mA"] = resampled_dict["I(R_gnd)"] * 1e3

    resampled_df = pd.DataFrame(resampled_dict)

    sample_dict: dict[str, list[float]] = {"time": down_time}
    for name in signal_list:
        sample_dict[name] = down_values[name]
    sample_df = pd.DataFrame(sample_dict).sort_values("time", kind="mergesort").reset_index(drop=True)

    if first_time is None or last_time is None:
        raise RuntimeError(f"Failed to capture time bounds for {raw_path}")

    if first_time is None or last_time is None:
        raise RuntimeError(f"Failed to capture time bounds for {raw_path}")

    duration = max_time - min_time
    if duration <= 0:
        raise RuntimeError(f"Non-positive simulation duration detected in {raw_path}")

    resampled_peak_power_w = float(np.max(resampled_dict["power_w"]))
    resampled_peak_current_a = float(np.max(np.abs(resampled_dict["I(R_gnd)"])))
    resampled_peak_delta_v = float(np.max(np.abs(resampled_dict["delta_v"])))

    summary = {
        "time_stop_s": float(duration),
        "time_stop_us": float(duration * 1e6),
        "point_count": float(point_count),
        "downsample_stride": float(
            point_count / target_count if target_count else float("nan")
        ),
        "total_points": float(total_points),
        "total_irad_sq": float(total_irad_sq),
        "total_current_sum": float(total_ignd),
        "total_delta_v_sum": float(total_delta_v),
        "duration_s": float(duration),
        "peak_power_w": resampled_peak_power_w,
        "peak_current_a": resampled_peak_current_a,
        "peak_delta_v": resampled_peak_delta_v,
    }
    for name in signal_list:
        summary[f"{name}_min"] = float(mins[name])
        summary[f"{name}_max"] = float(maxs[name])

    return sample_df, resampled_df, summary


def generate_visualisations(args: argparse.Namespace) -> ProcessedData:
    case = args.case
    case_dir = args.data_root / case
    raw_path = _locate_raw_file(case_dir)

    resistance, netlist_path = resolve_radiation_resistance(
        case,
        args.data_root,
        args.netlist_dir,
        args.power_resistance,
    )

    signals = ["V(nd)", "V(na)", "V(t)", "V(nc)", "V(nb)", "I(R_rad)", "I(R_gnd)"]
    sample_df, resampled, aggregation = aggregate_raw_waveforms(
        raw_path,
        resample_rule=args.resample,
        signals=signals,
        resistance=resistance,
    )

    output_case_dir = args.output_data / case
    save_dataframe(sample_df, output_case_dir / "timeseries_enriched.csv")
    save_dataframe(resampled, output_case_dir / f"timeseries_resampled_{args.resample}.csv")

    if resampled.empty:
        raise RuntimeError(f"Resampled dataframe for case {case} is empty")

    time_span_ms = float(
        (resampled["time_seconds"].iloc[-1] - resampled["time_seconds"].iloc[0]) * 1e3
    )

    duration_s = aggregation["duration_s"]

    mean_power_uW = float(resampled["power_uW"].mean())
    peak_power_uW = float(resampled["power_uW"].max())
    mean_current_mA = float(resampled["current_mA"].mean())
    peak_current_mA = float(np.abs(resampled["current_mA"]).max())
    mean_delta_v = float(resampled["delta_v"].mean())
    peak_delta_v = float(np.max(np.abs(resampled["delta_v"])))

    summary = {
        "case": case,
        "radiation_resistance_ohm": resistance,
        "time_span_ms": time_span_ms,
        "mean_power_uW": mean_power_uW,
        "peak_power_uW": peak_power_uW,
        "mean_current_mA": mean_current_mA,
        "peak_current_mA": peak_current_mA,
        "mean_delta_v": mean_delta_v,
        "peak_delta_v": peak_delta_v,
    }
    save_summary(summary, output_case_dir / "summary.json")

    figure_case_dir = args.figure_dir
    time_axis_ms = resampled["time_seconds"].to_numpy() * 1e3

    plot_time_series(
        time_axis_ms,
        resampled["power_uW"],
        ylabel="Radiated Power [µW]",
        title=f"Case {case}: Radiated Power (resampled {args.resample})",
        destination=figure_case_dir / f"{case}_power_time.png",
    )
    plot_time_series(
        time_axis_ms,
        resampled["current_mA"],
        ylabel="Return Current [mA]",
        title=f"Case {case}: Return Current (resampled {args.resample})",
        destination=figure_case_dir / f"{case}_current_time.png",
    )
    plot_time_series(
        time_axis_ms,
        resampled["delta_v"],
        ylabel="Differential Voltage [V]",
        title=f"Case {case}: Differential Voltage (resampled {args.resample})",
        destination=figure_case_dir / f"{case}_voltage_time.png",
    )
    if "V(t)" in resampled.columns:
        plot_time_series(
            time_axis_ms,
            resampled["V(t)"],
            ylabel="Temperature Node [K]",
            title=f"Case {case}: Mesa Temperature (resampled {args.resample})",
            destination=figure_case_dir / f"{case}_temperature_time.png",
        )

    plot_dc_scatter(resampled, figure_case_dir / f"{case}_dc_scatter.png")
    plot_waveforms(sample_df, figure_case_dir / f"JPE_diel_{case}_waveforms.png", case)

    return ProcessedData(
        case=case,
        raw=sample_df.reset_index(drop=True),
        resampled=resampled,
        power_resistance=resistance,
        netlist_path=netlist_path,
        raw_path=raw_path,
    )


def main() -> None:  # pragma: no cover - CLI entry
    args = parse_args()
    result = generate_visualisations(args)
    print(f"[INFO] Case {result.case} processed. Figures stored in {args.figure_dir}.")


if __name__ == "__main__":
    main()
