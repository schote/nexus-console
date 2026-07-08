# Unrolled Sequence

`UnrolledSequence` is a frozen (immutable) dataclass produced by `SequenceProvider.unroll_sequence`. It carries the complete, hardware-ready representation of a pulse sequence: the interleaved `int16` waveform array for the TX card, the list of `RxData` descriptors for each ADC gate, and hardware metadata that can be used for waveform analysis or debugging.

The `seq` field holds a flat `int16` array of length `4 × sample_count`, with channels interleaved in Fortran order: `[ch0, ch1, ch2, ch3, ch0, ch1, …]`. Bit 15 of channels 1–3 carries the digital control signals (ADC gate, phase reference, RF unblanking).

---

::: console.interfaces.unrolled_sequence.UnrolledSequence
