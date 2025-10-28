#!/usr/bin/env python3
"""Plot time-averaged power/current/voltage traces from processed TSV data.

The CLI is intentionally lightweight: it expects a tab-delimited file emitted by
``src/JPE_circuit_model/post_processing/time_averaging.py`` and produces three
PNG figures matching the DailyNote visualisations used on 2025-10-01.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot power/current/voltage traces from time-averaged TSV."
    )
    parser.add_argument("input_tsv", type=Path, help="Time-averaged TSV file.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for output PNG files.",
    )
    parser.add_argument(
        "--prefix",
        default="time_average",
        help="Filename prefix for saved figures (default: time_average).",
    )
    return parser.parse_args()


def load_time_series(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t")
    if "time" not in df.columns:
        raise KeyError("time column missing from TSV")
    df["time"] = pd.to_datetime(df["time"])
    df["elapsed_ms"] = (df["time"] - df["time"].iloc[0]).dt.total_seconds() * 1e3
    if {"V(nt)", "V(na)"} <= set(df.columns):
        df["delta_v"] = df["V(nt)"] - df["V(na)"]
    return df


def plot_series(
    df: pd.DataFrame,
    *,
    x: str,
    y: str,
    ylabel: str,
    output: Path,
    color: str,
) -> None:
    values = df[y].to_numpy()
    mask = np.isfinite(values)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(df.loc[mask, x], values[mask], color=color, linewidth=1.4)
    ax.set_xlabel("Time [ms]")
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", linewidth=0.5)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    df = load_time_series(args.input_tsv)
    out_dir = args.output_dir
    prefix = args.prefix

    if "power" in df.columns:
        plot_series(
            df,
            x="elapsed_ms",
            y="power",
            ylabel="Power [W]",
            output=out_dir / f"{prefix}_power_time.png",
            color="#1f77b4",
        )
    if "I(Rgnd)" in df.columns:
        df["current_mA"] = df["I(Rgnd)"] * 1e3
        plot_series(
            df,
            x="elapsed_ms",
            y="current_mA",
            ylabel="Ground Return Current [mA]",
            output=out_dir / f"{prefix}_current_time.png",
            color="#d62728",
        )
    if "delta_v" in df.columns:
        plot_series(
            df,
            x="elapsed_ms",
            y="delta_v",
            ylabel="Differential Voltage [V]",
            output=out_dir / f"{prefix}_voltage_time.png",
            color="#2ca02c",
        )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
