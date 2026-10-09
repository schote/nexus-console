# 3D Turbo Spin-Echo

`tse_3d` constructs a three-dimensional turbo spin-echo (TSE) sequence with configurable echo train length, k-space trajectory, and phase encoding dimensions. It also provides the `sort_kspace` function for reordering raw acquisition data into the correct k-space positions using the PyPulseq labels embedded in each ADC event. See the [3D TSE example](../../../../examples/tse_3d.md) for a complete acquisition and reconstruction workflow.

---

::: console.utilities.sequences.tse.tse_3d
