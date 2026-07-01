# Examples

The following examples demonstrate common low-field MRI experiments using Nexus Console. Each example is self-contained: it constructs a PyPulseq sequence, executes the acquisition, and processes or visualises the result.

!!! warning "Hardware required"
    All examples below require a connected and calibrated MRI system (TX and RX Spectrum Instrumentation cards, magnet, gradient coils, and RF chain). They cannot be executed in a software-only environment. Before running any example, ensure that the Larmor frequency (`console.parameter.larmor_frequency`) and B1 scaling (`console.parameter.b1_scaling`) have been calibrated for the target system.

## Available examples

| Example | Sequence type | Key output |
|---|---|---|
| [Spin-echo spectrum](spin_echo.md) | Spin-echo, 1D | NMR spectrum via FFT |
| [T2 relaxation](t2_measurement.md) | Multi-TE spin-echo | T2 map via exponential fitting |
| [3D turbo spin-echo](tse_3d.md) | 3D TSE / RARE | Reconstructed 3D image volume |

## Implementing custom experiments

It is recommended to maintain custom experiments in a **separate repository** from the Nexus Console package, importing the console as an installed dependency. This separation keeps system-specific calibration data and experiment scripts isolated from the framework source code. The built-in sequence constructors in `console.utilities.sequences` provide a starting point that can be adapted or replaced by fully custom PyPulseq sequences.
