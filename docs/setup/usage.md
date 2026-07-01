# Usage

This page describes the minimal workflow to perform an MRI acquisition with Nexus Console. A complete end-to-end experiment consists of five steps: instantiating the acquisition control, defining acquisition parameters, loading a pulse sequence, executing the acquisition, and saving the results.

## The global parameter object

When the `console` package is imported, it attempts to load the last persisted `AcquisitionParameter` state from `~/nexus-console/acquisition-parameter.state`. If no state file exists, a default instance is created. The recovered (or default) instance is exposed as `console.parameter`:

```python
import console

# Inspect the current global acquisition parameter state
print(console.parameter)
```

This global singleton is mutated in place by experiment scripts and automatically persisted to disk on every attribute change, ensuring that the most recent calibration state (Larmor frequency, B1 scaling, etc.) is available across sessions.

## Minimal end-to-end acquisition

```python
import console
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.sequences.spectrometry import se_spectrum

# 1. Connect to hardware —————————————————————————————————————————
#    AcquisitionControl reads device_config.yaml and connects to both cards.
acq = AcquisitionControl(configuration_file="device_config.yaml")

# 2. Set acquisition parameters ——————————————————————————————————
#    The global instance already holds the last calibrated state; only
#    parameters that differ from the saved state need to be updated.
console.parameter.larmor_frequency = 2.0e6   # Larmor frequency in Hz
console.parameter.b1_scaling       = 1.0     # RF transmit power scaling
console.parameter.num_averages     = 1        # number of signal averages

# 3. Build a pulse sequence ——————————————————————————————————————
#    Sequence constructors return pypulseq Sequence objects.
#    Pass the system limits from the acquisition control to ensure that
#    timing constraints are consistent with the hardware configuration.
seq = se_spectrum.constructor(
    echo_time=20e-3,    # echo time in s
    rf_duration=200e-6, # RF pulse duration in s
    system=acq.get_sequence_system(),
)

# 4. Unroll the sequence and arm the hardware ————————————————————
acq.set_sequence(sequence=seq, parameter=console.parameter)

# 5. Execute the acquisition ————————————————————————————————————
acq_data = acq.run()

# 6. Access the processed data ——————————————————————————————————
#    processed_data shape: (num_coils, num_samples)
rx = acq_data.receive_data[0]
data = rx.processed_data.squeeze()   # complex baseband signal

# 7. Save results ————————————————————————————————————————————————
acq_data.add_info({"note": "spin-echo spectrum acquisition"})
acq_data.save()          # writes rx_data.h5 + meta.json + sequence.seq

# 8. Disconnect ——————————————————————————————————————————————————
#    The AcquisitionControl destructor handles disconnection;
#    calling del explicitly is good practice in scripts.
del acq
```

## Using your own PyPulseq sequences

Any `pypulseq.Sequence` object can be passed directly to `set_sequence`. This makes it straightforward to integrate Nexus Console with custom sequence design workflows:

```python
from pypulseq import Sequence, make_block_pulse, make_adc, make_delay

system = acq.get_sequence_system()
seq = Sequence(system=system)

rf = make_block_pulse(flip_angle=90 * 3.14159 / 180, duration=200e-6, system=system)
adc = make_adc(num_samples=512, dwell=10e-6, system=system)
delay = make_delay(d=20e-3)

seq.add_block(rf)
seq.add_block(delay)
seq.add_block(adc)

acq.set_sequence(sequence=seq, parameter=console.parameter)
acq_data = acq.run()
```

Alternatively, a `.seq` file path can be passed as a string:

```python
acq.set_sequence(sequence="path/to/sequence.seq", parameter=console.parameter)
```

## Persisting acquisition parameters

`AcquisitionParameter` supports explicit save and load operations, making it possible to archive calibration states together with acquisition data:

```python
# Save to a specific path
console.parameter.save("experiments/session_20240101/params.state")

# Load from a specific path
from console.interfaces.acquisition_parameter import AcquisitionParameter
params = AcquisitionParameter.load("experiments/session_20240101/params.state")
```

## Exporting to ISMRMRD

To export acquired data in ISMRMRD format for use with Gadgetron or other reconstruction tools, call `save_ismrmrd` with an optional ISMRMRD header:

```python
import ismrmrd

header = ismrmrd.xsd.ismrmrdHeader()
# ... populate header fields (encoding, trajectories, etc.) ...

mrd_path = acq_data.save_ismrmrd(header=header)
```

If no header is provided, a minimal header containing system information and experimental conditions is generated automatically.

## Next steps

For detailed experiment examples, see:

- [Spin-echo spectrum](../examples/spin_echo.md)
- [T2 relaxation measurement](../examples/t2_measurement.md)
- [3D turbo spin-echo imaging](../examples/tse_3d.md)

For a deep dive into how the acquisition loop, sequence unrolling, and post-processing work, see the [Code reference](../reference/).
