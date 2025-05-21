#!/usr/bin/env python3
"""Script to simulate a simple RLC resonant circuit ASC file."""
import argparse
import logging

from kupicelib import AscEditor
from kuPyLTSpice import LTspice, SimRunner


def main():
    parser = argparse.ArgumentParser(description="Simulate a simple RLC resonant circuit ASC file")
    parser.add_argument("input", help="Path to input .asc file")
    parser.add_argument("-o", "--output", default=None, help="Path to output modified .asc file")
    parser.add_argument("--output-folder", default="resonant_sim_results", help="Simulation output folder")
    parser.add_argument("--params", nargs="*", default=None, help="Optional component parameter overrides (e.g. R1=20n,L1=1m)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    editor = AscEditor(args.input)

    # Apply parameter overrides if provided
    if args.params:
        for param in args.params:
            if "=" in param:
                comp, val = param.split("=", 1)
                logging.info(f"Setting component {comp} value to {val}")
                editor.set_component_parameters(comp, Value=val)

    # Add AC analysis and measurement directives
    editor.reset_netlist()
    editor.add_instructions(
        "; Simulation settings",
        ".ac dec 100 1 100k",
        ".meas AC Gain MAX mag(V(out))"
    )

    output_asc = args.output or args.input.replace(".asc", "_sim.asc")
    editor.save_netlist(output_asc)
    logging.info(f"Modified ASC saved to {output_asc}")

    runner = SimRunner(simulator=LTspice, output_folder=args.output_folder)
    runner.run(output_asc)
    runner.wait_completion()
    logging.info(f"Simulation completed. Results in folder {args.output_folder}")

if __name__ == "__main__":
    main()
