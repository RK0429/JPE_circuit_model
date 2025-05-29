# Wine-based LTspice Installation Guide for Mac

This guide documents the successful installation and configuration of Wine-based LTspice on macOS to resolve the issue where .raw and .log files are not generated when using Mac native LTspice.

## Prerequisites

- macOS (tested on Apple Silicon M4 Pro)
- Homebrew package manager
- Admin privileges for installation

## Installation Steps

### 1. Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Wine using Homebrew

```bash
brew install --cask wine-stable
```

**Note**: Wine-stable is built for Intel macOS and requires Rosetta 2. If prompted, install Rosetta 2 with:

```bash
softwareupdate --install-rosetta --agree-to-license
```

### 3. Download Windows LTspice Installer

```bash
cd ~/Downloads
curl -L -o LTspice64.exe "https://ltspice.analog.com/software/LTspice64.exe"
```

### 4. Install LTspice using Wine

```bash
wine ~/Downloads/LTspice64.exe
```

Follow the Windows installer wizard. The default installation path will be:
`C:\Program Files\LTC\LTspiceXVII\` (in Wine's virtual C: drive)

### 5. Configure Environment Variables

Add the following to your shell configuration file (`~/.zshrc` or `~/.bashrc`):

```bash
# LTspice Wine configuration
export LTSPICEFOLDER="$HOME/.wine/drive_c/Program Files/LTC/LTspiceXVII"
export LTSPICEEXECUTABLE="XVIIx64.exe"
```

Then reload your shell configuration:

```bash
source ~/.zshrc  # or source ~/.bashrc
```

### 6. Verify Installation

Test that LTspice can be launched via Wine:

```bash
wine "$LTSPICEFOLDER/$LTSPICEEXECUTABLE" -h
```

## Using Wine-based LTspice with Python Scripts

### Testing the Setup

1. Navigate to your project directory:

```bash
cd /path/to/your/project
```

2. Run a simulation:

```bash
./run_edit_simple_resonant.sh ./examples/simple_resonant.asc \
  -o ./examples/simple_resonant_modified.asc \
  --output-folder ./simulation/simple_resonant \
  -p "R1=20n"
```

### Expected Output

When successful, you should see:

- Simulation messages indicating success
- Generated files in the output folder:
  - `.asc` - Modified circuit file
  - `.net` - Netlist file
  - `.raw` - Simulation results (waveform data)
  - `.log` - Simulation log file

### Verifying Wine vs Native LTspice

To check which version of LTspice is being used:

```python
from cespy.simulators.ltspice_simulator import LTspice
print("Using Mac native LTspice:", LTspice.using_macos_native_sim())
# Should print: False (indicating Wine-based LTspice)
```

## Troubleshooting

### Common Issues

1. **Wine GUI opens instead of batch mode**: This is normal for some operations. The simulation should still complete successfully.

2. **Permission errors**: Ensure the output directory is writable:

```bash
chmod -R 755 /path/to/output/directory
```

3. **Path not found errors**: Verify the Wine prefix and LTspice installation:

```bash
ls "$HOME/.wine/drive_c/Program Files/LTC/LTspiceXVII/"
```

4. **Environment variables not loading**: Ensure you've sourced your shell configuration file after adding the exports.

### Wine-specific Messages

You may see various Wine messages during execution (MoltenVK info, fixme warnings). These are normal and can be ignored as long as the simulation completes successfully.

## Advantages of Wine-based LTspice

1. **Full command-line support**: Can generate netlists from .asc files
2. **Batch mode operation**: Supports -Run and -netlist flags
3. **Complete file generation**: Produces all expected output files (.raw, .log, .net)
4. **Python integration**: Works seamlessly with cespy and PyLTSpice libraries

## Performance Considerations

- Wine adds some overhead compared to native applications
- First run may be slower due to Wine initialization
- Subsequent runs are typically faster
- GUI operations may show some latency

## Alternative Solutions

If Wine-based LTspice doesn't meet your needs, consider:

1. **NGspice**: Open-source simulator with native Mac support
2. **Xyce**: Sandia's parallel circuit simulator
3. **QUCS**: Qt-based circuit simulator
4. **Running simulations on a Windows VM or remote machine**

## Conclusion

Wine-based LTspice successfully resolves the limitations of Mac native LTspice, enabling full command-line automation and proper file generation for circuit simulation workflows on macOS.
