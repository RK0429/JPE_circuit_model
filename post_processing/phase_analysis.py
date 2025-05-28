#!/usr/bin/env python3
# coding: utf-8


from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Constants
FONT_FAMILY = "Times New Roman"
MATH_FONTSET = "cm"
MATH_DEFAULT = "it"
FONT_SIZE = 15
R_RAD = 20  # Resistance value for power calculation

# File Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PLOTS_DIR = PROJECT_ROOT / "plots"

BASE_DIR = DATA_DIR
FILENAME_IN = BASE_DIR / "dc_sweep_JPE_phase_original.txt"
FILENAME_OUT = BASE_DIR / "dc_sweep_JPE_phase_processed.txt"
PLOT_PATH = PLOTS_DIR / "dc_sweep_JPE_phase.pdf"


def load_data(file_path: str) -> pd.DataFrame:
    """Load data from a whitespace-delimited text file into a Pandas DataFrame.

    Parameters:     file_path (str): Path to the input text file.

    Returns:     pd.DataFrame: Loaded DataFrame.

    Raises:     FileNotFoundError: If the file does not exist.
    pd.errors.ParserError: If there's an error parsing the file.
    """
    try:
        df = pd.read_csv(file_path, sep=r"\s+")  # type: ignore[call-overload]
        logging.info("Data loaded successfully from %s.", file_path)
        logging.debug("DataFrame columns: %s", df.columns.tolist())
        return df
    except FileNotFoundError:
        logging.error("File not found: %s", file_path)
        raise
    except pd.errors.ParserError as e:
        logging.error("Error parsing file %s: %s", file_path, e)
        raise
    except Exception as e:
        logging.error("Unexpected error loading data from %s: %s", file_path, e)
        raise


def process_data(df: pd.DataFrame, resample_interval: str = "100us") -> pd.DataFrame:
    """Process the DataFrame by computing phase differences, power, and resampling.

    Parameters:     df (pd.DataFrame): Original DataFrame.     resample_interval (str):
    Resample interval for data (pandas offset alias).

    Returns:     pd.DataFrame: Processed and resampled DataFrame.

    Raises:     KeyError: If required columns are missing.
    """
    df_processed = df.copy()

    # Verify required columns
    required_columns = ["time", "V(nphase1)", "V(nphase2)", "I(Rrad)"]
    missing_columns = [
        col for col in required_columns if col not in df_processed.columns
    ]
    if missing_columns:
        logging.error("Missing columns in data: %s", missing_columns)
        raise KeyError(f"Missing columns: {missing_columns}")

    # Compute differences in phases
    df_processed["dphase1"] = df_processed["V(nphase1)"].diff()
    df_processed["dphase2"] = df_processed["V(nphase2)"].diff()
    logging.info(
        "Computed 'dphase1' and 'dphase2' as differences of V(nphase1) and V(nphase2)."
    )

    # Compute power
    df_processed["power"] = df_processed["I(Rrad)"] ** 2
    logging.info("Computed 'power' as square of 'I(Rrad)'.")

    # Convert 'time' to datetime
    try:
        df_processed["time"] = pd.to_datetime(df_processed["time"], unit="s")
        logging.info("Converted 'time' column to datetime.")
    except (ValueError, TypeError) as e:
        logging.error("Error converting 'time' to datetime: %s", e)
        raise

    # Set 'time' as index
    df_processed.set_index("time", inplace=True)
    logging.info("Set 'time' as index.")

    # Resample data every 100 microseconds (100U)
    try:
        df_resampled = df_processed.resample(resample_interval).mean()
        logging.info("Resampled data every %s and took mean.", resample_interval)
    except (ValueError, TypeError, KeyError) as e:
        logging.error("Error during resampling: %s", e)
        raise

    # Reset index
    df_resampled.reset_index(inplace=True)
    logging.info("Reset index after resampling.")

    # Optional: Check 'time' dtype
    logging.debug(
        "'time' column dtype after processing: %s", df_resampled["time"].dtype
    )

    return df_resampled


def plot_data(
    df_resampled: pd.DataFrame,
    plot_path: Optional[str] = None,
    xlim: Optional[tuple[float, float]] = None,
    radius: float = R_RAD,
) -> Figure:
    """Plot Delta Phase and Power over Time using twin y-axes.

    Parameters:     df_resampled (pd.DataFrame): Processed DataFrame.     plot_path
    (Optional[str]): Path to save the plot. If None, plot is not saved.     xlim
    (Optional[tuple[float, float]]): Two-element tuple specifying the x-axis limits,
    e.g. (xmin, xmax).     radius (float): Resistance value for power calculation.

    Returns:     matplotlib.figure.Figure: The created figure.

    Raises:     KeyError: If required columns are missing.
    """
    required_columns = ["time", "V(nphase1)", "V(nphase2)", "power"]
    missing_columns = [
        col for col in required_columns if col not in df_resampled.columns
    ]
    if missing_columns:
        logging.error("Missing columns for plotting: %s", missing_columns)
        raise KeyError(f"Missing columns: {missing_columns}")

    # Configure plotting parameters
    plt.rcParams["font.family"] = FONT_FAMILY
    plt.rcParams["mathtext.fontset"] = MATH_FONTSET
    plt.rcParams["mathtext.default"] = MATH_DEFAULT
    plt.rcParams["font.size"] = FONT_SIZE
    logging.info("Configured matplotlib plotting parameters.")

    # Create figure and axes
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot Delta Phase on ax1
    start_time = df_resampled["time"].iloc[0]
    delta_time = (
        df_resampled["time"] - start_time
    ).dt.total_seconds()  # Convert to microseconds
    delta_phi = (df_resampled["V(nphase2)"] - df_resampled["V(nphase1)"]) % (2 * np.pi)
    ln1 = ax1.plot(
        delta_time, delta_phi, color="blue", label=r"$\Delta\varphi$", linewidth=1
    )

    ax1.set_xlabel(r"Time [$\mu$s]")
    ax1.set_ylabel(r"$\Delta\varphi$ [rad]")
    ax1.set_yticks([0, np.pi, 2 * np.pi])
    ax1.set_yticklabels(["0", r"$\pi$", r"$2\pi$"])
    ax1.grid(True, linestyle="--", linewidth=0.5)

    # Create a second y-axis for Power
    ax2 = ax1.twinx()
    power = df_resampled["power"] * radius * 1e6  # Scale power
    ln2 = ax2.plot(
        delta_time, power, color="orange", label=r"$P_{\rm rad}$", linewidth=1
    )

    ax2.set_ylabel(r"$P_{\rm rad}$ [$\mu$W]")
    ax2.grid(False)  # Remove grid for second axis

    # Combine legends from both axes
    lns = ln1 + ln2
    labels = [str(line.get_label()) for line in lns]
    ax1.legend(lns, labels, loc="upper left")

    # If xlim is provided, apply it
    if xlim is not None:
        ax1.set_xlim(xlim)

    # Adjust layout
    fig.tight_layout()

    # Save plot if path is provided
    if plot_path:
        try:
            fig.savefig(plot_path)
            logging.info("Plot saved to %s.", plot_path)
        except OSError as e:
            logging.error("Error saving plot to %s: %s", plot_path, e)

    # Show plot
    plt.show()

    return fig


def save_data(df: pd.DataFrame, file_path: str) -> None:
    """Save the DataFrame to a text file with tab delimiter.

    Parameters:     df (pd.DataFrame): DataFrame to save.     file_path (str): Path to
    save the DataFrame.
    """
    try:
        df.to_csv(file_path, sep="\t", index=True)
        logging.info("Processed data saved to %s.", file_path)
    except OSError as e:
        logging.error("Error saving data to %s: %s", file_path, e)
        raise


# Entry point
def main() -> None:
    parser = argparse.ArgumentParser(description="DC Sweep Phase and Power Analysis")
    parser.add_argument(
        "input_file",
        help="Path to input data file",
        default=str(FILENAME_IN),
        nargs="?",
    )
    parser.add_argument(
        "output_file",
        help="Path to save processed data",
        default=str(FILENAME_OUT),
        nargs="?",
    )
    parser.add_argument(
        "--plot-file", help="Path to save the plot", default=str(PLOT_PATH)
    )
    parser.add_argument(
        "--resample-interval",
        help="Resample interval for data (pandas offset alias)",
        default="100us",
    )
    parser.add_argument(
        "--radius",
        type=float,
        help="Resistance value for power calculation",
        default=R_RAD,
    )
    args = parser.parse_args()

    df = load_data(args.input_file)
    df_resampled = process_data(df, resample_interval=args.resample_interval)
    save_data(df_resampled, args.output_file)
    plot_data(df_resampled, plot_path=args.plot_file, radius=args.radius)


if __name__ == "__main__":
    main()
