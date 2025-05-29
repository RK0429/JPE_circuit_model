#!/usr/bin/env python3
"""Script to modify JPE_3stacks.asc by adjusting the number of 1stack components and
their parameters."""
import argparse
import logging

from python_integration.utils import modify_stacks, parse_params


def main():
    parser = argparse.ArgumentParser(description="Modify JPE_3stacks.asc file")
    parser.add_argument("input", help="Path to input JPE_3stacks.asc")
    parser.add_argument(
        "-o",
        "--output",
        default="JPE_3stacks_modified.asc",
        help="Output ASC file path",
    )
    parser.add_argument(
        "-n", "--num", type=int, required=True, help="Desired number of stacks"
    )
    parser.add_argument(
        "-p",
        "--params",
        nargs="*",
        default=[],
        help="Per-stack parameters, e.g. L=175n,R=8.29,C=100n",
    )
    parser.add_argument(
        "--simulate", action="store_true", help="Run simulation after modification"
    )
    parser.add_argument("--sim-output", help="Simulation output folder")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    params_list = parse_params(args.params)
    modify_stacks(
        args.input,
        args.output,
        "1stack",
        args.num,
        params_list,
        args.simulate,
        args.sim_output,
    )


if __name__ == "__main__":
    main()
