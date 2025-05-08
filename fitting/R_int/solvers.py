#!/usr/bin/env python
# coding: utf-8

import logging
from typing import cast

import numpy as np
from scipy.optimize import root  # type: ignore

from fitting.R_int.model import P2T, T2R_int, T2R_th


def solve4T(
    T: float, P: float, alpha: float, beta: float, gamma: float, T_bath: float
) -> float:
    """
    Solve for temperature residual given power and parameters.
    """
    R_th = cast(float, T2R_th(T, alpha, beta, gamma))
    T_calc = cast(float, P2T(P, R_th, T_bath))
    return T - T_calc


def solve4V_int(
    V_int: float,
    I_int: float,
    A: float,
    B: float,
    C: float,
    D: float,
    alpha: float,
    beta: float,
    gamma: float,
    T_bath: float,
) -> float:
    """
    Function to solve for V_int given I_int and model parameters.
    """
    P = V_int * I_int
    sol = root(fun=solve4T, x0=30.0, args=(P, alpha, beta, gamma, T_bath))
    if not sol.success:
        logging.warning(
            f"Root finding did not converge for V_int={V_int}, I_int={I_int}."
        )
    T_val = sol.x[0]
    R_int = cast(float, T2R_int(T_val, A, B, C, D))
    return V_int - R_int * I_int


def I_int2V_int(
    I_ints: np.ndarray,
    A: float,
    B: float,
    C: float,
    D: float,
    alpha: float,
    beta: float,
    gamma: float,
    T_bath: float,
) -> np.ndarray:
    """
    Calculate V_int array from I_int array using root finding.
    """
    V_int = np.empty_like(I_ints)
    for i, I in enumerate(I_ints):
        sol = root(
            fun=solve4V_int, x0=20e-3, args=(I, A, B, C, D, alpha, beta, gamma, T_bath)
        )
        if sol.success:
            V_int[i] = sol.x[0]
        else:
            logging.warning(f"Root finding did not converge for I_int={I}.")
            V_int[i] = np.nan
    return V_int
