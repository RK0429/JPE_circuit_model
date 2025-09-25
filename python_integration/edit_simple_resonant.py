#!/usr/bin/env python3
"""Script to simulate a simple RLC resonant circuit ASC file."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from cespy import AscEditor, LTspice, SimRunner


def _resolve_simulation_file(output_asc: str) -> str:
    """Return the path that should be passed to the simulator."""
    simulation_path = output_asc

    if sys.platform != "darwin":
        return simulation_path

    try:
        if not LTspice.using_macos_native_sim():
            return simulation_path
    except AttributeError:
        logging.debug("Could not detect Mac native LTspice version")
        return simulation_path

    logging.info("Mac native LTspice detected.")
    output_net = Path(output_asc).with_suffix(".net")
    if output_net.exists():
        logging.info("Found existing netlist file: %s", output_net)
        return output_net.as_posix()

    logging.info(
        "Mac native LTspice has limitations. Attempting to use Wine-based LTspice for netlist generation..."
    )
    wine_ltspice = os.environ.get("LTSPICEEXECUTABLE")
    if not wine_ltspice:
        logging.warning(
            "No Wine-based LTspice found. Simulation may fail. Consider installing LTspice via Wine or exporting the netlist manually."
        )
        return simulation_path

    try:
        netlist_path = LTspice.create_netlist(output_asc)
    except (RuntimeError, OSError) as error:
        logging.warning("Failed to generate netlist: %s", error)
    else:
        logging.info("Netlist generated: %s", netlist_path)
        simulation_path = str(netlist_path)

    return simulation_path


def main() -> None:
    """Main function to run the simple resonant circuit simulation."""
    parser = argparse.ArgumentParser(
        description="Simulate a simple RLC resonant circuit ASC file"
    )
    parser.add_argument("input", help="Path to input .asc file")
    parser.add_argument(
        "-o", "--output", default=None, help="Path to output modified .asc file"
    )
    parser.add_argument(
        "--output-folder",
        default="resonant_sim_results",
        help="Simulation output folder",
    )
    parser.add_argument(
        "-p",
        "--params",
        nargs="*",
        default=None,
        help="Optional component parameter overrides (e.g. R1=20n,L1=1m)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    editor = AscEditor(args.input)
    editor.reset_netlist()

    if args.params:
        for param in args.params:
            if "=" not in param:
                continue
            component, value = param.split("=", 1)
            logging.info("Setting component %s value to %s", component, value)
            editor.set_component_parameters(component, Value=value)

    editor.add_instructions(".ac dec 100 1 100k", ".meas AC Gain MAX mag(V(out))")

    output_asc = args.output or args.input.replace(".asc", "_sim.asc")
    editor.save_netlist(output_asc)
    logging.info("Modified ASC saved to %s", output_asc)

    simulation_file = _resolve_simulation_file(output_asc)

    runner = SimRunner(
        simulator=LTspice, output_folder=args.output_folder, verbose=True
    )
    runner.run(simulation_file)  # type: ignore[reportUnknownMemberType]
    runner.wait_completion()
    logging.info("Simulation completed. Results in folder %s", args.output_folder)


if __name__ == "__main__":
    main()
