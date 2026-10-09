# Quickstart

This page describes the installation of the console software. It assumes that the measurement cards are installed and wired, and that the Spectrum driver is installed (see [Hardware](../system/hardware.md) and [Wiring](../system/wiring.md)).

## Requirements

- Python ≥ 3.13
- Spectrum Instrumentation driver for the measurement cards ([download area](https://spectrum-instrumentation.com/support/downloads.php))

## Installation

Install the package into a virtual environment (`venv` or `conda`):

```bash
pip install nexus-console
```

For development, clone the repository and install it in editable mode with the optional dependency groups:

```bash
git clone https://github.com/schote/nexus-console.git
cd nexus-console
pip install -e ".[test,lint,dev]"
```

| Extra | Content |
|---|---|
| `test` | pytest and coverage |
| `lint` | ruff, mypy |
| `dev` | Profiling and notebook tools |
| `docs-mkdocs` | Documentation build |

## Verification

```bash
nexus --help
```

```python
import console
print(console.parameter)
```

On import, the package loads the last saved [acquisition parameter](../system/configuration.md#acquisition-parameter) state from `<home>/nexus-console/acquisition-parameter.state` or creates a default state.

## Device configuration

Copy [`examples/example_device_config.yaml`](https://github.com/schote/nexus-console/blob/main/examples/example_device_config.yaml) and adapt it to the hardware: device paths, sampling rate, output and input ranges, termination, amplifier gains, coil efficiencies and system limits. The keys are explained in [Device configuration](../system/configuration.md).

Continue with the [first acquisition](first-acquisition.md).

## Documentation

To build the documentation locally, install the `docs-mkdocs` extra and start the development server:

```bash
pip install -e ".[docs-mkdocs]"
mkdocs serve --watch src
```
