# Installation

## Prerequisites

Before installing Nexus Console, ensure that the following hardware and software requirements are met:

- **Spectrum Instrumentation measurement cards** installed in the host computer via PCIe slots (AWG model M2p.6546-x4 and digitizer model M2p.5933-x4, or compatible variants from the M2p series).
- **Spectrum Instrumentation driver** installed and operational. Driver packages are available from the [Spectrum Instrumentation downloads page](https://spectrum-instrumentation.com/support/downloads.php).
- **Python 3.10 – 3.13** (earlier or later versions are not officially supported).

## Install from PyPI

The recommended installation method for end users is to install from the Python Package Index:

```bash
pip install nexus-console
```

## Install from source (development)

For development work or to modify the source code, clone the repository and perform an editable install:

```bash
git clone https://github.com/schote/nexus-console.git
cd nexus-console
pip install -e .
```

### Optional dependency groups

Additional dependency groups are available for testing, linting, documentation building, and development:

```bash
pip install -e ".[test]"         # pytest, pytest-cov, pytest-xdist, coverage
pip install -e ".[lint]"         # mypy, ruff, types-PyYAML
pip install -e ".[docs-mkdocs]"  # MkDocs Material documentation stack
pip install -e ".[dev]"          # profiling tools, Jupyter notebook support
```

Multiple groups can be combined:

```bash
pip install -e ".[test,lint,dev]"
```

## Virtual environment (recommended)

It is strongly recommended to install Nexus Console into an isolated virtual environment to avoid dependency conflicts. Using Conda:

```bash
conda create --name nexus-env "python>=3.10,<3.14"
conda activate nexus-env
pip install nexus-console
```

Or using the standard `venv` module:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install nexus-console
```

## Verify the installation

After a successful installation, the `nexus` command-line entry point is available:

```bash
nexus --help
```

To verify that the package is importable:

```python
import console
print(console.parameter)
```

This will print the currently active `AcquisitionParameter` state (loaded from the last saved state, or the default if no state file exists).

## Device configuration

Nexus Console requires a YAML configuration file (`device_config.yaml`) describing the hardware: PCIe device paths, per-channel amplitude limits, gradient coil efficiency, gradient power amplifier (GPA) gain, and MRI system limits used to instantiate the PyPulseq sequence system. A reference configuration is included in the repository root and must be adapted to match the target hardware.

See [Measurement cards](../setup/cards.md) for a description of all configuration parameters.
