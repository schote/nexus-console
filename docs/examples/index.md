# Examples

The examples below are complete acquisition scripts from the [`examples/`](https://github.com/schote/nexus-console/tree/main/examples) directory of the repository. Each script constructs a sequence with one of the built-in constructors in `console.utilities.sequences`, runs the acquisition and processes the result.

!!! warning "Hardware required"
    The examples require a fully assembled and connected system (see [Hardware](../system/hardware.md)). Before running an imaging or relaxometry experiment, the Larmor frequency and the B1 scaling (`console.parameter.larmor_frequency`, `console.parameter.b1_scaling`) must be calibrated for the system.

| Example | Sequence | Result |
|---|---|---|
| [Spin-echo spectrum](spin_echo.md) | Spin echo | Spectrum, e.g. for frequency calibration |
| [T2 relaxation](t2_measurement.md) | Spin echoes with varying echo time | T2 from a mono-exponential fit |
| [3D turbo spin-echo](tse_3d.md) | 3D TSE | Image volume and ISMRMRD export |
| [Remote acquisition](remote_acquisition.md) | 3D TSE | Acquisition via the `nexus` service |

The parameters of all sequence constructors are documented in the API reference under [`utilities.sequences`](../reference/utilities/sequences/tse/tse_3d.md).

## Custom experiments

Any PyPulseq sequence can be passed to `AcquisitionControl.set_sequence`, provided it was constructed with the system limits of the console (`AcquisitionControl.get_sequence_system()`). It is recommended to keep system-specific experiment scripts and calibration data in a separate repository and to use the console as an installed package.
