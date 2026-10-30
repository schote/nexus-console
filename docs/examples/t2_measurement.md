# T2 relaxation

The transverse relaxation time T2 is determined from a series of spin echoes with increasing echo time TE. The echo amplitudes are fitted to the model

$$
S(\text{TE}) = a + b \, e^{-\text{TE}/T_2},
$$

where the offset $a$ accounts for noise and baseline contributions.

## Sequence

The constructor [`t2_relaxation.constructor`][console.utilities.sequences.spectrometry.t2_relaxation.constructor] repeats a spin-echo experiment for `num_steps` echo times linearly spaced in `echo_time_range`, separated by the repetition time. It returns the sequence and the array of echo times. Each echo time yields one ADC event, i.e. one entry in `AcquisitionData.receive_data` per echo time and average.

## Procedure

1. Construct the sequence and set the calibrated Larmor frequency and B1 scaling.
2. Run the acquisition and arrange the data as `(averages, coils, echo times, samples)` using `RxData.average_index`.
3. Average, determine the peak amplitude of each echo and fit the model with `scipy.optimize.curve_fit`.
4. Store the fitted T2 and the echo times with the acquisition data.

## Script

```python title="examples/t2_measurement.py"
--8<-- "examples/t2_measurement.py"
```
