#!/usr/bin/env python3
"""
Script to modify JPE_3stacks.asc by adjusting the number of
1stack components and their parameters.
"""
import argparse
import logging
from copy import deepcopy
from typing import Optional

from kupicelib import AscEditor  # type: ignore
from kuPyLTSpice import LTspice, SimRunner  # type: ignore


def modify_3stacks(
    input_file: str,
    output_file: str,
    num_stacks: int,
    params_list: list,
    simulate: bool = False,
    sim_output: Optional[str] = None,
):
    """
    Modify input ASC file by adjusting the number of 1stack components
    and updating their parameters. Optionally run simulation.
    """
    editor = AscEditor(input_file)
    symbol_name = "1stack"
    # Identify existing components
    all_refs = [
        ref
        for ref in editor.get_components()
        if editor.get_component(ref).symbol == symbol_name
    ]
    sorted_refs = sorted(all_refs, key=lambda r: int(r.lstrip("X")))
    existing_count = len(sorted_refs)
    # Compute vertical spacing
    if existing_count >= 2:
        pos0 = editor.get_component(sorted_refs[0]).position.Y
        pos1 = editor.get_component(sorted_refs[1]).position.Y
        delta_y = pos1 - pos0
    else:
        delta_y = 176
    # Remove extra components
    if num_stacks < existing_count:
        for ref in sorted_refs[num_stacks:]:
            editor.remove_component(ref)
    # Add missing components
    if num_stacks > existing_count:
        if existing_count == 0:
            raise RuntimeError("No template 1stack component found to clone")
        template = editor.get_component(sorted_refs[0])
        for i in range(existing_count + 1, num_stacks + 1):
            new_comp = deepcopy(template)
            new_comp.reference = f"X{i}"
            new_comp.position.Y = template.position.Y + (i - 1) * delta_y
            editor.add_component(new_comp)
    # Update parameters
    for idx, params in enumerate(params_list, start=1):
        if idx > num_stacks:
            break
        ref = f"X{idx}"
        editor.set_component_parameters(ref, **params)
    # Save modified ASC
    editor.save_netlist(output_file)
    logging.info(f"Modified ASC saved to {output_file}")
    # Optional simulation
    if simulate:
        runner = SimRunner(simulator=LTspice, output_folder=sim_output or "sim_results")
        runner.run(output_file)
        runner.wait_completion()


def parse_params(param_strs):
    """Parse parameter strings like 'L=175n,R=8.29,C=100n' into a list of dicts."""
    results = []
    for s in param_strs:
        entry = {}
        for pair in s.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                entry[key.strip()] = val.strip()
        results.append(entry)
    return results


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
    modify_3stacks(
        args.input, args.output, args.num, params_list, args.simulate, args.sim_output
    )


if __name__ == "__main__":
    main()
