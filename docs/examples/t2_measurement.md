# T2 Relaxation Measurement

This example measures the transverse relaxation time T2 by acquiring a series of spin-echo signals at varying echo times and fitting the resulting signal decay to a mono-exponential model.

## Physical background

The transverse magnetisation following a 90° excitation pulse decays with time constant T2* due to the combined effects of intrinsic spin–spin relaxation (T2) and static field inhomogeneity. A 180° refocusing pulse in a spin-echo experiment cancels the inhomogeneity contribution, yielding a signal at echo time TE proportional to:

$$
S(\text{TE}) = S_0 \cdot e^{-\text{TE}/T_2} + S_\infty
$$

where $S_0$ is the equilibrium signal amplitude and $S_\infty$ is a constant offset. By acquiring echoes at multiple TE values and fitting this model, T2 can be extracted quantitatively.

## Sequence constructor

The `t2_relaxation.constructor` function generates a multi-TE spin-echo sequence in which all phase-encoding steps are collected consecutively. The phase encoding dimension of the acquisition data corresponds to the different TE values.

| Parameter | Description |
|---|---|
| `echo_time` | Tuple `(TE_min, TE_max)` defining the echo time range (s) |
| `num_steps` | Number of TE values sampled between `TE_min` and `TE_max` |
| `repetition_time` | Repetition time TR between individual spin-echo experiments (s) |
| `rf_duration` | Duration of the rectangular RF pulses (s) |
| `system` | PyPulseq `Opts` system limits |

The constructor returns a tuple `(sequence, te_values)`, where `te_values` is a list of the actual TE values used.

## Step-by-step breakdown

1. **Instantiate `AcquisitionControl`** and **construct the T2 sequence** with the desired TE range and number of steps.
2. **Set acquisition parameters** — at minimum, specify the Larmor frequency and B1 scaling.
3. **Execute the acquisition** — the returned `AcquisitionData` contains one `RxData` entry per TE value, stored in the phase-encoding dimension. If `num_steps = N`, the shape of `processed_data` per receive event is `(num_coils, num_samples)`, and there are N entries in `receive_data`.
4. **Extract peak signal amplitudes** — for each TE, compute the maximum absolute value of the complex signal in the time domain. This is robust to frequency offset and phase drift.
5. **Fit the mono-exponential decay** — use `scipy.optimize.curve_fit` with the model $f(\text{TE}) = A \cdot e^{-\text{TE}/C} + B$.
6. **Visualise** — plot the measured signal points and the fitted decay curve.
7. **Save** — append the fitted T2 and the echo time array to the metadata and save the acquisition data.

## Example script

```python title="examples/t2_measurement.py"
--8<-- "examples/t2_measurement.py"
```

## Interpreting the results

The fitted parameter $C$ is the T2 relaxation time. Typical T2 values for biological tissues at low field (50 mT) range from tens to hundreds of milliseconds, longer than at clinical field strengths because the spectral density of molecular motion is more favourable at low frequencies. The fitted offset $B$ accounts for noise or baseline contributions and should be close to zero for high-SNR measurements.
