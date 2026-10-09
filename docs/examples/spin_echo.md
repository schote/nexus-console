# Spin-echo spectrum

A spin echo is acquired and its spectrum is calculated by a Fourier transform. The experiment tests the complete signal chain and is used to determine the Larmor frequency: a peak offset from 0 Hz in the spectrum corresponds to the deviation of `console.parameter.larmor_frequency` from the actual resonance frequency.

## Sequence

The constructor [`se_spectrum.constructor`][console.utilities.sequences.spectrometry.se_spectrum.constructor] creates a 90° excitation pulse and a 180° refocussing pulse (phase π/2) at TE/2. The ADC is either centred on the echo or, with `use_fid=True`, acquires the decay after the refocussing pulse.

## Procedure

1. Create an `AcquisitionControl` instance, which connects to the cards.
2. Construct the sequence and set the Larmor frequency.
3. Unroll the sequence with `set_sequence` and run the acquisition.
4. Calculate the spectrum from `processed_data`; the frequency axis follows from the dwell time `RxData.dwell_time`.
5. Store the data with `save()` and disconnect the cards by deleting the instance.

## Script

```python title="examples/spinecho_1d.py"
--8<-- "examples/spinecho_1d.py"
```
