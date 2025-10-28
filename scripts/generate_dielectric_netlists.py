#!/usr/bin/env python3
"""Generate LTspice netlists for dielectric parameter estimation studies.

This helper reproduces the experiment conditions listed in
``Paper/DissertationTeX/chapters/ch05_nonlinear_circuit/dielectric_parameter_estimation/dielectric_parameter_estimation.tex``.
It subdivides the three mesas according to Table ``tab:simulation_conditions``,
applies the shape-scaling rules from the dissertation, and emits netlists that
instantiate the ``1stack`` subcircuit with geometry-dependent parameters.

Key features
------------
* Uses the fitted bulk parameters from Table ``tab:fitting_parameters``.
* Respects the quasiparticle resistance scaling via the ``M`` and ``N`` knobs
  exposed by ``models/1stack.asc`` (``1.5 nm`` per junction).
* Applies the ``1 μs = 1 s`` unit scaling used in existing LTspice decks by
  multiplying all inductances and capacitances by ``1e6``.
* Writes one `.net` file per subdivision tuple (``1-1-1`` up to ``10-40-150``)
  into the requested output directory.

Example
-------
```bash
uv run python src/JPE_circuit_model/scripts/generate_dielectric_netlists.py \
    --output-dir src/JPE_circuit_model/examples/dielectric_netlists
```
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from math import floor, log
from pathlib import Path
from textwrap import dedent

# --- Constants ----------------------------------------------------------------

JUNCTION_THICKNESS_NM = 1.5
LC_TIMESCALE = 1_000_000.0  # 1 μs is treated as 1 s inside LTspice decks.
TEMPLATE_BLOCK_ERROR = "Template netlist is missing marker comment"

ENGINEERING_SUFFIXES = {
    -5: "f",
    -4: "p",
    -3: "n",
    -2: "u",
    -1: "m",
    1: "k",
    2: "Meg",
    3: "g",
    4: "t",
}


SIMULATION_CASES: dict[str, tuple[int, int, int]] = {
    "1-1-1": (1, 1, 1),
    "1-4-15": (1, 4, 15),
    "2-8-30": (2, 8, 30),
    "3-16-60": (3, 16, 60),
    "10-40-150": (10, 40, 150),
}


@dataclass(frozen=True)
class MesaGeometry:
    name: str
    area_um2: float
    thickness_nm: float
    critical_current_ma: float

    @property
    def area_m2(self) -> float:
        return self.area_um2 * 1e-12

    @property
    def thickness_m(self) -> float:
        return self.thickness_nm * 1e-9

    @property
    def junction_count(self) -> int:
        return round(self.thickness_nm / JUNCTION_THICKNESS_NM)


@dataclass(frozen=True)
class BulkParameters:
    r_p_total: float
    l_p_total: float
    c_int_total: float
    r_total: float
    l_total: float
    c_total: float
    r_int_total: float


@dataclass(frozen=True)
class MesaDerived:
    geometry: MesaGeometry
    r_p: float
    l_p: float
    c_int: float
    r_series: float
    l_series: float
    c_series: float
    r_int: float
    i_c_amp: float


@dataclass(frozen=True)
class Segment:
    label: str
    mesa_name: str
    stack_index: int
    node_in: str
    node_out: str
    junctions: int
    thickness_nm: float
    r_p: float
    l_p: float
    c_int: float
    r_int: float
    m_value: float
    i_c_amp: float

    def to_netlist_line(self) -> str:
        params = [
            f"M={format_float(self.m_value)}",
            f"N={self.junctions}",
            f"I_c={format_eng(self.i_c_amp)}",
            f"R={format_eng(self.r_p)}",
            f"L={format_eng(self.l_p * LC_TIMESCALE)}",
            f"C={format_eng(self.c_int * LC_TIMESCALE)}",
        ]
        params_str = " ".join(params)
        return (
            f"{self.label} {self.node_in} {self.node_out} T 0 "
            f"1stack params: {params_str}"
        )


# --- Helpers ------------------------------------------------------------------

def format_eng(value: float) -> str:
    """Format numeric values using SPICE-friendly engineering prefixes."""
    if value == 0.0:
        return "0"
    exponent = floor(log(abs(value), 1000))
    if exponent == 0:
        return f"{value:g}"
    suffix = ENGINEERING_SUFFIXES.get(exponent)
    if suffix is None:
        return f"{value:.6E}"
    scaled = value * 1000 ** -exponent
    return f"{scaled:g}{suffix}"


def format_float(value: float) -> str:
    """Format dimensionless ratios with limited precision."""
    return f"{value:.6g}"


def chunks(sequence: Iterable[str], width: int) -> Iterator[list[str]]:
    """Yield successive chunks of ``sequence`` with length at most ``width``."""
    block: list[str] = []
    for item in sequence:
        block.append(item)
        if len(block) >= width:
            yield block
            block = []
    if block:
        yield block


def compute_mesa_parameters(
    geometries: list[MesaGeometry],
    bulk: BulkParameters,
) -> list[MesaDerived]:
    ratios = [mesa.thickness_m / mesa.area_m2 for mesa in geometries]
    ratio_sum = sum(ratios)

    gamma_c = bulk.c_total * ratio_sum
    gamma_c_int = bulk.c_int_total * ratio_sum

    derived: list[MesaDerived] = []
    for idx, mesa in enumerate(geometries):
        ratio = ratios[idx]
        r_scale = ratio / ratio_sum
        r_p = bulk.r_p_total * r_scale
        l_p = bulk.l_p_total * r_scale
        r_series = bulk.r_total * r_scale
        l_series = bulk.l_total * r_scale
        r_int = bulk.r_int_total * r_scale
        c_series = gamma_c * mesa.area_m2 / mesa.thickness_m
        c_int = gamma_c_int * mesa.area_m2 / mesa.thickness_m
        derived.append(
            MesaDerived(
                geometry=mesa,
                r_p=r_p,
                l_p=l_p,
                c_int=c_int,
                r_series=r_series,
                l_series=l_series,
                c_series=c_series,
                r_int=r_int,
                i_c_amp=mesa.critical_current_ma * 1e-3,
            )
        )
    return derived


def distribute_junctions(total: int, segments: int) -> list[int]:
    """Split ``total`` junctions into ``segments`` almost-equal integers."""
    base = total // segments
    remainder = total % segments
    return [base + (1 if i < remainder else 0) for i in range(segments)]


def build_segments(
    mesa: MesaDerived,
    segments: int,
    label_offset: int,
    start_node: str,
    final_node: str,
    r_total: float,
    prefix: str,
) -> tuple[list[Segment], str]:
    """Create per-segment parameters and nodes for a given mesa."""
    junction_counts = distribute_junctions(mesa.geometry.junction_count, segments)
    node_names: list[str] = []
    current_node = start_node
    label_width = max(3, len(str(label_offset + segments)))
    name_width = max(2, len(str(segments)))
    segments_out: list[Segment] = []

    for idx, junctions in enumerate(junction_counts, start=1):
        is_last_segment = idx == segments
        segment_label = f"XX{label_offset + idx:0{label_width}d}"
        if is_last_segment:
            next_node = final_node
        else:
            suffix = f"_s{idx:0{name_width}d}"
            next_node = f"{prefix}{suffix}"
        node_names.append(next_node)

        thickness_nm = junctions * JUNCTION_THICKNESS_NM
        thickness_ratio = thickness_nm / mesa.geometry.thickness_nm
        # Resistive/inductive quantities scale with thickness; capacitances scale inversely.
        r_p = mesa.r_p * thickness_ratio
        l_p = mesa.l_p * thickness_ratio
        r_int = mesa.r_int * thickness_ratio
        c_int = mesa.c_int * (mesa.geometry.thickness_nm / thickness_nm)

        segments_out.append(
            Segment(
                label=segment_label,
                mesa_name=mesa.geometry.name,
                stack_index=idx,
                node_in=current_node,
                node_out=next_node,
                junctions=junctions,
                thickness_nm=thickness_nm,
                r_p=r_p,
                l_p=l_p,
                c_int=c_int,
                r_int=r_int,
                m_value=r_total / r_int,
                i_c_amp=mesa.i_c_amp,
            )
        )
        current_node = next_node

    return segments_out, current_node


def load_template(template_path: Path) -> tuple[list[str], list[str]]:
    """Return template netlist sections without stack instances."""
    try:
        raw_text = template_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw_text = template_path.read_text(encoding="cp1252")
    content = raw_text.splitlines()
    try:
        block_idx = content.index("* block symbol definitions")
    except ValueError as exc:  # pragma: no cover - template structure invariant
        raise RuntimeError(TEMPLATE_BLOCK_ERROR) from exc

    prefix = [
        line
        for line in content[:block_idx]
        if not line.strip().startswith("XX")
    ]
    suffix = content[block_idx:]
    return prefix, suffix


def render_netlist(
    prefix: list[str],
    suffix: list[str],
    segments: list[Segment],
    lc_bulk: tuple[float, float, float],
    ic_nodes: list[str],
    case_label: str,
) -> str:
    """Assemble the full netlist text for a single subdivision case."""
    header = list(prefix)
    header.insert(
        0,
        f"* Generated by generate_dielectric_netlists.py for case {case_label}",
    )
    header.append(f"* Stack configuration: {case_label}")

    for segment in segments:
        header.append(segment.to_netlist_line())
    header.append("")

    r_total, l_total, c_total = lc_bulk
    # Replace R_rad / L_rad / C_rad if present.
    for idx, line in enumerate(header):
        token = line.strip().split()
        if not token:
            continue
        if token[0] == "R_rad":
            header[idx] = f"R_rad Nd N003 {format_eng(r_total)}"
        elif token[0] == "L_rad":
            header[idx] = f"L_rad N003 N005 {format_eng(l_total * LC_TIMESCALE)}"
        elif token[0] == "C_rad":
            header[idx] = f"C_rad N005 Na {format_eng(c_total * LC_TIMESCALE)}"

    tail = list(suffix)
    ic_entries = [f"V({node})=0" for node in ic_nodes]
    ic_lines: list[str] = []
    for block in chunks(ic_entries, 6):
        prefix_token = ".ic" if not ic_lines else "+"
        ic_lines.append(f"{prefix_token} {' '.join(block)}")

    try:
        tran_idx = next(
            idx for idx, line in enumerate(tail) if line.strip().startswith(".tran")
        )
    except StopIteration:  # pragma: no cover - template invariant
        tran_idx = -1

    for idx in range(tran_idx + 1, len(tail)):
        if tail[idx].strip().startswith(".ic"):
            tail[idx : idx + 1] = ic_lines
            break

    return "\n".join(header + tail) + "\n"


def generate_case(
    case_name: str,
    subdivision: tuple[int, int, int],
    template_prefix: list[str],
    template_suffix: list[str],
    mesas: list[MesaDerived],
    bulk: BulkParameters,
    output_dir: Path,
) -> Path:
    """Generate one netlist and return its path."""
    segments: list[Segment] = []
    node_pointer = "Nd"
    label_offset = 0
    interface_names = ["Nc", "Nb", "Na"]
    last_mesa_index = len(mesas) - 1

    for mesa_idx, (mesa, seg_count) in enumerate(zip(mesas, subdivision, strict=True)):
        final_node = "Na" if mesa_idx == last_mesa_index else interface_names[mesa_idx]
        prefix = interface_names[mesa_idx]
        generated, node_pointer = build_segments(
            mesa=mesa,
            segments=seg_count,
            label_offset=label_offset,
            start_node=node_pointer,
            final_node=final_node,
            r_total=bulk.r_int_total,
            prefix=prefix,
        )
        segments.extend(generated)
        label_offset += seg_count
        if mesa_idx != last_mesa_index:
            node_pointer = final_node

    ic_nodes_order = ["Nd"]
    for segment in segments:
        if segment.node_out not in ic_nodes_order:
            ic_nodes_order.append(segment.node_out)
    if "Na" not in ic_nodes_order:
        ic_nodes_order.append("Na")

    lc_bulk = (bulk.r_total, bulk.l_total, bulk.c_total)

    netlist_text = render_netlist(
        prefix=template_prefix,
        suffix=template_suffix,
        segments=segments,
        lc_bulk=lc_bulk,
        ic_nodes=ic_nodes_order,
        case_label=case_name,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"JPE_diel_{case_name}.net"
    output_path.write_text(netlist_text, encoding="utf-8")
    return output_path


# --- CLI ----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate LTspice netlists for dielectric parameter estimation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent(
            """\
            Available cases:
              1-1-1, 1-4-15, 2-8-30, 3-16-60, 10-40-150
            """
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="src/JPE_circuit_model/examples/dielectric_netlists",
        type=Path,
        help="Directory to place generated .net files (default: %(default)s)",
    )
    parser.add_argument(
        "--template",
        default="src/JPE_circuit_model/examples/JPE_3stacks.net",
        type=Path,
        help="Existing LTspice netlist used as template (default: %(default)s)",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=list(SIMULATION_CASES.keys()),
        help="Subset of cases to generate (default: all)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = args.cases or list(SIMULATION_CASES.keys())
    template_prefix, template_suffix = load_template(args.template)

    geometries = [
        MesaGeometry("Mesa1", area_um2=16_333.0, thickness_nm=60.0, critical_current_ma=12.0),
        MesaGeometry("Mesa2", area_um2=24_500.0, thickness_nm=258.0, critical_current_ma=18.0),
        MesaGeometry("Mesa3", area_um2=24_568.0, thickness_nm=954.0, critical_current_ma=18.05),
    ]
    bulk = BulkParameters(
        r_p_total=1.5190,
        l_p_total=2.6958e-12,
        c_int_total=1.2149e-13,
        r_total=8.5994,
        l_total=6.3986e-12,
        c_total=1.0498e-14,
        r_int_total=204.1,
    )

    mesas = compute_mesa_parameters(geometries, bulk)

    for case_name in cases:
        subdivision = SIMULATION_CASES[case_name]
        generate_case(
            case_name=case_name,
            subdivision=subdivision,
            template_prefix=template_prefix,
            template_suffix=template_suffix,
            mesas=mesas,
            bulk=bulk,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":  # pragma: no cover - script entry point
    main()
