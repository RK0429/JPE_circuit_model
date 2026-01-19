#!/usr/bin/env python3
"""Analyse high-frequency modulation runs for the dielectric 1-4-15 case."""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from matplotlib.axes import Axes

SCRIPT_ROOT = Path(__file__).resolve().parent
_CASE_SPEC = importlib.util.spec_from_file_location(
    "_dielectric_case", SCRIPT_ROOT / "visualize_dielectric_case.py"
)
if _CASE_SPEC is None or _CASE_SPEC.loader is None:
    raise RuntimeError("Failed to load visualize_dielectric_case module")  # noqa: TRY003

_case_module = importlib.util.module_from_spec(_CASE_SPEC)
_CASE_SPEC.loader.exec_module(_case_module)
extract_radiation_resistance = cast(
    Callable[[Path], float],
    _case_module.extract_radiation_resistance,
)


@dataclass
class ModulationEntry:
    label: str
    f_phys_hz: float
    f_sim_hz: float
    vmod_peak_v: float


FloatArray = npt.NDArray[np.float64]
MIN_INTERPOLATED_SAMPLES = 2


@dataclass
class DiffMetrics:
    freq_sim_hz: FloatArray
    freq_phys_hz: FloatArray
    amplitudes: FloatArray
    vpp_target_v: float
    dt: float
    time: FloatArray
    diff_series: FloatArray
    target_idx: int


@dataclass
class PowerMetrics:
    mean_w: float
    peak_w: float
    amplitudes_w: FloatArray


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


def interpolate_uniform(time: FloatArray, values: FloatArray) -> tuple[FloatArray, FloatArray]:
    uniform_time = np.linspace(time[0], time[-1], len(time), dtype=float)
    uniform_values = np.asarray(np.interp(uniform_time, time, values), dtype=float)
    return uniform_time, uniform_values


def compute_fft(values: FloatArray, dt: float) -> tuple[FloatArray, FloatArray]:
    freq = np.asarray(np.fft.rfftfreq(values.size, d=dt), dtype=float)
    spec = np.fft.rfft(values)
    amp = np.asarray(2 * np.abs(spec) / values.size, dtype=float)
    if values.size:
        amp[0] = np.abs(spec[0]) / values.size
    return freq, amp


def select_window(df: pd.DataFrame, window: float) -> pd.DataFrame:
    t_max = df["time"].iat[-1]
    start = max(df["time"].iat[0], t_max - window)
    return df[df["time"] >= start].copy()


def _resolve_case_dir(entry: ModulationEntry, case: str, data_root: Path) -> Path:
    candidates = [entry.label, f"f{entry.label}", entry.label.lower(), f"f{entry.label.lower()}"]
    for candidate in candidates:
        potential_dir = data_root / candidate / case
        if potential_dir.exists():
            return potential_dir
    msg = f"Unable to locate data for label {entry.label} under {data_root}"
    raise FileNotFoundError(msg)


def _compute_diff_metrics(
    steady_df: pd.DataFrame, entry: ModulationEntry, steady_window: float
) -> DiffMetrics:
    diff = steady_df["V(na)"] - steady_df["V(nb)"]
    diff_ac = diff - diff.mean()
    diff_time = steady_df["time"].to_numpy(dtype=float)
    u_time, u_diff = interpolate_uniform(diff_time, diff_ac.to_numpy(dtype=float))
    if u_time.size < MIN_INTERPOLATED_SAMPLES:
        msg = f"Insufficient samples retained for {entry.label} window={steady_window}"
        raise ValueError(msg)

    dt = float(u_time[1] - u_time[0])
    diff_freq, diff_amp = compute_fft(u_diff, dt)
    target_idx = int(np.argmin(np.abs(diff_freq - entry.f_sim_hz))) if diff_amp.size else 0
    vpp_target = float(2 * diff_amp[target_idx]) if diff_amp.size else 0.0
    freq_phys = diff_freq * 1e6

    return DiffMetrics(
        freq_sim_hz=diff_freq,
        freq_phys_hz=freq_phys,
        amplitudes=diff_amp,
        vpp_target_v=vpp_target,
        dt=dt,
        time=u_time,
        diff_series=u_diff,
        target_idx=target_idx,
    )


def _compute_power_metrics(
    steady_df: pd.DataFrame, dt: float, netlist_path: Path
) -> PowerMetrics:
    r_rad = extract_radiation_resistance(netlist_path)
    irad = steady_df["I(R_rad)"].to_numpy(dtype=float)
    power = (irad**2) * r_rad
    power_mean_w = float(power.mean())
    power_peak_w = float(power.max())
    power_ac = power - power.mean()
    _, power_amp = compute_fft(power_ac, dt)
    return PowerMetrics(mean_w=power_mean_w, peak_w=power_peak_w, amplitudes_w=power_amp)


def _select_power_peaks(
    diff_freq: FloatArray, power_amp: FloatArray, freq_phys: FloatArray
) -> list[dict[str, float]]:
    if power_amp.size <= 1:
        return []
    sorted_idx = np.argsort(power_amp[1:])[-5:] + 1
    return [
        {
            "freq_sim_hz": float(diff_freq[idx]),
            "freq_phys_hz": float(freq_phys[idx]),
            "power_w": float(power_amp[idx]),
        }
        for idx in sorted_idx[::-1]
    ]


def analyse_entry(
    entry: ModulationEntry,
    case: str,
    data_root: Path,
    analysis_root: Path,
    figure_root: Path,
    steady_window: float,
    v_bias: float,
) -> dict[str, float | str | list[dict[str, float]]]:
    case_dir = _resolve_case_dir(entry, case, data_root)
    label_key = case_dir.parent.name
    csv_path = case_dir / "JPE_diel_1-4-15_timeseries.csv"
    netlist_path = case_dir / "JPE_diel_1-4-15.net"
    df = pd.read_csv(csv_path)

    steady_df = select_window(df, steady_window)
    if steady_df.empty:
        msg = f"No samples retained for {entry.label} window={steady_window}"
        raise ValueError(msg)

    diff_metrics = _compute_diff_metrics(steady_df, entry, steady_window)
    power_metrics = _compute_power_metrics(steady_df, diff_metrics.dt, netlist_path)
    peaks = _select_power_peaks(
        diff_metrics.freq_sim_hz, power_metrics.amplitudes_w, diff_metrics.freq_phys_hz
    )

    summary = {
        "case": case,
        "label": entry.label,
        "f_phys_hz": entry.f_phys_hz,
        "f_sim_hz": entry.f_sim_hz,
        "vmod_peak_v": entry.vmod_peak_v,
        "vpp_at_target_v": diff_metrics.vpp_target_v,
        "fft_bin_frequency_hz": float(diff_metrics.freq_sim_hz[diff_metrics.target_idx]),
        "fft_bin_frequency_phys_hz": float(
            diff_metrics.freq_phys_hz[diff_metrics.target_idx]
        ),
        "time_window_s": steady_window,
        "v_bias_source_v": v_bias,
        "radiated_power_mean_w": power_metrics.mean_w,
        "radiated_power_peak_w": power_metrics.peak_w,
        "radiation_peaks": peaks,
    }

    analysis_dir = analysis_root / label_key
    figure_dir = figure_root / label_key
    analysis_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    (analysis_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    np.savez(
        analysis_dir / "spectra.npz",
        freq_sim=diff_metrics.freq_sim_hz,
        freq_phys=diff_metrics.freq_phys_hz,
        diff_amp=diff_metrics.amplitudes,
        power_amp=power_metrics.amplitudes_w,
    )

    fig, axes_array = plt.subplots(2, 1, figsize=(7.5, 7.5))
    axes_array = cast(np.ndarray[Any], axes_array)
    ax_time = cast(Axes, axes_array[0])
    ax_power = cast(Axes, axes_array[1])

    ax_time.plot((diff_metrics.time - diff_metrics.time[0]) * 1e3, diff_metrics.diff_series * 1e3)
    ax_time.set_title(
        f"{entry.label}: Delta V time-domain (last {steady_window * 1e3:.0f} ms)"
    )
    ax_time.set_xlabel("Time [ms]")
    ax_time.set_ylabel("Delta V [mV]")

    ax_power.plot(diff_metrics.freq_phys_hz * 1e-9, power_metrics.amplitudes_w * 1e6)
    ax_power.set_title("Radiated Power Spectrum")
    ax_power.set_xlabel("Frequency [GHz]")
    ax_power.set_ylabel("Amplitude [uW]")
    ax_power.set_xlim(0, diff_metrics.freq_phys_hz.max() * 1e-9)
    ax_power.grid(True, which="both", linestyle=":", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(figure_dir / "modulation_overview.png", dpi=300)
    plt.close(fig)

    return summary


def main() -> None:
    args = parse_args()
    case, v_bias, entries = load_config(args.config)
    args.analysis_root.mkdir(parents=True, exist_ok=True)
    args.figure_root.mkdir(parents=True, exist_ok=True)

    all_summaries: list[dict[str, float | str | list[dict[str, float]]]] = []
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
