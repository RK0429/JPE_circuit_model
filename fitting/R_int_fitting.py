#!/usr/bin/env python
# coding: utf-8

"""
CLI entry point for R_int fitting analysis.
"""

import argparse
import logging

import lmfit as lf  # type: ignore

from fitting.fitting import perform_fitting
from fitting.io import load_data, save_processed_data
from fitting.model import P2T, T2R_th
from fitting.plot import (
    plot_current_temperature,
    plot_current_thermal_resistance,
    plot_thermal_resistance,
    plot_voltage_current,
)
from fitting.processing import process_data
from fitting.solvers import I_int2V_int


def parse_args():
    parser = argparse.ArgumentParser(description="R_int fitting analysis")
    parser.add_argument("input_file", help="Path to input data file")
    parser.add_argument(
        "--output-data",
        "-o",
        default="processed_data.dat",
        help="Path to save processed data",
    )
    parser.add_argument(
        "--output-plot", "-p", default="fit_plots.pdf", help="Path to save primary plot"
    )
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    args = parse_args()

    # Load and process data
    df = load_data(args.input_file)
    df_proc = process_data(df)
    save_processed_data(df_proc, args.output_data)

    # Prepare data arrays
    I_int = df_proc["Current"].to_numpy() * 1e-3
    V_int = df_proc["Reduced Voltage"].to_numpy()

    # Define the model
    model = lf.Model(
        I_int2V_int,
        independent_vars=["I_ints"],
        param_names=["A", "B", "C", "D", "alpha", "beta", "gamma", "T_bath"],
    )

    initial = {
        "A": 140.26315944091203,
        "B": 74.42877017162486,
        "C": 2993.7109475835937,
        "D": 14.966433685735403,
        "alpha": 0.0,
        "beta": 0.07007291353077101,
        "gamma": 7162.304320037531,
        "T_bath": -26.29469185418874,
    }
    bounds = {
        "A": (0.0, None),
        "B": (0.0, 500.0),
        "C": (0.0, 10000.0),
        "D": (0.0, None),
        "alpha": (0.0, 1.2),
        "beta": (0.005, 0.1),
        "gamma": (0.0, 8000.0),
        "T_bath": (-50.0, 40.0),
    }
    vary = {
        "A": True,
        "B": True,
        "C": True,
        "D": True,
        "alpha": False,
        "beta": False,
        "gamma": True,
        "T_bath": True,
    }

    # Create parameters
    params = model.make_params()
    for name in model.param_names:
        p = params[name]
        minb, maxb = bounds[name]
        p.set(value=initial[name], min=minb, max=maxb, vary=vary[name])

    # Perform fitting
    result = perform_fitting(model, params, I_int, V_int)

    # Plot results
    plot_thermal_resistance(result, output=args.output_plot)

    V_cal = I_int2V_int(I_int, **result.best_values)
    plot_voltage_current(I_int, V_int, V_cal, output=args.output_plot)

    P_cal = V_cal * I_int
    T_cal = P2T(P_cal, result.best_values["gamma"], result.best_values["T_bath"])
    plot_current_temperature(I_int, T_cal, output=args.output_plot)

    R_th_cal = T2R_th(
        T_cal,
        result.best_values["alpha"],
        result.best_values["beta"],
        result.best_values["gamma"],
    )
    plot_current_thermal_resistance(I_int, R_th_cal, result, output=args.output_plot)


if __name__ == "__main__":
    main()
