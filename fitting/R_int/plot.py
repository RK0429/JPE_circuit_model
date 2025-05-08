#!/usr/bin/env python
# coding: utf-8

import logging
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from fitting.R_int.model import T2R_th


def plot_thermal_resistance(result, output: Optional[str] = None):
    """
    Plot Thermal Resistance vs Temperature from fitting result.
    """
    T = np.linspace(-50, 100, 100)
    R_th = T2R_th(
        T,
        result.best_values["alpha"],
        result.best_values["beta"],
        result.best_values["gamma"],
    )

    plt.figure(figsize=(8, 6))
    plt.plot(T, R_th, label="Thermal Resistance Model")
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Thermal Resistance [K/W]")
    plt.xlabel("Temperature [K]")
    plt.legend()
    plt.tight_layout()
    if output:
        plt.savefig(output)
        logging.info(f"Thermal resistance plot saved to {output}.")
    plt.show()


def plot_voltage_current(
    I_int: np.ndarray,
    V_int_exp: np.ndarray,
    V_int_calc: np.ndarray,
    output: Optional[str] = None,
):
    """
    Plot Experimental and Calculated Voltage vs Current.
    """
    plt.figure(figsize=(8, 6))
    plt.scatter(I_int * 1e3, V_int_exp, label="Experimental", s=5)
    plt.scatter(I_int * 1e3, V_int_calc, label="Calculated", s=5)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Voltage [V]")
    plt.xlabel("Current [mA]")
    plt.legend()
    plt.tight_layout()
    if output:
        plt.savefig(output)
        logging.info(f"Voltage vs current plot saved to {output}.")
    plt.show()


def plot_current_temperature(
    I_int: np.ndarray, T_cal: np.ndarray, output: Optional[str] = None
):
    """
    Plot Temperature vs Current.
    """
    plt.figure(figsize=(8, 6))
    plt.scatter(I_int, T_cal, s=5)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Temperature [K]")
    plt.xlabel("Current [A]")
    plt.tight_layout()
    if output:
        out = output.replace(".pdf", "_Temperature_vs_Current.pdf")
        plt.savefig(out)
        logging.info(f"Temperature vs current plot saved to {out}.")
    plt.show()


def plot_current_thermal_resistance(
    I_int: np.ndarray, R_th_cal: np.ndarray, result, output: Optional[str] = None
):
    """
    Plot Thermal Resistance vs Current.
    """
    plt.figure(figsize=(8, 6))
    plt.scatter(I_int, R_th_cal, s=5)
    plt.grid(True, linestyle="--", linewidth=0.5)
    plt.ylabel("Thermal Resistance [K/W]")
    plt.xlabel("Current [A]")
    plt.ylim(0, result.best_values["gamma"] * 10)
    plt.tight_layout()
    if output:
        out = output.replace(".pdf", "_Thermal_Resistance_vs_Current.pdf")
        plt.savefig(out)
        logging.info(f"Thermal resistance vs current plot saved to {out}.")
    plt.show()
