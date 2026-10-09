# Spin-Echo Spectrum

`se_spectrum` constructs a spin-echo spectrum sequence: a 90° excitation pulse followed by a 180° refocusing pulse at TE/2, with an ADC gate centred on the echo. The spin-echo refocuses static field inhomogeneity, yielding a T2-limited line width rather than the broader T2*-limited line of an FID. An optional FID readout before the refocusing pulse can be enabled.

---

::: console.utilities.sequences.spectrometry.se_spectrum
