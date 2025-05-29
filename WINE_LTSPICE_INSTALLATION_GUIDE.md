# Wine-based LTspice Installation Guide for Mac

This guide documents the steps to successfully install and configure Wine-based LTspice on macOS to resolve issues where `.raw` or `.log` files are not generated when using the native Mac LTspice.

## Prerequisites

- macOS (Tested on Apple Silicon M4 Pro)
- Homebrew package manager
- Administrator privileges during installation

## Installation Steps

### 1. Install Homebrew (if not already installed)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2. Install Wine using Homebrew

```bash
brew install --cask wine-stable
```

**Note**: `wine-stable` is built for Intel macOS and requires Rosetta 2. If prompted, install Rosetta 2 with the following command.
**Further Note**: We have confirmed that the above command works without issues on Apple Silicon Macs.

```bash
softwareupdate --install-rosetta --agree-to-license
```

### 3. Download the Windows LTspice Installer

```bash
cd ~/Downloads
curl -L -o LTspice64.exe "https://ltspice.analog.com/software/LTspice64.exe"
```

### 4. Install LTspice using Wine

```bash
wine ~/Downloads/LTspice64.exe
```

Follow the Windows installer wizard. The default installation path is:
`C:\Program Files\LTC\LTspiceXVII\` (within Wine's virtual C: drive)

### 5. Set Environment Variables

Add the following to your shell configuration file (`~/.zshrc` or `~/.bashrc`):

```bash
# LTspice Wine Configuration
export LTSPICEFOLDER="$HOME/.wine/drive_c/Program Files/LTC/LTspiceXVII"
export LTSPICEEXECUTABLE="XVIIx64.exe"
```

Then, reload your shell configuration:

```bash
source ~/.zshrc  # or source ~/.bashrc
```

### 6. Verify Installation

Test that LTspice can be launched via Wine:

```bash
wine "$LTSPICEFOLDER/$LTSPICEEXECUTABLE" -h
```

## Using Wine-based LTspice with Python Scripts

### Test Setup

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

On success, you should see:

- Simulation messages indicating success
- Files generated in the output folder:
  - `.asc` - Modified circuit file
  - `.net` - Netlist file
  - `.raw` - Simulation results (waveform data)
  - `.log` - Simulation log file

### Verifying Wine vs. Native LTspice

To check which version of LTspice is being used:

```python
from cespy.simulators.ltspice_simulator import LTspice
print("Using Mac native LTspice:", LTspice.using_macos_native_sim())
# Should display False (indicating Wine-based LTspice)
```

## Troubleshooting

### Common Issues

1. **Wine GUI opens instead of batch mode**: This is normal behavior for some operations. The simulation should still complete successfully.

2. **Permission errors**: Ensure the output directory is writable.

    ```bash
    chmod -R 755 /path/to/output/directory
    ```

3. **Path not found errors**: Verify your Wine prefix and LTspice installation.

    ```bash
    ls "$HOME/.wine/drive_c/Program Files/LTC/LTspiceXVII/"
    ```

4. **Environment variables not loaded**: Ensure you `source`d your shell configuration file after adding the exports.

### Wine-Specific Messages

You may see various Wine messages during execution (MoltenVK info, fixme warnings, etc.). These are normal and can be ignored as long as the simulation completes successfully.

## Advantages of Wine-based LTspice

1. **Full command-line support**: Capable of generating netlists from `.asc` files
2. **Batch mode operation**: Supports `-Run` and `-netlist` flags
3. **Complete file generation**: Produces all expected output files (`.raw`, `.log`, `.net`)
4. **Python integration**: Works seamlessly with `cespy` and `PyLTSpice` libraries

## Performance Considerations

- Wine adds some overhead compared to native applications
- The first run may be slower due to Wine initialization
- Subsequent runs are typically faster
- GUI operations might experience some lag

## Alternative Solutions

If Wine-based LTspice does not suit your needs, consider these alternatives:

1. **NGspice**: Open-source simulator with native Mac support
2. **Xyce**: Parallel circuit simulator from Sandia National Laboratories
3. **QUCS**: Qt-based circuit simulator
4. **Running simulations on a Windows VM or remote machine**

## Conclusion

Wine-based LTspice successfully addresses the limitations of native Mac LTspice, enabling full command-line automation and proper file generation for circuit simulation workflows on macOS.
