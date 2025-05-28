#!/usr/bin/env python
# coding: utf-8

"""CLI entry point for antenna parameter fitting analysis."""

import argparse
import logging

import numpy as np

from ..utils.fitting import perform_fitting, setup_fitting_model
from ..utils.io import load_data, load_txt_data
from ..utils.plot import plot_complex_figure, plot_fitting_results, plot_txt_data
from .model import constants, output_power


def parse_args():
    parser = argparse.ArgumentParser(description="Antenna parameter fitting analysis")
    parser.add_argument(
        "--bo-file", required=True, help="Path to Bolometer Output data file"
    )
    parser.add_argument("--ive-file", required=True, help="Path to IVE data file")
    parser.add_argument("--txt-file", required=True, help="Path to text data file")
    parser.add_argument("--fig6", default="Fig6.pdf", help="Path to save fit plot")
    parser.add_argument(
        "--fig10", default="Fig10.pdf", help="Path to save complex figure"
    )
    parser.add_argument(
        "--epsilon-fit", type=float, default=15000, help="Scaling factor for fitting"
    )
    parser.add_argument(
        "--epsilon-comp",
        type=float,
        default=5000,
        help="Scaling factor for complex figure",
    )
    parser.add_argument(
        "--Rrad", type=float, default=23, help="Scaling factor Rrad for text data"
    )
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    # Load experimental data
    bolometer_df, ive_df = load_data(args.bo_file, args.ive_file)
    R_int = bolometer_df["Resistance"].to_numpy()
    BO_exp = bolometer_df["Bolometer Output"].to_numpy() * 1e-3
    V = bolometer_df["Reduced Voltage"].to_numpy()

    # Load macro data
    R_macro = ive_df["Resistance"].to_numpy()
    V_macro = ive_df["Reduced Voltage"].to_numpy()
    I_macro = ive_df["Current"].to_numpy()
    BO_macro = ive_df["Bolometer Detection"].to_numpy() * 1e-3

    # Define parameter dictionaries
    par_val = {
        "ratio": 1,
        "R": 55.04,
        "L": 3.27e-10 * constants.e * 2 / constants.hbar / 808,
        "C": 2.748e-16 * constants.e * 2 / constants.hbar / 808,
        "C_intt": 4.339e-11 * constants.e * 2 / constants.hbar / 808,
        "C_intb": 3.222e-12 * constants.e * 2 / constants.hbar / 808,
        "R_loss_t": 0.202,
        "R_loss_b": 2.922,
        "Ic": 18e-3,
        "R_ext": 1.15,
        "L_ext": 10e-9 * constants.e * 2 / constants.hbar / 808,
        "R_gnd": 7.20,
        "R_mid": 8.29,
        "R_FG": 50,
        "L_FG": 10e-9 * constants.e * 2 / constants.hbar / 808,
        "N": 848,
    }
    par_min = {key: 0.0 for key in par_val}
    par_min["N"] = 1
    par_max = {key: np.inf for key in par_val}
    par_vary = {
        "ratio": False,
        "R": True,
        "L": True,
        "C": True,
        "C_intt": False,
        "C_intb": False,
        "R_loss_t": False,
        "R_loss_b": False,
        "Ic": False,
        "R_ext": False,
        "L_ext": False,
        "R_gnd": False,
        "R_mid": False,
        "R_FG": False,
        "L_FG": False,
        "N": False,
    }

    # Setup and perform fitting
    model = setup_fitting_model(output_power)
    params = model.make_params()
    for name in model.param_names:
        params[name].set(
            value=par_val[name],
            min=par_min[name],
            max=par_max[name],
            vary=par_vary[name],
        )

    sb_scaled = BO_exp / constants.Sb * args.epsilon_fit
    result = perform_fitting(
        model=model,
        params=params,
        V=V,
        R_int=R_int,
        data=sb_scaled,
        weights=BO_exp,
    )

    # Calculate and plot fitting results
    RP_cal = output_power(
        V=V,
        R_int=R_int,
        ratio=result.best_values["ratio"],
        R=result.best_values["R"],
        L=result.best_values["L"] * 2,
        C=result.best_values["C"] / 2.1,
        C_intt=result.best_values["C_intt"],
        C_intb=result.best_values["C_intb"],
        R_loss_t=result.best_values["R_loss_t"],
        R_loss_b=result.best_values["R_loss_b"],
        Ic=result.best_values["Ic"],
        R_ext=result.best_values["R_ext"],
        L_ext=result.best_values["L_ext"],
        R_gnd=result.best_values["R_gnd"],
        R_mid=result.best_values["R_mid"],
        R_FG=result.best_values["R_FG"],
        L_FG=result.best_values["L_FG"],
        N=result.best_values["N"],
    )
    plot_fitting_results(
        V=V,
        BO_exp_scaled=sb_scaled,
        RP_cal=RP_cal,
        fig_path=args.fig6,
    )

    # Plot macro data fitting
    RP_cal_macro = output_power(
        V=V_macro,
        R_int=R_macro,
        ratio=result.best_values["ratio"],
        R=result.best_values["R"],
        L=result.best_values["L"],
        C=result.best_values["C"],
        C_intt=result.best_values["C_intt"],
        C_intb=result.best_values["C_intb"],
        R_loss_t=result.best_values["R_loss_t"],
        R_loss_b=result.best_values["R_loss_b"],
        Ic=result.best_values["Ic"],
        R_ext=result.best_values["R_ext"],
        L_ext=result.best_values["L_ext"],
        R_gnd=result.best_values["R_gnd"],
        R_mid=result.best_values["R_mid"],
        R_FG=result.best_values["R_FG"],
        L_FG=result.best_values["L_FG"],
        N=result.best_values["N"],
    )
    plot_fitting_results(
        V=V_macro,
        BO_exp_scaled=BO_macro / constants.Sb * args.epsilon_fit,
        RP_cal=RP_cal_macro,
        fig_path=args.fig6,
    )

    # Load and plot text data
    dc_sweep_df = load_txt_data(args.txt_file)
    plot_txt_data(
        df=dc_sweep_df,
        fig_path=args.fig10,
        epsilon=args.epsilon_comp,
        Rrad=args.Rrad,
    )

    # Complex figure combining experimental and text data
    V_cal_txt = (dc_sweep_df["V(nt)"] - dc_sweep_df["V(na)"]).to_numpy()
    I_cal_txt = (-dc_sweep_df["I(Rfg)"] * 1e3).to_numpy()
    RP_cal_txt = (dc_sweep_df["power"] * args.Rrad).to_numpy()
    plot_complex_figure(
        V_exp=V_macro,
        I_exp=I_macro,
        RP_exp=BO_macro,
        V_cal=V_cal_txt,
        I_cal=I_cal_txt,
        RP_cal=RP_cal_txt,
        fig_path=args.fig10,
        constants=constants,
        epsilon=args.epsilon_comp,
        show_exp=True,
    )


if __name__ == "__main__":
    main()
