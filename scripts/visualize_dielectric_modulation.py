#!/usr/bin/env python3
"""Analyse high-frequency modulation runs for the dielectric 1-4-15 case."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:  # allow standalone execution
    from .visualize_dielectric_case import extract_radiation_resistance
except ImportError:  # pragma: no cover - fallback for script mode
    from visualize_dielectric_case import extract_radiation_resistance


@dataclass
class ModulationEntry:
    label: str
    f_phys_hz: float
    f_sim_hz: float
    vmod_peak_v: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate spectra and metrics for modulation experiments.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="JSON config produced after calibration (modulation_config.json).",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        required=True,
        help="Parent directory holding <label>/1-4-15/JPE_diel_1-4-15_timeseries.csv.",
    )
    parser.add_argument(
        "--analysis-root",
        type=Path,
        required=True,
        help="Destination base for derived CSV/JSON artefacts.",
    )
    parser.add_argument(
        "--figure-root",
        type=Path,
        required=True,
        help="Destination base for figures.",
    )
    parser.add_argument(
        "--steady-window",
        type=float,
        default=0.1,
        help="Duration (s) of the trailing window used for FFT (default 0.1 s).",
    )
    return parser.parse_args()


def load_config(path: Path) -> tuple[str, float, list[ModulationEntry]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = [
        ModulationEntry(
            label=item["label"],
            f_phys_hz=float(item["f_phys_hz"]),
            f_sim_hz=float(item["f_sim_hz"]),
            vmod_peak_v=float(item["vmod_peak_v"]),
        )
        for item in payload["frequencies"]
    ]
    return payload["case"], float(payload["v_bias_source_v"]), entries


def interpolate_uniform(time: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    uniform_time = np.linspace(time[0], time[-1], len(time))
    uniform_values = np.interp(uniform_time, time, values)
    return uniform_time, uniform_values


def compute_fft(values: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    freq = np.fft.rfftfreq(values.size, d=dt)
    spec = np.fft.rfft(values)
    amp = 2 * np.abs(spec) / values.size
    if values.size:
        amp[0] = np.abs(spec[0]) / values.size
    return freq, amp


def select_window(df: pd.DataFrame, window: float) -> pd.DataFrame:
    t_max = df["time"].iat[-1]
    start = max(df["time"].iat[0], t_max - window)
    return df[df["time"] >= start].copy()


def analyse_entry(
    entry: ModulationEntry,
    case: str,
    data_root: Path,
    analysis_root: Path,
    figure_root: Path,
    steady_window: float,
    v_bias: float,
) -> dict[str, float | str]:
    candidates = [entry.label, f"f{entry.label}", entry.label.lower(), f"f{entry.label.lower()}"]
    for candidate in candidates:
        potential_dir = data_root / candidate / case
        if potential_dir.exists():
            case_dir = potential_dir
            break
    else:
        raise FileNotFoundError(f"Unable to locate data for label {entry.label} under {data_root}")
    label_key = case_dir.parent.name
    csv_path = case_dir / "JPE_diel_1-4-15_timeseries.csv"
    netlist_path = case_dir / "JPE_diel_1-4-15.net"
    df = pd.read_csv(csv_path)

    steady_df = select_window(df, steady_window)
    if steady_df.empty:
        raise ValueError(f"No samples retained for {entry.label} window={steady_window}")

    diff = steady_df["V(na)"] - steady_df["V(nb)"]
    diff_ac = diff - diff.mean()
    diff_time = steady_df["time"].to_numpy()
    u_time, u_diff = interpolate_uniform(diff_time, diff_ac.to_numpy())
    dt = float(u_time[1] - u_time[0])
    diff_freq, diff_amp = compute_fft(u_diff, dt)
    target_idx = int(np.argmin(np.abs(diff_freq - entry.f_sim_hz)))
    vpp_target = float(2 * diff_amp[target_idx])

    r_rad = extract_radiation_resistance(netlist_path)
    irad = steady_df["I(R_rad)"].to_numpy()
    power = (irad**2) * r_rad
    power_mean_w = float(power.mean())
    power_peak_w = float(power.max())
    power_ac = power - power.mean()
    u_time_p, u_power = interpolate_uniform(diff_time, power_ac)
    _, power_amp = compute_fft(u_power, dt)

    freq_phys = diff_freq * 1e6
    sorted_idx = np.argsort(power_amp[1:])[-5:] + 1 if power_amp.size > 1 else np.array([], dtype=int)
    peaks = [
        {
            "freq_sim_hz": float(diff_freq[idx]),
            "freq_phys_hz": float(freq_phys[idx]),
            "power_w": float(power_amp[idx]),
        }
        for idx in sorted_idx[::-1]
    ]

    summary = {
        "case": case,
        "label": entry.label,
        "f_phys_hz": entry.f_phys_hz,
        "f_sim_hz": entry.f_sim_hz,
        "vmod_peak_v": entry.vmod_peak_v,
        "vpp_at_target_v": vpp_target,
        "fft_bin_frequency_hz": float(diff_freq[target_idx]),
        "fft_bin_frequency_phys_hz": float(freq_phys[target_idx]),
        "time_window_s": steady_window,
        "v_bias_source_v": v_bias,
        "radiated_power_mean_w": power_mean_w,
        "radiated_power_peak_w": power_peak_w,
        "radiation_peaks": peaks,
    }

    analysis_dir = analysis_root / label_key
    figure_dir = figure_root / label_key
    analysis_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    (analysis_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    np.savez(
        analysis_dir / "spectra.npz",
        freq_sim=diff_freq,
        freq_phys=freq_phys,
        diff_amp=diff_amp,
        power_amp=power_amp,
    )

    fig, axes = plt.subplots(2, 1, figsize=(7.5, 7.5))
    axes[0].plot((u_time - u_time[0]) * 1e3, u_diff * 1e3)
    axes[0].set_title(f"{entry.label}: Delta V time-domain (last {steady_window*1e3:.0f} ms)")
    axes[0].set_xlabel("Time [ms]")
    axes[0].set_ylabel("Delta V [mV]")

    axes[1].plot(freq_phys * 1e-9, power_amp * 1e6)
    axes[1].set_title("Radiated Power Spectrum")
    axes[1].set_xlabel("Frequency [GHz]")
    axes[1].set_ylabel("Amplitude [µW]")
    axes[1].set_xlim(0, freq_phys.max() * 1e-9)
    axes[1].grid(True, which="both", linestyle=":", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(figure_dir / "modulation_overview.png", dpi=300)
    plt.close(fig)

    return summary


def main() -> None:
    args = parse_args()
    case, v_bias, entries = load_config(args.config)
    args.analysis_root.mkdir(parents=True, exist_ok=True)
    args.figure_root.mkdir(parents=True, exist_ok=True)

    all_summaries: list[dict[str, float | str]] = []
    for entry in entries:
        summary = analyse_entry(
            entry=entry,
            case=case,
            data_root=args.data_root,
            analysis_root=args.analysis_root,
            figure_root=args.figure_root,
            steady_window=args.steady_window,
            v_bias=v_bias,
        )
        all_summaries.append(summary)

    combined = args.analysis_root / "summary_all.json"
    combined.write_text(json.dumps(all_summaries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
