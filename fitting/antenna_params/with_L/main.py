#!/usr/bin/env python

"""CLI entry point for antenna parameter fitting analysis."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import lmfit as lf
import numpy as np
from numpy.typing import NDArray

from ..utils.fitting import perform_fitting, setup_fitting_model
from ..utils.io import load_data, load_txt_data
from ..utils.plot import (
    ComplexFigureData,
    FittingSeries,
    plot_complex_figure,
    plot_fitting_results,
    plot_txt_data,
)
from .model import GAMMA, constants, output_power

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class ExperimentalDataset:
    """Bolometer measurements gathered from experiments."""

    resistance: FloatArray
    bolometer_output: FloatArray
    voltage: FloatArray


@dataclass(frozen=True)
class MacroDataset:
    """Macroscopic measurements collected alongside the bolometer data."""

    resistance: FloatArray
    voltage: FloatArray
    current: FloatArray
    bolometer_detection: FloatArray


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Antenna parameter fitting analysis")
    parser.add_argument("--bo-file", required=True, help="Path to Bolometer Output data file")
    parser.add_argument("--ive-file", required=True, help="Path to IVE data file")
    parser.add_argument("--txt-file", required=True, help="Path to text data file")
    parser.add_argument("--fig6", default="Fig6.pdf", help="Path to save fit plot")
    parser.add_argument("--fig10", default="Fig10.pdf", help="Path to save complex figure")
    parser.add_argument("--epsilon-fit", type=float, default=15_000.0, help="Scaling factor for fitting")
    parser.add_argument(
        "--epsilon-comp",
        type=float,
        default=5_000.0,
        help="Scaling factor for complex figure",
    )
    parser.add_argument("--rrad", type=float, default=23.0, help="Radiation resistance for text data")
    parser.add_argument(
        "--L-int-t",
        type=float,
        default=1e-9 * GAMMA,
        help="Top internal inductance [H]",
    )
    parser.add_argument(
        "--L-int-b",
        type=float,
        default=1e-9 * GAMMA,
        help="Bottom internal inductance [H]",
    )
    return parser.parse_args(argv)


def _load_datasets(args: argparse.Namespace) -> tuple[ExperimentalDataset, MacroDataset]:
    bolometer_df, ive_df = load_data(args.bo_file, args.ive_file)
    experimental = ExperimentalDataset(
        resistance=bolometer_df["Resistance"].to_numpy(),
        bolometer_output=bolometer_df["Bolometer Output"].to_numpy() * 1e-3,
        voltage=bolometer_df["Reduced Voltage"].to_numpy(),
    )
    macro = MacroDataset(
        resistance=ive_df["Resistance"].to_numpy(),
        voltage=ive_df["Reduced Voltage"].to_numpy(),
        current=ive_df["Current"].to_numpy(),
        bolometer_detection=ive_df["Bolometer Detection"].to_numpy() * 1e-3,
    )
    return experimental, macro


def _initial_parameter_values(args: argparse.Namespace) -> dict[str, float]:
    scale = constants.e * 2.0 / constants.hbar / 808.0
    return {
        "ratio": 1.0,
        "R": 55.04,
        "L": 3.27e-10 * scale,
        "C": 2.748e-16 * scale,
        "C_intt": 4.339e-11 * scale,
        "C_intb": 3.222e-12 * scale,
        "R_loss_t": 0.202,
        "R_loss_b": 2.922,
        "Ic": 18e-3,
        "R_ext": 1.15,
        "L_ext": 10e-9 * scale,
        "R_gnd": 7.20,
        "R_mid": 8.29,
        "R_FG": 50.0,
        "L_FG": 10e-9 * scale,
        "N": 848.0,
        "L_int_t": args.L_int_t,
        "L_int_b": args.L_int_b,
    }


def _parameter_bounds(initial: Mapping[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    minimums = dict.fromkeys(initial, 0.0)
    minimums["N"] = 1.0
    maximums = dict.fromkeys(initial, float(np.inf))
    return minimums, maximums


def _parameter_activity() -> dict[str, bool]:
    return {
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
        "L_int_t": False,
        "L_int_b": False,
    }


def _configure_parameters(
    model: lf.Model,
    initial: Mapping[str, float],
    lower: Mapping[str, float],
    upper: Mapping[str, float],
    vary: Mapping[str, bool],
) -> lf.Parameters:
    params = model.make_params()
    for name in model.param_names:
        parameter = params[name]
        parameter.set(
            value=initial[name],
            min=lower[name],
            max=upper[name],
            vary=vary[name],
        )
    return params


def _evaluate_power(
    voltage: FloatArray,
    resistance: FloatArray,
    values: Mapping[str, float],
    *,
    inductance_scale: float = 1.0,
    capacitance_scale: float = 1.0,
) -> FloatArray:
    stack_count = round(float(values["N"]))
    return output_power(
        voltage=voltage,
        internal_resistance=resistance,
        ratio=float(values["ratio"]),
        R=float(values["R"]),
        L=float(values["L"]) * inductance_scale,
        C=float(values["C"]) * capacitance_scale,
        C_intt=float(values["C_intt"]),
        C_intb=float(values["C_intb"]),
        R_loss_t=float(values["R_loss_t"]),
        R_loss_b=float(values["R_loss_b"]),
        Ic=float(values["Ic"]),
        R_ext=float(values["R_ext"]),
        L_ext=float(values["L_ext"]),
        R_gnd=float(values["R_gnd"]),
        R_mid=float(values["R_mid"]),
        R_FG=float(values["R_FG"]),
        L_FG=float(values["L_FG"]),
        N=stack_count,
        L_int_t=float(values["L_int_t"]),
        L_int_b=float(values["L_int_b"]),
    )


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    experimental, macro = _load_datasets(args)
    initial = _initial_parameter_values(args)
    lower, upper = _parameter_bounds(initial)
    vary = _parameter_activity()

    model = setup_fitting_model(output_power)
    params = _configure_parameters(model, initial, lower, upper, vary)

    scaled_power = experimental.bolometer_output / constants.Sb * args.epsilon_fit
    result = perform_fitting(
        model=model,
        params=params,
        voltage=experimental.voltage,
        internal_resistance=experimental.resistance,
        measured_power=scaled_power,
        weights=experimental.bolometer_output,
    )

    fitted_power = _evaluate_power(
        experimental.voltage,
        experimental.resistance,
        result.best_values,
        inductance_scale=2.0,
        capacitance_scale=1.0 / 2.1,
    )
    plot_fitting_results(
        experimental=FittingSeries(voltage=experimental.voltage, power=scaled_power),
        calculated=FittingSeries(voltage=experimental.voltage, power=fitted_power),
        figure_path=args.fig6,
    )

    macro_scaled_power = macro.bolometer_detection / constants.Sb * args.epsilon_fit
    macro_power = _evaluate_power(macro.voltage, macro.resistance, result.best_values)
    plot_fitting_results(
        experimental=FittingSeries(voltage=macro.voltage, power=macro_scaled_power),
        calculated=FittingSeries(voltage=macro.voltage, power=macro_power),
        figure_path=args.fig6,
    )

    text_dataframe = load_txt_data(args.txt_file)
    plot_txt_data(
        dataframe=text_dataframe,
        figure_path=args.fig10,
        epsilon=args.epsilon_comp,
        radiation_resistance=args.rrad,
    )

    text_voltage = (
        text_dataframe["V(nt)"].to_numpy() - text_dataframe["V(na)"].to_numpy()
    )
    text_current = -text_dataframe["I(Rfg)"].to_numpy() * 1e3
    text_power = text_dataframe["power"].to_numpy() * args.rrad

    plot_complex_figure(
        experimental=ComplexFigureData(
            voltage=macro.voltage,
            current=macro.current,
            power=macro.bolometer_detection,
        ),
        calculated=ComplexFigureData(
            voltage=text_voltage,
            current=text_current,
            power=text_power,
        ),
        figure_path=args.fig10,
        constants=constants,
        epsilon=args.epsilon_comp,
        show_experimental=True,
    )


if __name__ == "__main__":
    main()
