# Installation

This page describes the installation of the console software. It assumes that the measurement cards are installed and wired, and that the Spectrum driver is installed (see [Hardware](../system/hardware.md) and [Wiring](../system/wiring.md)).

## Requirements

- Python ≥ 3.13
- [Spectrum Instrumentation driver](https://spectrum-instrumentation.com/support/downloads.php) for the measurement cards

## Python package

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

Verify the installation by running the following command.

```bash
nexus --help
```

If the installation was successful, you should see the help context of the command you can start the nexus-service with.

## Device configuration

Before you can start executing sequences, you need to create a device configuration file. Copy the example [`examples/example_device_config.yaml`](https://github.com/schote/nexus-console/blob/main/examples/example_device_config.yaml) which serves as a template and adapt it to your hardware. The keys are explained in [Device configuration](../system/configuration.md). Continue with the [first acquisition](first-acquisition.md).