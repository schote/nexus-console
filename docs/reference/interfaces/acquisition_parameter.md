# Acquisition Parameter

`AcquisitionParameter` is a mutable, auto-persisting dataclass that carries all experiment-specific parameters required by the [Sequence Provider](../pulseq_interpreter/sequence_provider.md) and the post-processing pipeline. A single global instance (`console.parameter`) is loaded from disk when the package is imported and shared across all experiment scripts within a session.

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

::: console.interfaces.acquisition_parameter.AcquisitionParameter

::: console.interfaces.dimensions.Dimensions

::: console.interfaces.enums.DDCMethod