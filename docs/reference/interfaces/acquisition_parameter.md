# AcquisitionParameter

`AcquisitionParameter` is a mutable, auto-persisting dataclass that carries all experiment-specific parameters required by the [Sequence Provider](../pulseq_interpreter/sequence_provider.md) and the post-processing pipeline. A single global instance (`console.parameter`) is loaded from disk when the package is imported and shared across all experiment scripts within a session.

## Parameter fields

| Field | Type | Default | Description |
|---|---|---|---|
| `larmor_frequency` | `float` | 2.0 × 10⁶ | Proton Larmor frequency in Hz. Must satisfy $f_0 < f_\text{spcm}/2$. |
| `b1_scaling` | `float` | 1.0 | Dimensionless scaling factor for the RF transmit amplitude. |
| `gradient_offset` | `Dimensions` | (0, 0, 0) | DC gradient offsets in mV, applied to channels x, y, z for shimming. |
| `fov_scaling` | `Dimensions` | (1, 1, 1) | Multiplicative scaling of gradient waveforms per axis, used to adjust the effective field of view. |
| `channel_assignment` | `Dimensions` | (1, 2, 3) | Mapping of sequence gradient axes (x, y, z) to TX card output channels (1, 2, 3). Must be a permutation of {1, 2, 3}. |
| `ddc_method` | `DDCMethod` | `FIR` | Decimation filter applied during post-processing. |
| `num_averages` | `int` | 1 | Number of signal averages per acquisition. |
| `averaging_delay` | `float` | 0.0 | Delay in seconds between consecutive averages, e.g. to allow longitudinal magnetisation recovery. |
| `state_filepath` | `str` | `~/nexus-console/acquisition-parameter.state` | Path to the JSON state file. |

## Auto-save mechanism

`AcquisitionParameter` overrides `__setattr__` so that any attribute mutation automatically calls `save()`. The state is serialised to JSON and written to `state_filepath`. Nested `Dimensions` objects register a `_child_changed` callback that triggers the same save when their `x`, `y`, or `z` fields change.

On import, `console.__init__` calls `AcquisitionParameter.load()` to restore the persisted state. If the state file does not exist or is corrupted, a default instance is created.

```python
# Mutating any field auto-saves the state
console.parameter.larmor_frequency = 2.03e6   # immediately written to disk
console.parameter.fov_scaling.x    = 0.95     # nested mutation also auto-saves
```

## Channel assignment

`channel_assignment` decouples the logical gradient axis of a PyPulseq sequence (x, y, z) from the physical TX card output channel (1, 2, 3). This is useful for systems where the physical gradient coil axes are not aligned with the standard imaging axes. The assignment `Dimensions(x=2, y=1, z=3)` would, for example, route the sequence's x-gradient waveform to TX Ch2 (Gy) and the y-gradient to TX Ch1 (Gx).

---

::: console.interfaces.acquisition_parameter
