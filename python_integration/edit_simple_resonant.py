#!/usr/bin/env python3
"""Script to simulate a simple RLC resonant circuit ASC file."""
import argparse
import logging

from cespy import AscEditor, LTspice, SimRunner


def main():
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
    # Ensure fresh netlist load before applying parameter overrides
    editor.reset_netlist()

    # Apply parameter overrides if provided
    if args.params:
        for param in args.params:
            if "=" in param:
                comp, val = param.split("=", 1)
                logging.info("Setting component %s value to %s", comp, val)
                editor.set_component_parameters(comp, Value=val)

    # Add AC analysis and measurement directives
    editor.add_instructions(".ac dec 100 1 100k", ".meas AC Gain MAX mag(V(out))")

    output_asc = args.output or args.input.replace(".asc", "_sim.asc")
    editor.save_netlist(output_asc)
    logging.info("Modified ASC saved to %s", output_asc)

    # Check if we need special handling for Mac native LTspice
    import sys
    from pathlib import Path

    simulation_file = output_asc

    # Try to detect if Mac native LTspice is being used
    if sys.platform == "darwin":
        try:
            # Check if LTspice can handle ASC files
            if LTspice.using_macos_native_sim():
                logging.info("Mac native LTspice detected.")

                # Look for an existing netlist file
                output_net = Path(output_asc).with_suffix(".net")
                if output_net.exists():
                    logging.info("Found existing netlist file: %s", output_net)
                    simulation_file = str(output_net)
                else:
                    # Try to use wine-based LTspice if available
                    logging.info(
                        "Mac native LTspice has limitations. "
                        "Attempting to use Wine-based LTspice for netlist generation..."
                    )

                    # Temporarily switch to wine-based LTspice if available
                    import os

                    wine_ltspice = os.environ.get("LTSPICEEXECUTABLE")
                    if wine_ltspice:
                        # Generate netlist using wine-based LTspice
                        try:
                            netlist_path = LTspice.create_netlist(output_asc)
                            simulation_file = str(netlist_path)
                            logging.info("Netlist generated: %s", netlist_path)
                        except Exception as e:
                            logging.warning("Failed to generate netlist: %s", e)
                            # Continue with ASC file and let it fail with proper error
                    else:
                        logging.warning(
                            "No Wine-based LTspice found. Simulation may fail. "
                            "Consider: 1) Installing LTspice via Wine, or "
                            "2) Manually exporting netlist from LTspice GUI"
                        )
        except AttributeError:
            # using_macos_native_sim not available in this version
            logging.debug("Could not detect Mac native LTspice version")

    runner = SimRunner(
        simulator=LTspice, output_folder=args.output_folder, verbose=True
    )
    runner.run(simulation_file)
    runner.wait_completion()
    logging.info("Simulation completed. Results in folder %s", args.output_folder)


if __name__ == "__main__":
    main()
