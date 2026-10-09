# First acquisition

An acquisition consists of four steps: connect to the cards, define sequence and acquisition parameters, run the acquisition, and store the data.

!!! warning
    Switch off the RF and gradient power amplifiers before connecting to the cards (see [Wiring](../system/wiring.md#safety)).

```python
import console
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.sequences import se_spectrum

# 1. Connect to the cards using the device configuration
acq = AcquisitionControl(configuration_file="device_config.yaml")

# 2. Construct a sequence with the system limits of the console and set acquisition parameters
seq = se_spectrum.constructor(echo_time=20e-3, rf_duration=200e-6, system=acq.get_sequence_system())
console.parameter.larmor_frequency = 2.0e6
console.parameter.num_averages = 1

# 3. Unroll the sequence and run the acquisition
acq.set_sequence(sequence=seq, parameter=console.parameter)
acq_data = acq.run()

# 4. Access and store the data
rx_data = acq_data.receive_data[0]           # first ADC event of the first average
signal = rx_data.processed_data              # complex, shape (channels, samples)
acq_data.add_info({"note": "first acquisition"})
acq_data.save()                              # HDF5, JSON and .seq file
acq_data.save_ismrmrd()                      # ISMRMRD file

# Disconnect from the cards
del acq
```

| Step | Description | Details |
|---|---|---|
| Connect | Loads and validates the device configuration, connects and configures both cards | [Device configuration](../system/configuration.md) |
| Sequence | Any PyPulseq `Sequence`, or the path to a `.seq` file; the acquisition parameters are read from `console.parameter` | [Sequence unrolling](../system/sequence-unrolling.md) |
| Run | Replays the sequence `num_averages` times and processes the received data | [Acquisition](../system/acquisition.md) |
| Data | One `RxData` per ADC event and average | [Signal flow](../system/signal-flow.md) |

`AcquisitionControl.run` accepts a `progress_callback`, which is called with the progress in percent, and `store_unprocessed=True` to keep the raw samples. Before running, the waveforms can be inspected with `acq.plot_waveforms(time_range=(0, 50e-3))`.

Instead of creating `AcquisitionControl` in the experiment script, the cards can be operated by a persistent service (see [Remote acquisition](../examples/remote_acquisition.md)). Complete experiments are given in the [Examples](../examples/index.md).
