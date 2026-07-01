# Spin-Echo Spectrum

This example demonstrates how to acquire an NMR spectrum using a spin-echo sequence and display the magnitude spectrum via a Fast Fourier Transform (FFT). It serves as a minimal integration test for the complete signal chain: sequence generation → waveform replay → NMR signal acquisition → post-processing.

## Experiment overview

A spin-echo sequence consists of a 90° excitation pulse followed, after half the echo time (TE/2), by a 180° refocusing pulse. The spin echo forms at time TE after excitation. Because the spin echo refocuses static field inhomogeneity dephasing, it yields narrower spectral lines than a free-induction decay (FID), making it preferable for spectroscopic measurements on inhomogeneous low-field magnets.

The sequence constructor `console.utilities.sequences.spectrometry.se_spectrum.constructor` accepts:

| Parameter | Description |
|---|---|
| `echo_time` | Time between excitation pulse centre and echo centre (s) |
| `rf_duration` | Duration of the rectangular RF pulses (s) |
| `use_sinc` | If `True`, use a sinc-shaped excitation pulse instead of a rectangular block pulse |
| `system` | PyPulseq `Opts` system limits (obtained from `AcquisitionControl.get_sequence_system()`) |

## Step-by-step breakdown

The experiment proceeds as follows:

1. **Instantiate `AcquisitionControl`** — connects to the TX and RX cards and reads the device configuration.
2. **Construct the spin-echo sequence** — creates a PyPulseq `Sequence` object with the specified echo time and RF pulse duration.
3. **Set acquisition parameters** — specify the Larmor frequency; all other parameters are loaded from the persisted state.
4. **Unroll and execute** — `set_sequence` unrolls the PyPulseq description into `int16` waveform arrays and arms the hardware; `run()` executes the acquisition loop.
5. **Extract processed data** — `processed_data` contains the complex baseband signal after demodulation, phase correction, and decimation.
6. **Compute the spectrum** — a double-sided FFT with fftshift yields the magnitude spectrum; the frequency axis is computed from the decimated dwell time.
7. **Save results** — `add_info` appends metadata to the acquisition record; `save` writes `rx_data.h5`, `meta.json`, and the `.seq` file.
8. **Disconnect** — `del acq` triggers the `AcquisitionControl` destructor, which disconnects from both cards.

## Example script

```python title="examples/spinecho_1d.py"
--8<-- "examples/spinecho_1d.py"
```

!!! note "Frequency axis"
    The FFT frequency axis is computed from the decimated dwell time of the processed data, which is available as `acq_data.receive_data[0].dwell_time` (in seconds). The `processed_data` numpy array does not carry a `dwell_time` attribute.

## Expected output

The magnitude spectrum shows one or more peaks centred near the Larmor frequency offset. In a well-shimmed, homogeneous low-field magnet, the line width at half maximum reflects the inherent T2* of the sample. Broad or shifted peaks indicate a Larmor frequency calibration error or field inhomogeneity.
