# Spectrum-Pulseq MRI Console

[![Sphinx Docs](https://github.com/schote/spectrum-console/actions/workflows/docs.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/docs.yml)
[![Static Tests](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml)

This project aims to implement a console for magnetic resonance imaging (MRI) acquisitions. The central hardware components are two spectrum cards from Spectrum Instrumentation. They serve as arbitrary waveform generators (AWG) and analog to digital converter (digitizer). This application controls AWG and digitizer cards to perform MRI scans from a sequence description with the open-source pulseq framework. The console application is formerly designed for low-field applications, but might be extendable also for higher field strength.

## Installation

It is recommended to install the package in a virtual environment (e.g. [conda](https://docs.conda.io/projects/conda/en/stable/)). 
Further documentation on setting up miniconda can be found [here](https://conda.io/projects/conda/en/stable/user-guide/install/index.html). 
The package was developed under [Python 3.10](https://www.python.org/downloads/release/python-3100/) so it is recommended to use `python==3.10`.

To install the console application, clone the repository an ensure that you are in the repository directory, which is `*/spectrum-console/`. 
The package can be installed with differen dependencies depending on the specific requirements:

    `pip install -e .`

Installs all the necessary base dependencies to use the package (minimum required).

    `pip install -e ".[lint]"`

Installs additional (optional) dependencies that are required to run the linter.

    `pip install -e ".[test]"`

Installs additional (optional) dependencies that are required to run the linter.

    `pip install -e ".[docs]"`

Installs additional (optional) dependencies that are required to build the sphinx documentation locally.

    `pip install -e ".[dev]"`

Installs additional (optional) developer dependencies for profiling and developing in vs code.


    _Hint: Multiple dependency groups can be installed using `".[lint, test]"` for instance._

## Usage

Please follow the project [documentation](schote.github.io/spectrum-console/) which contains a quick-start guide, some examples and a user guide.


---
