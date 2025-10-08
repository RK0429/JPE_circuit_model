"""Utility helpers for modifying LTspice ASC files programmatically."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from kupicelib import AscEditor
from kupicelib.editor.asc_editor import AscComponent
from kuPyLTSpice import LTspice, SimRunner

LOGGER = logging.getLogger(__name__)

MIN_COMPONENTS_FOR_SPACING = 2
DEFAULT_VERTICAL_SPACING = 176
DEFAULT_SIMULATION_TIMEOUT = 600.0


@dataclass(slots=True)
class SimulationConfig:
    """Optional configuration for running an LTspice simulation."""

    enabled: bool = False
    output_folder: str | None = None
    timeout: float | None = None
    switches: Sequence[str] | None = None


class NetlistModificationError(RuntimeError):
    """Raised when the ASC file cannot be modified as requested."""

    @classmethod
    def missing_raw_log(cls) -> NetlistModificationError:
        return cls("Simulation did not produce raw/log files")

    @classmethod
    def missing_output(cls, raw_path: Path, log_path: Path) -> NetlistModificationError:
        return cls(f"Simulation output missing: {raw_path}, {log_path}")


def parse_params(param_strs: Sequence[str]) -> list[dict[str, str]]:
    """Parse parameter strings like ``L=175n,R=8.29`` into dictionaries."""
    results: list[dict[str, str]] = []
    for entry in param_strs:
        parameters: dict[str, str] = {}
        for pair in entry.split(","):
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            parameters[key.strip()] = value.strip()
        results.append(parameters)
    return results


def _sorted_component_refs(editor: AscEditor, symbol_name: str) -> list[str]:
    references: list[str] = []
    for reference in editor.get_components():
        component = editor.get_component(reference)
        if component.symbol == symbol_name:
            references.append(reference)
    return sorted(references, key=lambda ref: int(ref.lstrip("X")))


def _compute_vertical_spacing(editor: AscEditor, references: Sequence[str]) -> int:
    if len(references) >= MIN_COMPONENTS_FOR_SPACING:
        first = editor.get_component(references[0]).position.Y
        second = editor.get_component(references[1]).position.Y
        return int(second - first)
    return DEFAULT_VERTICAL_SPACING


def _clone_component(template: AscComponent, index: int, delta_y: int) -> AscComponent:
    clone = deepcopy(template)
    clone.reference = f"X{index}"
    clone.position.Y = template.position.Y + (index - 1) * delta_y
    return clone


def _add_missing_components(
    editor: AscEditor,
    template: AscComponent,
    existing_count: int,
    target_count: int,
    delta_y: int,
) -> None:
    for index in range(existing_count + 1, target_count + 1):
        editor.add_component(_clone_component(template, index, delta_y))


def _apply_parameters(
    editor: AscEditor,
    params_list: Sequence[Mapping[str, str]],
    target_count: int,
) -> None:
    for index, params in enumerate(params_list, start=1):
        if index > target_count:
            break
        editor.set_component_parameters(f"X{index}", **params)


def _run_simulation(
    editor_output: str,
    config: SimulationConfig,
) -> tuple[str, str] | None:
    runner = SimRunner(
        simulator=LTspice,
        output_folder=config.output_folder or "sim_results",
    )
    timeout = config.timeout if config.timeout is not None else DEFAULT_SIMULATION_TIMEOUT

    if config.switches:
        raw_file, log_file = runner.run_now(
            editor_output,
            switches=list(config.switches),
            timeout=timeout,
        )
        if raw_file is None or log_file is None:
            raise NetlistModificationError.missing_raw_log()
        raw_path = Path(raw_file)
        log_path = Path(log_file)
        if not raw_path.exists() or not log_path.exists():
            raise NetlistModificationError.missing_output(raw_path, log_path)
        LOGGER.info("Simulation completed. Raw: %s, Log: %s", raw_path, log_path)
        return raw_path.as_posix(), log_path.as_posix()

    runner.run(editor_output)
    runner.wait_completion()
    LOGGER.info("Simulation completed with asynchronous runner")
    return None


def modify_stacks(
    input_file: str,
    output_file: str,
    symbol_name: str,
    num_stacks: int,
    params_list: Sequence[Mapping[str, str]],
    simulation: SimulationConfig | None = None,
) -> tuple[str, str] | None:
    """Modify an ASC file by cloning/removing components and optionally simulate."""
    editor = AscEditor(input_file)
    references = _sorted_component_refs(editor, symbol_name)
    existing_count = len(references)
    delta_y = _compute_vertical_spacing(editor, references)

    if num_stacks < existing_count:
        for reference in references[num_stacks:]:
            editor.remove_component(reference)

    if num_stacks > existing_count:
        if not references:
            message = f"No template component '{symbol_name}' found to clone"
            raise NetlistModificationError(message)
        template = editor.get_component(references[0])
        _add_missing_components(editor, template, existing_count, num_stacks, delta_y)

    _apply_parameters(editor, params_list, num_stacks)

    editor.save_netlist(output_file)
    LOGGER.info("Modified ASC saved to %s", output_file)

    sim_config = simulation or SimulationConfig()
    if not sim_config.enabled:
        return None

    return _run_simulation(output_file, sim_config)
