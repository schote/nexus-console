# Spectrum-Pulseq MRI Console

[![Sphinx Docs](https://github.com/schote/spectrum-console/actions/workflows/docs.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/docs.yml)
[![Static Tests](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml)

This project aims to implement a console for magnetic resonance imaging (MRI) acquisitions. The central hardware components are two spectrum cards from Spectrum Instrumentation. They serve as arbitrary waveform generators (AWG) and analog to digital converter (digitizer). This application controls AWG and digitizer cards to perform MRI scans from a sequence description with the open-source pulseq framework. The console application is formerly designed for low-field applications, but might be extendable also for higher field strength.

## Installation

It is recommended to install the package in a virtual environment. There are many options to create and manage virtual environments. Examples are [virtualenv](https://mothergeo-py.readthedocs.io/en/latest/development/how-to/venv-win.html), [venv](https://docs.python.org/3/library/venv.html), [conda](https://docs.conda.io/projects/conda/en/stable/) or [miniconda](https://docs.conda.io/en/latest/miniconda.html). Further documentation on miniconda can be found [here](https://conda.io/projects/conda/en/stable/user-guide/install/index.html).

You can check your python version by running `python --version`, `python > 3.10` is required.

To install the console application, ensure that you are in the repository directory (`*/spectrum-console/`). Use one of the following commands to install the package with the dependencies needed:

### `pip install -e .`

Installs all the necessary base dependencies to use the package (minimum required).

### `pip install -e ".[lint]"`

Installs additional (optional) dependencies that are required to run the linter.

### `pip install -e ".[test]"`

Installs additional (optional) dependencies that are required to run the linter.

### `pip install -e ".[docs]"`

Installs additional (optional) dependencies that are required to build the sphinx documentation locally.

### `pip install -e ".[dev]"`

Installs additional (optional) developer dependencies for profiling and developing in vs code.


    Hint: Multiple dependency groups can be installed using `[lint, test]` for instance.

---
