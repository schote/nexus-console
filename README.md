# Nexus-Console for Advanced Low-Field MRI

![Python](https://img.shields.io/badge/python-3.10-blue)
[![License](https://img.shields.io/github/license/schote/spectrum-console)](https://www.gnu.org/licenses/gpl-3.0.de.html)
[![Sphinx Docs](https://github.com/schote/spectrum-console/actions/workflows/docs.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/docs.yml)
[![Static Tests](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml)
[![Pytest](https://github.com/schote/spectrum-console/actions/workflows/pytest.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/pytest.yml)
![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fgist.githubusercontent.com%2Fschote%2F4d47c22492a23337a79400f4859a4c25%2Fraw%2Fcd5263422b929b375047c5b78e145f5cec6197ad%2Fcoverage.json)

This project aims to implement a versatile console for low-field magnetic resonance imaging (MRI) acquisitions. The central hardware components are two spectrum cards from Spectrum Instrumentation. 
They serve as arbitrary waveform generators (AWG) and analog to digital converter (digitizer). 
Depending on the measurement card specification, the Nexus console can also be used for higher frequencies (first experiments at 7T were conducted).
This application controls AWG and digitizer cards to perform MRI scans by directly interpreting sequences defined by the open-source pulseq framework, i.e. the python implementation [pypulseq](https://github.com/imr-framework/pypulseq). 
An interfaces to the open data MR raw data format [ISMRMRD](https://ismrmrd.github.io/apidocs/1.5.0/) is implemented to directly enable Nexus with the latest reconstruction algorithms, e.g. from the [Gadgetron](https://gadgetron.github.io/) toolbox.

## Installation

It is recommended to install the package in a virtual environment (e.g. [conda](https://docs.conda.io/projects/conda/en/stable/)). 
Further documentation on setting up miniconda can be found [here](https://conda.io/projects/conda/en/stable/user-guide/install/index.html). 
The package was developed under [Python 3.10](https://www.python.org/downloads/release/python-3100/) so it is recommended to use `python==3.10`.

To install the Nexus console application, clone the repository an ensure that you are in the repository directory, which is `*/nexus-console/`. 
The package can be installed with different dependencies depending on the specific requirements:

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

Please follow the project [documentation](https://schote.github.io/nexus-console/) which contains a quick-start guide, some examples and a user guide.


---
