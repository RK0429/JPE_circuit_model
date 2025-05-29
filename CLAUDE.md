# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JPE_circuit_model is a Python-based circuit modeling and simulation framework for Josephson Plasma Emitters (JPE) using LTSpice and other SPICE simulators. The project combines circuit simulation capabilities with analysis tools for processing and visualizing simulation results, including experimental data fitting.

## Development Commands

```bash
# Install dependencies (using Poetry)
poetry install

# Run formatters
poetry run black .
poetry run autopep8 --in-place --recursive .

# Run linters
poetry run flake8
poetry run pylint python_integration fitting post_processing

# Run type checker
poetry run mypy python_integration fitting post_processing

# Run tests
poetry run pytest

# Build documentation (for submodules)
cd cespy/docs && make html
cd kupicelib/doc && sphinx-build . _build
cd kuPyLTSpice/doc && sphinx-build . _build
```

## Architecture Overview

The project consists of three main components:

### 1. Core Libraries (Submodules)

- **cespy/**: Unified Python toolkit for SPICE simulators (LTSpice, NGSpice, QSpice, Xyce)
  - Provides simulator abstraction, schematic editing, and analysis tools
  - Has its own CLAUDE.md with detailed architecture information
  
- **kuPyLTSpice/**: Modified PyLTSpice for LTSpice automation
  - Handles LTSpice-specific operations and file formats
  
- **kupicelib/**: Extended library for SPICE simulation automation
  - Additional utilities and simulator support

### 2. Analysis Scripts

- **post_processing/**: Data processing and visualization
  - `time_averaging.py`: Reduces data size through time averaging and visualizes I-V characteristics
  - `phase_analysis.py`: Analyzes and visualizes phase relationships
  
- **fitting/**: Experimental data fitting
  - `R_int/main.py`: Internal resistance fitting analysis
  - `antenna_params/with_L/main.py`: Antenna parameter fitting with inductance
  - `antenna_params/without_L/main.py`: Antenna parameter fitting without inductance

### 3. Circuit Models

- **examples/**: LTSpice circuit files (.asc)
  - `JPE_3stacks.asc`: 3-stack JPE model
  - `JPE_3stacks_RC.asc`: RC model variant
  - `simple_resonant.asc`: Simple resonant circuit
  
- **models/**: Component models (.asc, .asy)
  - Single stack models with and without RC components

## Key Workflows

### Running Simulations

1. Open circuit files in LTSpice from `examples/` directory
2. Run simulations (transient analysis is pre-configured)
3. Export data as text files for analysis

### Processing Simulation Data

```bash
# Time averaging analysis (from raw data)
python post_processing/time_averaging.py raw_data/dc_sweep_JPE.txt \
  --output_file data/dc_sweep_processed.txt \
  --plot_path results/dc_sweep_plot.png \
  --tt_plot_path results/temperature_time_plot.png

# Phase analysis
python post_processing/phase_analysis.py data/dc_sweep_JPE_phase_original.txt \
  results/dc_sweep_JPE_phase_processed.txt \
  --plot-file results/dc_sweep_phase_plot.pdf

# R_int fitting
python fitting/R_int/main.py data/R_int_data.txt \
  --output-data results/R_int_processed.dat \
  --output-plot results/R_int_plots.pdf
```

### Programmatic Circuit Editing

The `python_integration/` directory contains utilities for programmatically modifying circuit files:

- `edit_jpe_3stacks.py`: Modify 3-stack JPE circuits
- `edit_jpe_3stacks_rc.py`: Modify RC variant circuits
- `edit_simple_resonant.py`: Modify simple resonant circuits

## Data Flow

1. **Circuit Design**: Create/modify .asc files in LTSpice
2. **Simulation**: Run in LTSpice, export results as .txt
3. **Processing**: Use Python scripts to analyze and visualize
4. **Fitting**: Apply fitting algorithms to match experimental data

## Important Paths

- **Input data**: `raw_data/` (user should create and populate)
- **Processed data**: `data/`
- **Results**: `results/` (plots and analysis outputs)
- **Simulation outputs**: `simulation/`

## CLI Tools Available

From the cespy submodule:

- `cespy-asc-to-qsch`: Convert LTSpice to QSpice schematics
- `cespy-run-server`: Start simulation server
- `cespy-raw-convert`: Convert raw file formats
- `cespy-sim-client`: Connect to simulation server
- `cespy-ltsteps`: Process LTSpice step data
- `cespy-rawplot`: Plot raw simulation data
- `cespy-histogram`: Generate histograms from data
