#!/usr/bin/env python
# coding: utf-8

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_fitting_results(
    V: np.ndarray,
    BO_exp_scaled: np.ndarray,
    RP_cal: np.ndarray,
    fig_path: str,
    label_exp: str = "Experimental",
    label_cal: str = "Calculated",
    xlabel: str = "Voltage [V]",
    ylabel: str = "Output Power [units]",
):
    """
    Plot the experimental and calculated output power against voltage and save the figure.
    """
    plt.figure(figsize=(8, 6))
    plt.scatter(V, BO_exp_scaled * 1e6, label=label_exp, s=5)
    plt.scatter(V, RP_cal * 1e6, label=label_cal, s=5)
    plt.grid(True)
    plt.legend()
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(fig_path)
    logging.info(f"Fitting results plot saved to {fig_path}.")
    plt.show()


def plot_complex_figure(
    V_exp: np.ndarray,
    I_exp: np.ndarray,
    RP_exp: np.ndarray,
    V_cal: np.ndarray,
    I_cal: np.ndarray,
    RP_cal: np.ndarray,
    fig_path: str,
    constants,
    epsilon: float = 5000,
    show_exp: bool = True,
):
    """
    Create and save a complex figure with multiple subplots for voltage, current, and power relationships.
    """
    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["mathtext.default"] = "it"
    plt.rcParams["font.size"] = 15

    fig = plt.figure(figsize=(8, 8))
    spec = plt.GridSpec(ncols=2, nrows=2, width_ratios=[5, 2], height_ratios=[2, 5])

    ax_top = fig.add_subplot(spec[0])
    ax_side = fig.add_subplot(spec[3])
    ax_body = fig.add_subplot(spec[2], sharex=ax_top, sharey=ax_side)

    # Top plot
    ax_top.grid(ls="--")
    if show_exp:
        ax_top.scatter(
            V_exp,
            RP_exp / constants.Sb * epsilon * 1e6,
            label="Calculated",
            s=5,
            c="gray",
        )
    ax_top.scatter(V_cal, RP_cal * 1e6, s=5, c=RP_cal * 1e6, cmap="jet")
    ax_top.set_ylabel("Output Power [μW]")
    ax_top.yaxis.set_label_coords(-0.1, 0.5)
    ax_top.set_xlim(-0.05, 1.5)

    # Side plot
    ax_side.grid(ls="--")
    if show_exp:
        ax_side.scatter(
            RP_exp / constants.Sb * epsilon * 1e6,
            I_exp,
            label="Calculated",
            s=5,
            c="gray",
        )
    ax_side.scatter(RP_cal * 1e6, I_cal, s=5, c=RP_cal * 1e6, cmap="jet")
    ax_side.set_xlabel("Output Power [μW]")
    ax_side.set_ylim(0, 45)
    ax_side.set_yticks(np.arange(0, 50, 10))

    # Body plot
    ax_body.grid(ls="--")
    if show_exp:
        ax_body.scatter(V_exp, I_exp, s=5, c="gray")
    ax_body.scatter(V_cal, I_cal, s=5, c=RP_cal * 1e6, cmap="jet")
    ax_body.set_xlabel("Voltage [V]")
    ax_body.set_ylabel("Current [mA]")
    ax_body.yaxis.set_label_coords(-0.1, 0.5)
    ax_body.set_xlim(-0.05, 1.5)
    ax_body.set_ylim(0, 45)
    ax_body.set_xticks([0, 0.25, 0.5, 0.75, 1, 1.25])
    ax_body.set_yticks(np.arange(0, 50, 10))

    fig.tight_layout()
    plt.setp(ax_top.get_xticklabels(), visible=False)
    plt.setp(ax_side.get_yticklabels(), visible=False)
    plt.subplots_adjust(hspace=0.0, wspace=0.0)

    plt.savefig(fig_path)
    logging.info(f"Complex figure saved to {fig_path}.")
    plt.show()


def plot_txt_data(
    df: pd.DataFrame,
    fig_path: str,
    epsilon: float = 5000,
    Rrad: float = 62.69,
):
    """
    Plot the data from the text file in a complex figure.
    """
    plt.rcParams["font.family"] = "Times New Roman"
    plt.rcParams["mathtext.fontset"] = "cm"
    plt.rcParams["mathtext.default"] = "it"
    plt.rcParams["font.size"] = 15

    fig = plt.figure(figsize=(8, 8))
    spec = plt.GridSpec(ncols=2, nrows=2, width_ratios=[5, 2], height_ratios=[2, 5])

    ax_top = fig.add_subplot(spec[0])
    ax_side = fig.add_subplot(spec[3])
    ax_body = fig.add_subplot(spec[2], sharex=ax_top, sharey=ax_side)

    # Top plot
    ax_top.grid(ls="--")
    ax_top.scatter(
        df["V(nt)"] - df["V(na)"],
        df["power"] * Rrad * 1e6,
        s=5,
        c=df["power"] * Rrad * 1e6,
        cmap="jet",
    )
    ax_top.set_xlim(-0.05, 1.5)
    ax_top.set_ylabel(r"Output Power [$μ$W]")
    ax_top.yaxis.set_label_coords(-0.1, 0.5)

    # Side plot
    ax_side.grid(ls="--")
    ax_side.scatter(
        df["power"] * Rrad * 1e6,
        -df["I(Rfg)"] * 1e3,
        s=5,
        c=df["power"] * Rrad * 1e6,
        cmap="jet",
    )
    ax_side.set_xlabel(r"Output Power [$μ$W]")

    # Body plot
    ax_body.grid(ls="--")
    ax_body.scatter(
        df["V(nt)"] - df["V(na)"],
        -df["I(Rfg)"] * 1e3,
        s=5,
        c=df["power"] * Rrad * 1e6,
        cmap="jet",
    )
    ax_body.set_xlabel("Voltage [V]")
    ax_body.set_ylabel("Current [mA]")
    ax_body.set_xticks([0, 0.25, 0.5, 0.75, 1, 1.25])
    ax_body.set_xlim(-0.05, 1.5)
    ax_body.yaxis.set_label_coords(-0.1, 0.5)

    fig.tight_layout()
    plt.setp(ax_top.get_xticklabels(), visible=False)
    plt.setp(ax_side.get_yticklabels(), visible=False)
    plt.subplots_adjust(hspace=0.0, wspace=0.0)

    plt.savefig(fig_path)
    logging.info(f"Text data plot saved to {fig_path}.")
    plt.show()
