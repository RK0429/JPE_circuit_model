# Mac LTspice .raw and .log File Generation Issue - Solution Guide

## Problem Summary

When running LTspice simulations on Mac through Python scripts, the .raw and .log files are not being generated in the output folder. This is due to limitations of the native Mac version of LTspice.

## Root Causes

1. **Mac native LTspice cannot run .asc files directly from command line** - it requires .net (netlist) files
2. **Mac native LTspice cannot programmatically generate netlists from .asc files** - this functionality is not available in the Mac version
3. **Limited command-line options** - Mac LTspice only supports the `-b` (batch) flag

## Solutions

### Solution 1: Use LTspice under Wine (Recommended)

Install Wine and the Windows version of LTspice on your Mac:

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Wine
brew install --cask wine-stable

# Download Windows LTspice installer from analog.com
# Run it with Wine:
wine LTspice64.exe

# Set environment variables for the Python scripts
export LTSPICEFOLDER="$HOME/.wine/drive_c/Program Files/ADI/LTspice"
export LTSPICEEXECUTABLE="LTspice.exe"
```

### Solution 2: Manual Netlist Export

1. Open your .asc file in LTspice GUI
2. Go to View → SPICE Netlist
3. Save the netlist as a .net file
4. Modify your Python script to use the .net file instead of .asc

### Solution 3: Use Pre-generated Netlists

Create netlist files for your circuits and place them alongside your .asc files:

```python
# Modify your script to check for existing .net files
from pathlib import Path

asc_file = Path("examples/simple_resonant.asc")
net_file = asc_file.with_suffix(".net")

if net_file.exists():
    simulation_file = str(net_file)
else:
    simulation_file = str(asc_file)  # Will fail on Mac native
```

### Solution 4: Hybrid Approach (Implemented)

The modified `edit_simple_resonant.py` now includes logic to:

1. Detect if Mac native LTspice is being used
2. Look for existing .net files
3. Attempt to use Wine-based LTspice if available
4. Provide clear warnings about limitations

## Testing Your Setup

To verify which LTspice version you're using:

```python
from cespy import LTspice

if LTspice.using_macos_native_sim():
    print("Using Mac native LTspice (limited functionality)")
else:
    print("Using Wine-based LTspice (full functionality)")
```

## Best Practices for Mac Users

1. **Preferred**: Install LTspice via Wine for full functionality
2. **Alternative**: Pre-generate all netlists using the GUI
3. **Workaround**: Modify scripts to handle both .asc and .net files
4. **Documentation**: Always document which LTspice version your project requires

## Example Netlist Format

If you need to manually create netlists, here's the format:

```spice
* Circuit Title
V1 n001 0 AC 1
R1 n001 n002 10
L1 n002 out 1m
C1 out 0 100n
.ac dec 100 1 100k
.meas AC Gain MAX mag(V(out))
.end
```

## Environment Setup for CI/CD

For automated testing on Mac:

```yaml
# .github/workflows/test.yml
env:
  LTSPICE_MAC_NATIVE: "skip"  # Skip tests requiring netlist generation
  LTSPICEEXECUTABLE: "/path/to/wine/ltspice.exe"  # Or use Wine
```

## Troubleshooting

1. **No output files**: Check if LTspice process is actually running (`ps aux | grep -i ltspice`)
2. **Permission issues**: Ensure output directory is writable
3. **Path issues**: Use absolute paths for all file operations
4. **Wine issues**: Check Wine installation with `wine --version`

## Future Improvements

Consider migrating to simulators with better cross-platform support:

- NGspice (open source, full command-line support)
- Xyce (Sandia's parallel circuit simulator)
- QUCS (Qt-based circuit simulator)

These alternatives provide consistent behavior across all platforms.
