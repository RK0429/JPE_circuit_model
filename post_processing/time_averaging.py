#!/usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import polars as pl
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


def load_data(filename: str, delimiter: str = r"\\s+") -> pl.DataFrame:
    """
    Load data from a text file into a Polars DataFrame.

    Parameters:
        filename (str): Path to the input text file.
        delimiter (str): Separator pattern. Note: Polars' read_csv expects a single char separator.
                         If r"\\s+" (multiple whitespace) is used, this function attempts common fallbacks.

    Returns:
        pl.DataFrame: Loaded DataFrame.
    """
    try:
        if delimiter == r"\\s+":
            # Polars' read_csv separator is a single character.
            # For r"\\s+", pandas' delim_whitespace=True is used.
            # Here, we'll try common separators or log a warning.
            # A more robust solution for true regex \\s+ might involve reading lines and splitting.
            try:
                df = pl.read_csv(
                    filename,
                    separator="	",
                    try_parse_dates=True,
                    infer_schema_length=1000,
                )
                logging.info(
                    "Data loaded from %s using tab separator for '\\\\s+' delimiter.",
                    filename,
                )
            except pl.NoDataError:  # Fallback to space if tab fails or leads to no data
                df = pl.read_csv(
                    filename,
                    separator=" ",
                    try_parse_dates=True,
                    ignore_errors=True,
                    infer_schema_length=1000,
                )
                logging.info(
                    "Data loaded from %s using space separator for '\\\\s+' delimiter (with ignore_errors=True).",
                    filename,
                )
        else:
            df = pl.read_csv(
                filename,
                separator=delimiter,
                try_parse_dates=True,
                infer_schema_length=1000,
            )
            logging.info("Data loaded from %s with delimiter '%s'", filename, delimiter)
        return df
    except Exception:
        logging.exception("Failed to load data from %s", filename)
        raise


def rename_columns(df: pl.DataFrame) -> pl.DataFrame:
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
    # Ignore missing mapping keys by setting strict=False
    return df.rename(rename_map, strict=False)


def process_data(
    df: pl.DataFrame,
    time_unit: str = "us",
    resample_freq: str = "1N",
    skip_resampling: bool = False,
) -> pl.DataFrame:
    """
    Process the DataFrame by calculating power and resampling on the time index.

    Parameters:
        df (pd.DataFrame): Original DataFrame.
        time_unit (str): Unit for time conversion (e.g. 's', 'us', 'ms', 'ns').
        resample_freq (str): Polars duration string for resampling frequency (e.g., "1ns", "1us", "1ms").
                             Original pandas "1N" becomes "1ns".
        skip_resampling (bool): Skip time conversion and resampling.

    Returns:
        pd.DataFrame: Processed DataFrame with power and resampled time.
    """
    df_processed = df.clone()

    # Calculate power if not present
    if "power" not in df_processed.columns and "I(Rrad)" in df_processed.columns:
        df_processed = df_processed.with_columns(
            (pl.col("I(Rrad)") ** 2 * R_RAD).alias("power")
        )
        logging.info("Calculated 'power' from I(Rrad)")
    elif "power" in df_processed.columns:
        logging.info("'power' column already exists; skipping calculation")
    else:
        logging.warning("No 'I(Rrad)' column found; skipping power calculation")

    # Handle time conversion and resampling
    if skip_resampling:
        logging.info("Skipping time conversion and resampling as requested")
    elif "time" in df_processed.columns:
        try:
            # Assuming 'time' column is numeric (Unix timestamp like)
            # Polars time units: 'ns', 'us', 'ms'
            polars_time_unit = time_unit.lower()
            if polars_time_unit not in ["ns", "us", "ms"]:
                logging.warning(
                    "Unsupported time_unit '%s' for Polars pl.from_epoch. Defaulting to 'us'. Supported: ns, us, ms.",
                    polars_time_unit,
                )
                polars_time_unit = "us"

            df_processed = df_processed.with_columns(
                pl.from_epoch(pl.col("time"), time_unit=polars_time_unit).alias("time")
            )

            # Polars resample frequency mapping (e.g., "1N" -> "1ns")
            polars_resample_freq = resample_freq
            if resample_freq.upper().endswith("N"):
                polars_resample_freq = f"{resample_freq[:-1]}ns"

            # Ensure all columns to be aggregated are numeric or can be meaningfully aggregated
            # For simplicity, try to aggregate all. May need specific pl.agg([...]) list
            numeric_cols = [
                col
                for col in df_processed.columns
                if df_processed[col].dtype in pl.NUMERIC_DTYPES and col != "time"
            ]
            aggregations = [pl.mean(col).alias(col) for col in numeric_cols]
            if not aggregations:  # If no numeric columns other than time
                aggregations = [
                    pl.first(col).alias(col)
                    for col in df_processed.columns
                    if col != "time"
                ]

            df_processed = df_processed.group_by_dynamic(
                "time", every=polars_resample_freq
            ).agg(aggregations)
            logging.info("Resampled data every %s", polars_resample_freq)
        except Exception:
            logging.exception("Failed processing 'time' column for resampling")
            raise
    else:
        logging.warning(
            "No 'time' column found; skipping time conversion and resampling"
        )

    return df_processed


def configure_plotting() -> None:
    """
    Set global matplotlib plotting parameters.
    """
    plt.rcParams["font.family"] = FONT_FAMILY
    plt.rcParams["mathtext.fontset"] = MATH_FONTSET
    plt.rcParams["mathtext.default"] = MATH_DEFAULT
    plt.rcParams["font.size"] = FONT_SIZE


def plot_dc_sweep(
    df: pl.DataFrame,
    output_unit: str = "uW",
    xlim: Tuple[float, float] = (-0.05, 1.5),
    ylim: Optional[Tuple[float, float]] = None,
    output_path: Optional[str] = None,
) -> None:
    """
    Plot DC sweep results: power vs voltage and current vs voltage.

    Parameters:
        df (pl.DataFrame): Processed DataFrame.
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

    delta_v_series = df.get_column("V(nt)") - df.get_column("V(na)")
    # Assuming 'power' column is already in Watts (I^2 * R_RAD)
    power_scaled_series = df.get_column("power") * UNIT_FACTORS[output_unit]
    current_scaled_series = df.get_column("I(Rgnd)") * 1e3  # mA
    color_by_series = df.get_column("power")  # Or another relevant column for color

    ax_top.grid(ls="--")
    ax_top.scatter(
        delta_v_series, power_scaled_series, s=5, c=color_by_series, cmap="jet"
    )
    ax_top.set_xlim(xlim)
    ax_top.set_ylabel(f"Power [{output_unit}]")
    ax_top.yaxis.set_label_coords(-0.1, 0.5)

    ax_side.grid(ls="--")
    ax_side.scatter(
        power_scaled_series, current_scaled_series, s=5, c=color_by_series, cmap="jet"
    )
    if ylim:
        ax_side.set_ylim(ylim)
    ax_side.set_xlabel(f"Power [{output_unit}]")

    ax_body.grid(ls="--")
    ax_body.scatter(
        delta_v_series, current_scaled_series, s=5, c=color_by_series, cmap="jet"
    )
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


def plot_temperature_time(df: pl.DataFrame, output_path: Optional[str] = None) -> None:
    """
    Plot temperature (represented by 'V(t)') over time.
    Assumes 'time' column is Polars Datetime after processing.
    """
    if "time" not in df.columns:
        raise KeyError("'time' column not found in DataFrame for temperature plot.")
    if "V(t)" not in df.columns:
        raise KeyError("'V(t)' column not found in DataFrame for temperature plot.")

    # Assuming 'time' is pl.Datetime, get epoch for plotting if needed, or let matplotlib handle datetime
    # For x-axis label "Time [ns]", convert to nanoseconds from epoch or relative
    time_col = df.get_column("time")
    if time_col.len() > 0 and isinstance(
        time_col[0], int
    ):  # if it's already numeric (e.g. from skip_resample)
        x_values = time_col * 1e9  # Assuming it's in seconds, convert to ns
    elif time_col.dtype == pl.Datetime:
        x_values = time_col.dt.epoch(time_unit="ns")
    else:  # Fallback for other types or if it's already a duration in ns
        try:
            x_values = time_col.dt.total_nanoseconds()
        except AttributeError:  # Not a duration, try to use as is
            x_values = time_col
            logging.warning(
                "Time column for temperature plot is not Datetime or Duration. Plotting as is."
            )

    y_values = df.get_column("V(t)")

    configure_plotting()
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x_values, y_values)  # Matplotlib can often handle Polars Series directly
    ax.set_title("Temperature over Time")
    ax.set_xlabel("Time [ns]")  # Assuming x_values are nanoseconds
    ax.set_ylabel("Temperature [K]")
    ax.grid(True)
    fig.tight_layout()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path)
        logging.info("Temperature-time plot saved to %s", output_path)
    plt.show()


def save_data(df: pl.DataFrame, output_file: str) -> None:
    """
    Save DataFrame to file with tab delimiter.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(output_path, separator="\\t")
    logging.info("Data saved to %s", output_file)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="DC Sweep Time Averaging Analysis with Polars"
    )
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
    parser.add_argument("--delimiter", help="Delimiter for input file", default=r"\\s+")
    parser.add_argument(
        "--time_unit", help="Unit for numeric time col (us, ns, ms)", default="us"
    )
    parser.add_argument(
        "--resample_freq",
        help="Resample frequency (e.g., 1ns, 10us, 1ms, 1N for pandas compat)",
        default="1N",
    )
    parser.add_argument(
        "--skip_resample",
        action="store_true",
        help="Skip time conversion and resampling for already resampled data",
    )
    args = parser.parse_args()

    df_initial = load_data(args.input_file, delimiter=args.delimiter)
    df_renamed = rename_columns(df_initial)
    df_processed = process_data(
        df_renamed,
        time_unit=args.time_unit,
        resample_freq=args.resample_freq,
        skip_resampling=args.skip_resample,
    )

    if not args.skip_resample and args.output_file:
        save_data(df_processed, args.output_file)
    elif not args.skip_resample:
        # Default output file if not specified and not skipping resample
        default_output_path = str(
            Path(args.input_file).with_suffix("_processed_polars.txt")
        )
        save_data(df_processed, default_output_path)
        logging.info(
            "Processed data saved to default location: %s", default_output_path
        )
    else:
        logging.info(
            "Skipping saving processed data as skip_resample is set or no output_file provided."
        )

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
        except KeyError as e:
            logging.warning("Skipping temperature-time plot: %s", e)
        except Exception as e:
            logging.error(
                "Failed to generate temperature-time plot: %s", e, exc_info=True
            )


if __name__ == "__main__":
    main()
