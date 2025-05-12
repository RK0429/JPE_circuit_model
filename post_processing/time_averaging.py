#!/usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import gridspec

# Constants
FONT_FAMILY = "Times New Roman"
MATH_FONTSET = "cm"
MATH_DEFAULT = "it"
FONT_SIZE = 15
R_RAD = 8.537  # Resistance value for power calculation

# Unit conversion factors for power plotting
UNIT_FACTORS: dict[str, float] = {"W": 1, "mW": 1e3, "uW": 1e6, "nW": 1e9, "pW": 1e12}


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure root logger with standard formatting.
    """
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")


def load_data(filename: str, delimiter: str = r"\s+") -> pd.DataFrame:
    """
    Load data from a text file into a Pandas DataFrame.

    Parameters:
        filename (str): Path to the input text file.
        delimiter (str): Separator pattern or regex for pd.read_csv.

    Returns:
        pd.DataFrame: Loaded DataFrame.
    """
    try:
        if delimiter == r"\s+":
            df = pd.read_csv(filename, sep="\s+")
        else:
            df = pd.read_csv(filename, sep=delimiter)
        logging.info("Data loaded from %s", filename)
        return df
    except Exception:
        logging.exception("Failed to load data from %s", filename)
        raise


def rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename common column patterns to standardized names.
    """
    rename_map = {
        "V(nd)": "V(nt)",
        "V(n10)": "V(nt)",
        "V(n0)": "V(na)",
        "I(R_gnd)": "I(Rgnd)",
        "I(R_rad)": "I(Rrad)",
    }
    return df.rename(columns=rename_map)


def process_data(
    df: pd.DataFrame,
    time_unit: str = "us",
    resample_freq: str = "1N",
    skip_resampling: bool = False,
) -> pd.DataFrame:
    """
    Process the DataFrame by calculating power and resampling on the time index.

    Parameters:
        df (pd.DataFrame): Original DataFrame.
        time_unit (str): Unit for time conversion (e.g. 's', 'us').
        resample_freq (str): Pandas offset alias for resampling frequency.
        skip_resampling (bool): Skip time conversion and resampling.

    Returns:
        pd.DataFrame: Processed DataFrame with power and resampled time.
    """
    df_copy = df.copy()
    # Calculate power if not present
    if "power" not in df_copy.columns and "I(Rrad)" in df_copy.columns:
        df_copy["power"] = df_copy["I(Rrad)"] ** 2 * R_RAD
        logging.info("Calculated 'power' from I(Rrad)")
    elif "power" in df_copy.columns:
        logging.info("'power' column already exists; skipping calculation")
    else:
        logging.warning("No 'I(Rrad)' column found; skipping power calculation")

    # Handle time conversion and resampling
    if skip_resampling:
        logging.info("Skipping time conversion and resampling as requested")
    elif "time" in df_copy.columns:
        try:
            df_copy["time"] = pd.to_datetime(df_copy["time"], unit=time_unit)
            df_copy.set_index("time", inplace=True)
            df_copy = df_copy.resample(resample_freq).mean()
            df_copy.reset_index(inplace=True)
            logging.info("Resampled data every %s", resample_freq)
        except Exception:
            logging.exception("Failed processing 'time' column")
            raise
    else:
        logging.warning(
            "No 'time' column found; skipping time conversion and resampling"
        )

    return df_copy


def configure_plotting() -> None:
    """
    Set global matplotlib plotting parameters.
    """
    plt.rcParams["font.family"] = FONT_FAMILY
    plt.rcParams["mathtext.fontset"] = MATH_FONTSET
    plt.rcParams["mathtext.default"] = MATH_DEFAULT
    plt.rcParams["font.size"] = FONT_SIZE


def plot_dc_sweep(
    df: pd.DataFrame,
    output_unit: str = "uW",
    xlim: Tuple[float, float] = (-0.05, 1.5),
    ylim: Optional[Tuple[float, float]] = None,
    output_path: Optional[str] = None,
) -> None:
    """
    Plot DC sweep results: power vs voltage and current vs voltage.

    Parameters:
        df (pd.DataFrame): Processed DataFrame.
        output_unit (str): Unit for power plotting.
        xlim (Tuple[float,float]): X-axis limits.
        ylim (Optional[Tuple[float,float]]): Y-axis limits.
        output_path (Optional[str]): File path to save the figure.
    """
    required = {"V(nt)", "V(na)", "power", "I(Rgnd)"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(f"Missing columns for DC sweep plot: {missing}")

    if output_unit not in UNIT_FACTORS:
        raise ValueError(f"Invalid output_unit '{output_unit}'")

    configure_plotting()
    fig = plt.figure(figsize=(8, 8))
    spec = gridspec.GridSpec(
        ncols=2, nrows=2, width_ratios=[5, 2], height_ratios=[2, 5]
    )
    ax_top = fig.add_subplot(spec[0])
    ax_side = fig.add_subplot(spec[3])
    ax_body = fig.add_subplot(spec[2], sharex=ax_top, sharey=ax_side)

    delta_v = df["V(nt)"] - df["V(na)"]
    power_scaled = df["power"] * R_RAD * UNIT_FACTORS[output_unit]
    current_scaled = df["I(Rgnd)"] * 1e3  # mA

    ax_top.grid(ls="--")
    ax_top.scatter(delta_v, power_scaled, s=5, c=df["power"], cmap="jet")
    ax_top.set_xlim(xlim)
    ax_top.set_ylabel(f"Power [{output_unit}]")
    ax_top.yaxis.set_label_coords(-0.1, 0.5)

    ax_side.grid(ls="--")
    ax_side.scatter(power_scaled, current_scaled, s=5, c=df["power"], cmap="jet")
    if ylim:
        ax_side.set_ylim(ylim)
    ax_side.set_xlabel(f"Power [{output_unit}]")

    ax_body.grid(ls="--")
    ax_body.scatter(delta_v, current_scaled, s=5, c=df["power"], cmap="jet")
    ax_body.set_xlabel("Voltage [V]")
    ax_body.set_ylabel("Current [mA]")
    ax_body.set_xticks([0, 0.25, 0.5, 0.75, 1, 1.25])
    ax_body.set_yticks([0, 10, 20, 30])
    ax_body.set_xlim(xlim)
    if ylim:
        ax_body.set_ylim(ylim)
    ax_body.yaxis.set_label_coords(-0.1, 0.5)

    fig.tight_layout()
    plt.setp(ax_top.get_xticklabels(), visible=False)
    plt.setp(ax_side.get_yticklabels(), visible=False)
    plt.subplots_adjust(hspace=0.0, wspace=0.0)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path)
        logging.info("DC sweep plot saved to %s", output_path)
    plt.show()


def plot_temperature_time(df: pd.DataFrame, output_path: Optional[str] = None) -> None:
    """
    Plot temperature over time if 'V(t)' column exists.
    """
    if "V(t)" not in df.columns:
        raise KeyError("'V(t)' column not found in DataFrame")
    configure_plotting()
    fig, ax = plt.subplots(figsize=(10, 6))
    # Cast string time values to datetime to avoid categorical unit warnings
    if "time" in df.columns:
        try:
            time_vals = pd.to_datetime(df["time"])
        except Exception:
            time_vals = df["time"]
    else:
        time_vals = df.index
    ax.plot(time_vals, df["V(t)"])
    ax.set_title("Temperature over Time")
    ax.set_xlabel("Time")
    ax.set_ylabel("Temperature [K]")
    ax.grid(True)
    fig.tight_layout()
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path)
        logging.info("Temperature-time plot saved to %s", output_path)
    plt.show()


def save_data(df: pd.DataFrame, output_file: str) -> None:
    """
    Save DataFrame to file with tab delimiter.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, sep="\t", index=True)
    logging.info("Data saved to %s", output_file)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="DC Sweep Time Averaging Analysis")
    parser.add_argument("input_file", help="Input data file path")
    parser.add_argument(
        "--output_file", help="Processed data output path", default=None
    )
    parser.add_argument("--plot_path", help="DC sweep plot file path", default=None)
    parser.add_argument(
        "--tt_plot_path", help="Temperature-time plot file path", default=None
    )
    parser.add_argument(
        "--output_unit",
        choices=list(UNIT_FACTORS.keys()),
        help="Unit for power plot",
        default="uW",
    )
    parser.add_argument(
        "--xlim", nargs=2, type=float, help="X-axis limits", default=[-0.05, 1.5]
    )
    parser.add_argument(
        "--ylim", nargs=2, type=float, help="Y-axis limits", default=None
    )
    parser.add_argument("--delimiter", help="Delimiter for input file", default=r"\s+")
    parser.add_argument("--time_unit", help="Unit for time conversion", default="us")
    parser.add_argument(
        "--resample_freq", help="Resample frequency alias", default="1N"
    )
    parser.add_argument(
        "--skip_resample",
        action="store_true",
        help="Skip time conversion and resampling for already resampled data",
    )
    args = parser.parse_args()

    df = load_data(args.input_file, delimiter=args.delimiter)
    df = rename_columns(df)
    df_processed = process_data(
        df,
        time_unit=args.time_unit,
        resample_freq=args.resample_freq,
        skip_resampling=args.skip_resample,
    )

    if not args.skip_resample:
        output_data_path = args.output_file or str(
            Path(args.input_file).with_suffix("_processed.txt")
        )
        save_data(df_processed, output_data_path)
    else:
        logging.info("Skipping saving processed data as skip_resample is set")

    if args.plot_path:
        plot_dc_sweep(
            df_processed,
            output_unit=args.output_unit,
            xlim=tuple(args.xlim),
            ylim=tuple(args.ylim) if args.ylim else None,
            output_path=args.plot_path,
        )
    if args.tt_plot_path:
        try:
            plot_temperature_time(df_processed, output_path=args.tt_plot_path)
        except KeyError:
            logging.warning("Skipping temperature-time plot: 'V(t)' column not found")


if __name__ == "__main__":
    main()
