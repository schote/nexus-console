# Spectrum-Pulseq MRI Console

[![Sphinx Docs](https://github.com/schote/spectrum-console/actions/workflows/docs.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/docs.yml)
[![Static Tests](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml/badge.svg)](https://github.com/schote/spectrum-console/actions/workflows/static-tests.yml)

This project aims to implement a console for magnetic resonance imaging (MRI) acquisitions. The central hardware components are two spectrum cards from Spectrum Instrumentation. They serve as arbitrary waveform generators (AWG) and analog to digital converter (digitizer). This application controls AWG and digitizer cards to perform MRI scans from a sequence description with the open-source pulseq framework. The console application is formerly designed for low-field applications, but might be extendable also for higher field strength.

## Installation

It is recommended to install the package in a virtual environment (e.g. [conda](https://docs.conda.io/projects/conda/en/stable/)). Further documentation on setting up miniconda can be found [here](https://conda.io/projects/conda/en/stable/user-guide/install/index.html). The package was developed under [Python 3.10](https://www.python.org/downloads/release/python-3100/) so it is recommended to use `python==3.10` when setting up the environment.

To install the console application, ensure that you are in the repository directory `*/spectrum-console/`. 
The following dependency groups gather different package depending on the specific requirements:

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


_Hint: Multiple dependency groups can be installed using `[lint, test]` for instance._

## Usage

The following code gives a minimal example which creates an AcquisitionControl instance and executes a pulseq sequence.
Please note that measurement cards (AWG and digitizer) from spectrum-instrumentation must be installed to run the example.

```
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl

acq = AcquistionControl("../device_config.yaml")

# Define acquisition parameters
params = AcquisitionParameter(
    larmor_frequency=2.031e6,
    b1_scaling=5.0,
    fov_scaling=Dimensions(x=1., y=1., z=1.),
    fov_offset=Dimensions(x=0., y=0., z=0.),
    downsampling_rate=200,
    adc_samples=500,
    num_averages=1
)

data: AcquisitionData = acq.run(parameter=params, sequence=f"sequence_file.seq")

# Get down-sampled raw data with the dimensions: [averages, coils, phase_encoding, readout]
raw_data = data.raw
```


---
