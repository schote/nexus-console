# From PyPulseq to the Spectrum transmit card

Short developer note on how `SequenceProvider.unroll_sequence` turns a PyPulseq sequence into the
replay buffer of the Spectrum AWG (M2p.6546-x4). Full user documentation:
[`docs/system/sequence-calculation.md`](../../../docs/system/sequence-calculation.md).

## 1. Input: the PyPulseq sequence

A Pulseq sequence (PyPulseq 1.5, or a `.seq` file read with `SequenceProvider.read`) is an ordered list
of **blocks**. Each block has a `block_duration` and at most one event per type:

| Event | PyPulseq type | Attributes used by Nexus |
|---|---|---|
| RF | `rf` | `signal` (complex, Hz), `t`, `shape_dur`, `delay`, `dead_time`, `freq_offset`, `phase_offset` |
| Gradient x/y/z | `trap` | `amplitude` (Hz/m), `rise_time`, `flat_time`, `fall_time`, `delay` |
| Gradient x/y/z | `grad` (arbitrary) | `waveform` (Hz/m), `tt`, `shape_dur`, `delay` |
| ADC | `adc` | `num_samples`, `dwell`, `delay`, `dead_time`, `freq_offset`, `phase_offset` |
| Labels | `label` | copied into the `RxData` of the next ADC event |

Triggers and soft delays are currently ignored.

`SequenceProvider` subclasses `pypulseq.Sequence`, so a sequence is either read from file or copied block
by block with `from_pypulseq`.

## 2. Output: the replay buffer

`UnrolledSequence.seq` is a flat `int16` array of interleaved **frames**, one frame per card sample
($\Delta t = 1/f_s$, 50 ns at 20 MHz):

```text
[RF_0, G1_0, G2_0, G3_0, RF_1, G1_1, G2_1, G3_1, ...]
```

| Channel | Bits 0–14 | Bit 15 (digital output) |
|---|---|---|
| 0 | RF, full 16 bit | – |
| 1 | gradient, 15 bit | ADC gate (X1) |
| 2 | gradient, 15 bit | phase reference (X2) |
| 3 | gradient, 15 bit | RF unblanking (X3) |

Gradient samples are stored as `int16 -> uint16 >> 1` (LSB dropped, full scale unchanged); the digital
signals are then OR-ed into bit 15. Channels are **physical** outputs: the logical axes x/y/z are mapped
to channels 1–3 by `AcquisitionParameter.channel_assignment`.

The buffer is streamed to the card in FIFO mode (`TxCard._fifo_stream_worker`) and replayed once per
average; the card restarts between averages.

## 3. Unrolling algorithm

1. **Checks**: acquisition parameters (Larmor frequency below Nyquist, valid channel assignment) and
   `check_timing()` of the sequence.
2. **Timing grid**: every block duration is rounded to whole frames, `round(t * f_s)`; the cumulative sum
   gives each block's start frame. The total must match the sequence duration, otherwise `IndexError`.
3. **Allocate** `np.zeros(4 * n_frames, int16)`. Everything not covered by an event outputs 0.
4. **Loop over blocks**, each event is computed independently and written at
   `block_start + delay`:
   - **Gradients** (`_calculate_gradient`): amplitude conversion Hz/m → V → int16,
     $q = 32767 \cdot s_\text{FoV} G / (\gamma\, g_\text{GPA}\, \eta\, U_\text{max})$.
     Trapezoids are rebuilt sample by sample (linear ramps), arbitrary gradients are linearly
     interpolated (`np.interp`) on the card raster. Exceeding the output limit raises `ValueError`.
   - **RF** (`_calculate_rf`): complex envelope scaled, FFT-resampled (`scipy.signal.resample`) to the
     card raster, modulated at $f_0 + \Delta f$, real part to int16, optional RFPA LUT. Unblanking bit set
     from `dead_time` before the pulse until its end.
   - **ADC**: gate bit (extended by `dead_time`), 1.095 MHz phase reference bit at the start of the gate,
     and an `RxData` template (sample counts, dwell, offsets, labels).
5. Return an `UnrolledSequence` (buffer + scaling factors + `RxData` list).

Static gradient offsets (shims) are **not** in the buffer: they are set as DC offsets of the card
(`TxCard.set_gradient_offsets`); they only enter the unrolling as a headroom check.

## 4. Properties relevant for waveform corrections (e.g. gradient pre-emphasis)

- Gradients are computed **per block** and written into disjoint slices. A filter with memory (eddy-current
  tails) must therefore act on the **full per-channel waveform after unrolling**, not inside a block.
- The buffer is indexed by **physical channel**, which is where hardware corrections are defined.
- The int16 values of a channel are proportional to the output voltage, i.e. to the gradient current,
  so a linear filter can be applied directly on them (the per-channel scaling only matters for
  cross-channel terms).
- Bit 15 of channels 1–3 must be preserved when a gradient channel is rewritten.
- Memory: 8 bytes per frame (160 MB per second at 20 MHz); a float64 copy of one channel costs
  the same again, so long sequences should be filtered in chunks.
