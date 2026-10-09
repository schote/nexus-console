---
icon: material/cogs
---

# Measurement Cards

Nexus Console relies on two Spectrum Instrumentation PCIe measurement cards. Their roles, pin assignments, and configuration parameters are described below.

## Transmit Card — M2p.6546-x4

The AWG card replays RF and gradient waveforms computed by the [Sequence Provider](../reference/pulseq_interpreter/sequence_provider.md). It operates in FIFO single mode (`SPC_REP_FIFO_SINGLE`), streaming data from a ring buffer in the host memory to the card output in real time.

### Analogue outputs

| Port | Type | Max. output | Function |
|---|---|---|---|
| 0 | Analogue | ±6 V (configurable) | RF waveform, amplitude-modulated at the Larmor frequency f₀ |
| 1 | Analogue | ±6 V (configurable) | Gradient waveform Gx |
| 2 | Analogue | ±6 V (configurable) | Gradient waveform Gy |
| 3 | Analogue | ±6 V (configurable) | Gradient waveform Gz |

The maximum output voltage of each channel is set by the `channel_max_amplitude` field in `TxConfiguration` and must be within the range 1–6000 mV (1 mV resolution).

Channels 1–3 also carry digital control signals encoded in bit 15 of each 16-bit output word. The TX card exposes these digital signals on its auxiliary connectors:

### Digital outputs

| Port | Level | Function |
|---|---|---|
| X0 | 3.3 V | Clock output |
| X1 | 3.3 V | ADC gate signal (bit 15 of Ch 1 / Gx) |
| X2 | 3.3 V | Phase reference signal (bit 15 of Ch 2 / Gy) |
| X3 | 3.3 V | RF unblanking / RFPA enable (bit 15 of Ch 3 / Gz) |

### Clock mode

The TX card is configured with an external clock input (`SPC_CM_EXTERNAL`, 50 Ω termination, 1.5 V threshold). The clock source is the RX card's internal PLL output.

### Output channel filter

Each output channel supports a programmable output filter (`channel_filter_type`, values 0–3). Filter settings are card-version dependent; consult the Spectrum Instrumentation manual for the M2p.6546 series.

---

## Receive Card — M2p.5933-x4

The digitizer card samples NMR signals in gated FIFO mode (`SPC_REC_FIFO_GATE`). It continuously digitises up to eight analogue input channels and stores only the samples that fall within active ADC gate windows, detected via an external trigger signal on its X1 auxiliary input.

### Analogue inputs

| Port | Type | Max. input | Function |
|---|---|---|---|
| 0 | Analogue | ±200 mV – ±10 V (configurable) | Primary RF coil input; bit 15 carries the phase reference (from TX X2) |
| 1–7 | Analogue | ±200 mV – ±10 V (configurable) | Additional RF coil inputs (optional) |

The allowable amplitude range for each channel must be one of: 200, 500, 1000, 2000, 5000, or 10000 mV. This is set via `channel_max_amplitude` in `RxConfiguration`.

!!! note "Phase reference encoding"
    Analogue channel 0 has its most significant bit (bit 15) reserved for the phase reference signal received at the X2 digital input. As a result, channel 0 provides 15-bit effective analogue resolution rather than 16-bit. Channels 1–7 retain full 16-bit resolution.

### Digital inputs

| Port | Level | Function |
|---|---|---|
| Clk In | 3.3 V | External clock input (from RX internal PLL output) |
| X1 | 3.3 V | ADC gate / external trigger (positive edge, from TX X1) |
| X2 | 3.3 V | Phase reference signal (digital input, sampled with Ch 0) |

### Clock mode

The RX card uses its internal PLL as the master clock source (`SPC_CM_INTPLL`) and exports the clock signal on its BNC output (`SPC_CLOCKOUT = 1`). This clock feeds the TX card's external clock input.

### Gated FIFO acquisition

In gated FIFO mode, the card continuously samples data into a 1 GB ring buffer and extracts gate segments triggered by the positive edge on X1 (the ADC gate from the TX card). For each gate, the card records:

- A pre-trigger window (8 samples, fixed) prior to the gate edge.
- The gate itself, whose duration is determined from the timestamp buffer.
- A post-trigger window (4096 // num_active_channels samples) after the gate end.

Gate boundaries are determined from a 64-bit timestamp buffer: each gate is bounded by two consecutive 32-bit timestamps read from the card, and the gate duration is computed as their difference divided by the sample rate.

---

## Device Configuration File

Both cards are configured via a YAML file validated against `NexusConfiguration`. A minimal configuration skeleton:

```yaml
TxConfiguration:
  device_path: "/dev/spcm0"
  sampling_rate: 50          # MHz
  channel_max_amplitude: [200, 6000, 6000, 6000]  # mV, [RF, Gx, Gy, Gz]
  channel_filter_type: [0, 0, 0, 0]
  rf_terminated_50ohm: true
  gradients_terminated_50ohm: false
  gradient_efficiency: [4.0e-4, 4.0e-4, 4.0e-4]  # T/m/A, [x, y, z]
  gpa_gain: [4.7, 4.7, 4.7]                        # V/A, [x, y, z]
  rf_to_mvolt: 8.5e-3        # mV/Hz (Hz → mV conversion factor)

RxConfiguration:
  device_path: "/dev/spcm1"
  sampling_rate: 20          # MHz
  max_available_channels: 8
  channel_enable: [true, false, false, false, false, false, false, false]
  channel_max_amplitude: [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000]  # mV
  channel_terminated_50ohm: [true, true, true, true, true, true, true, true]

SystemLimits:
  max_grad: 8500.0      # Hz/m
  max_slew: 99999.0     # Hz/m/s
  rf_dead_time: 200e-6  # s
  rf_ringdown_time: 20e-6  # s
  adc_dead_time: 10e-6  # s
  block_duration_raster: 1e-6  # s
  rf_raster_time: 1e-6  # s
  grad_raster_time: 1e-6  # s
  adc_raster_time: 1e-6  # s
  B0: 50e-3             # T
```

### Impedance termination

Both TX and RX channels support configurable impedance termination:

- **TX** — `rf_terminated_50ohm` and `gradients_terminated_50ohm`: if a channel is terminated into high impedance (flag `false`), the card's analogue output voltage doubles at the load. The sequence provider and configuration models account for this by halving the effective output limit: `limit = 2 * channel_max_amplitude` when the channel is high-impedance terminated.
- **RX** — `channel_terminated_50ohm`: each receive channel can be terminated into 50 Ω or 1 MΩ (high impedance). Set `true` for 50 Ω (standard coaxial termination).

### Gradient scaling

The gradient waveform amplitude in PyPulseq is defined in Hz/m (gyromagnetic ratio × T/m). The sequence provider converts this to millivolts using:

$$
s(t)\,[\text{mV}] = \frac{s(t)\,[\text{Hz/m}] \times 10^{-3}}{\gamma\,[\text{MHz/T}] \cdot G_\text{gain}\,[\text{V/A}] \cdot \eta_G\,[\text{mT/m/A}]}
$$

where $\gamma = 42.577\,\text{MHz/T}$ is the proton gyromagnetic ratio, $G_\text{gain}$ is the GPA gain, and $\eta_G$ is the gradient coil efficiency. The field-of-view scaling factor $s_\text{FoV}$ and DC offset $\delta$ (both from `AcquisitionParameter`) are then applied:

$$
s_\text{scaled}(t) = s(t) \cdot s_\text{FoV} + \delta
$$

### RF scaling

The RF waveform amplitude in PyPulseq is defined in Hz. The conversion to millivolts is:

$$
s_\text{RF}(t)\,[\text{mV}] = s_\text{RF}(t)\,[\text{Hz}] \cdot \kappa_\text{rf} \cdot \alpha_{B_1}
$$

where $\kappa_\text{rf}$ (`rf_to_mvolt`, in mV/Hz) is a hardware calibration constant and $\alpha_{B_1}$ (`b1_scaling`) is an experiment-specific scaling factor. The result is normalised to `int16` range using the RF channel's output limit.
