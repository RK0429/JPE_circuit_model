import logging
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kupicelib import AscEditor  # type: ignore
from kuPyLTSpice import LTspice, SimRunner  # type: ignore


def parse_params(param_strs: List[str]) -> List[Dict[str, str]]:
    """Parse parameter strings like 'L=175n,R=8.29,C=100n' into a list of dicts."""
    results: List[Dict[str, str]] = []
    for s in param_strs:
        entry: Dict[str, str] = {}
        for pair in s.split(","):
            if "=" in pair:
                key, val = pair.split("=", 1)
                entry[key.strip()] = val.strip()
        results.append(entry)
    return results

def modify_stacks(
    input_file: str,
    output_file: str,
    symbol_name: str,
    num_stacks: int,
    params_list: List[Dict[str, str]],
    simulate: bool = False,
    sim_output: Optional[str] = None,
    timeout: Optional[float] = None,
    run_switches: Optional[List[str]] = None,
) -> Optional[Tuple[Any, Any]]:
    """
    Generic function to modify ASC files by adjusting the number of components
    with the given symbol_name, updating their parameters, saving the netlist,
    and optionally running a simulation.
    """
    editor = AscEditor(input_file)
    # Identify existing components with matching symbol_name
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

    # Add missing components by cloning the first one
    if num_stacks > existing_count:
        if existing_count == 0:
            raise RuntimeError(f"No template component '{symbol_name}' found to clone")
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

    if simulate:
        runner = SimRunner(simulator=LTspice, output_folder=sim_output or "sim_results")
        if run_switches:
            raw_file, log_file = runner.run_now(
                output_file,
                switches=run_switches,
                timeout=timeout if timeout is not None else 600.0,
            )
            if (
                raw_file is None
                or log_file is None
                or not Path(raw_file).exists()
                or not Path(log_file).exists()
            ):
                raise RuntimeError(
                    f"Simulation did not produce expected files: {raw_file}, {log_file}"
                )
            logging.info(f"Simulation completed. Raw: {raw_file}, Log: {log_file}")
            return raw_file, log_file
        else:
            runner.run(output_file)
            runner.wait_completion()
    return None
