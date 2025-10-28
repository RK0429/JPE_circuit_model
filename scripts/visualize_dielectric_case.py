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
import pandas as pd


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
    input_csv: Path


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


def generate_visualisations(args: argparse.Namespace) -> ProcessedData:
    case = args.case
    case_dir = args.data_root / case
    csv_path = case_dir / f"JPE_diel_{case}_timeseries.csv"

    resistance, netlist_path = resolve_radiation_resistance(
        case,
        args.data_root,
        args.netlist_dir,
        args.power_resistance,
    )

    raw_df = load_timeseries(csv_path)
    enriched = enrich_dataframe(raw_df, resistance, args.time_unit)
    resampled = resample_dataframe(enriched, args.resample)

    output_case_dir = args.output_data / case
    save_dataframe(enriched.reset_index(drop=True), output_case_dir / "timeseries_enriched.csv")
    save_dataframe(resampled, output_case_dir / f"timeseries_resampled_{args.resample}.csv")

    stats = {
        "case": case,
        "radiation_resistance_ohm": resistance,
        "time_span_ms": float((resampled["time_seconds"].max() - resampled["time_seconds"].min()) * 1e3),
        "mean_power_uW": float(resampled["power_uW"].mean()),
        "peak_power_uW": float(resampled["power_uW"].max()),
        "mean_current_mA": float(resampled["current_mA"].mean()),
        "peak_current_mA": float(resampled["current_mA"].max()),
        "mean_delta_v": float(resampled["delta_v"].mean()),
        "peak_delta_v": float(resampled["delta_v"].max()),
    }
    save_summary(stats, output_case_dir / "summary.json")

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

    return ProcessedData(
        case=case,
        raw=enriched.reset_index(drop=True),
        resampled=resampled,
        power_resistance=resistance,
        netlist_path=netlist_path,
        input_csv=csv_path,
    )


def main() -> None:  # pragma: no cover - CLI entry
    args = parse_args()
    result = generate_visualisations(args)
    print(f"[INFO] Case {result.case} processed. Figures stored in {args.figure_dir}.")


if __name__ == "__main__":
    main()
