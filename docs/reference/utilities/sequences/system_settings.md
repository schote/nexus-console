# System Settings

`system_settings` provides the PyPulseq `Opts` object that defines global MRI system hardware limits (maximum gradient amplitude, slew rate, RF dead/ringdown times, raster times) used by all built-in sequence constructors in `console.utilities.sequences`. The limits are derived from the `SystemLimits` section of the device configuration file.

---

::: console.utilities.sequences.system_settings
