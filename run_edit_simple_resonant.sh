#\!/bin/bash
# Wrapper script to run edit_simple_resonant with correct PYTHONPATH

export PYTHONPATH="/Users/r-kobayashi/Documents/DoctoralResearch/JPE_circuit_model/cespy/src:$PYTHONPATH"
poetry run python -m python_integration.edit_simple_resonant "$@"
