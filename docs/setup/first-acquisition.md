# First acquisition

In principle, every acquisition can be structured into the following procedure: connect to the cards, load the sequence, set the acquisition parameters, run the acquisition and store the data.

!!! note
    Usually, we would run an acquisition using the [nexus service](nexus-service.md). This example serves as a quick reference to test the `AcquisitionControl` in a single Jupyter notebook or Python script.

## Acquisition control

In a first step, we import the `AcquisitionControl` and create an instance of it using the path to our [device configuration](../system/configuration.md). This loads and validates the device configuration and connects and configures both measurement cards.

!!! warning
    When using an `AcquisitionControl` instance directly, you may want to create the instance before turning on your amplifiers (see [Wiring](../system/wiring.md#safety)).

```python
from console.spcm_control.acquisition_control import AcquisitionControl

acq = AcquisitionControl(configuration_file="device_config.yaml")
```

## Construct a sequence

Construct a PyPulseq sequence with the system limits of the console using one of the provided sequence constructors.

```python
import console
from console.utilities.sequences import se_spectrum

seq = se_spectrum.constructor(echo_time=20e-3, rf_duration=200e-6, system=acq.get_sequence_system())
console.parameter.larmor_frequency = 2.0e6
console.parameter.num_averages = 1
```

## Set acquisition parameter

Parameters that can be adjusted and changed at runtime are kept in an `AcquisitionParameter` instance.
On import, the package loads the last saved [acquisition parameter](../system/configuration.md#acquisition-parameter) state or creates a default state. Any change to the parameters is automatically synchronized with a JSON file on disk. This instance is created in the global scope so that it can be used across different scripts.

```python
import console

console.parameter.larmor_frequency = 2.0e6
console.parameter.num_averages = 1
```

## Run acquisition

`set_sequence` uses the sequence and the acquisition parameter instance to calculate the waveforms that are replayed by the console (see [sequence unrolling](../system/sequence-unrolling.md) for further details).
Instead of the sequence instance, the path to a Pulseq sequence file can be used as well.
After calculating the sequence waveforms, the sequence is executed using `run()`.
The acquisition data is processed automatically and returned as an `AcquisitionData` instance.

```python
acq.set_sequence(sequence=seq, parameter=console.parameter)
acq_data = acq.run()
```

## Save acquisition data

The acquisition data contains an `RxData` object for each ADC event that was acquired.
One specific object can be selected from the list of acquired `RxData` objects.
The acquired complex-valued signal is stored in the `processed_data` attribute.
`save()` stores the `AcquisitionData`, the metadata and the sequence.
Using `save_ismrmrd()`, the `AcquisitionData` can be stored in ISMRMRD format.
To close the card connection, delete the `AcquisitionControl` instance.

```python
rx_data = acq_data.receive_data[0]           # first ADC event of the first average
signal = rx_data.processed_data              # complex, shape (channels, samples)
acq_data.add_info({"note": "first acquisition"})
acq_data.save()                              # store HDF5, meta.json and sequence.seq
acq_data.save_ismrmrd()                      # ISMRMRD file

# Disconnect from the cards
del acq
```

Instead of manually creating and deleting the `AcquisitionControl` in the experiment script, the cards can be operated by a persistent service (see [Acquisition service](nexus-service.md)). Complete experiments are given in the [Examples](../examples/index.md).
