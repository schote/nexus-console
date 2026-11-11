"""Hardware loopback test: TX channels 0-3 are recorded by RX channels 0-3 and compared to the replayed sequence.

Requires measurement cards, therefore not collected by pytest. Run from the repository root:

    python tests/hardware/loopback.py [-p]

With -p, the measured signals and errors are plotted. Copy the block printed under "Loopback test result (report in
PR)" into the pull request.

Procedure:
1. The transmit and receive cards are detected, the test uses its own device configuration (DEVICE CONFIGURATION).
2. A test sequence covering all event types interpreted by the sequence provider is replayed NUM_AVERAGES times.
3. The replayed waveforms (unrolled sequence) and the recordings of all ADC gates are converted to mV.
4. Per channel, gain, delay and offset of the DAC -> ADC chain are fitted over all ADC gates. The delay is also
   fitted per ADC gate to verify the timing of each gate.
5. With these parameters, the error of the averaged recording and the spread of the repetitions are evaluated.
The test passes if all values are within the TOLERANCES below.
"""
import argparse
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from math import ceil, floor, pi
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pypulseq as pp
import yaml
from system_info import RX, TX, CardInfo, SystemInfo, system_info

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import NexusConfiguration, RxConfiguration, SystemLimits, TxConfiguration
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.spcm_control.acquisition_control import AcquisitionControl

# =====================================================================================================================
# Tolerances
# =====================================================================================================================
# Each channel of the DAC (TX) -> ADC (RX) chain is modelled as
#
#     recorded(t) = gain * replayed(t - delay) + offset
#
# with the replayed waveform from the unrolled sequence and the recording averaged over all repetitions, both in mV.
# Gain, delay and offset are fitted per channel over all ADC gates. The error is the deviation of the recording from
# this model, relative to the channel amplitude (peak of the replayed waveform). The tolerances assume precise cards
# (output filters disabled) and short cables:
#
# Gain error                |gain - 1|: conversion between int16 values and mV on TX and RX, including the analog
#                           frequency response, e.g. about -4 % at the RF carrier (fs/10) on a M2p.6546.
# Offset                    |offset| relative to the output range of the channel.
# Delay                     |delay| in samples: latency of the analog paths relative to the digital ADC gate signal,
#                           about -0.66 samples at 20 MHz with 15 cm cables. Coarse bound, the latency is unknown.
# Delay skew                Delay of a channel minus the mean delay of all channels: all channels pass identical
#                           DAC/ADC paths, a skew indicates a shifted channel.
# Gate delay deviation      Max. deviation of the delay fitted per ADC gate from the delay of the channel: a shifted
#                           waveform or ADC gate. Evaluated for gates in which the channel carries a waveform.
# RMS error                 RMS of the error: distorted or scaled waveforms in single gates.
# Peak error                Max. absolute error: local glitches, e.g. single wrong samples.
# Peak error at RF edges    Max. absolute error within EDGE_SAMPLES of the switch-on and switch-off of each RF pulse.
#                           Steps of the RF waveform (e.g. block pulses) are rounded by the analog bandwidth, causing
#                           errors of about 14 % next to the step. These samples are excluded from all other values.
# Repetition spread         Max. standard deviation of a sample over all repetitions: irreproducible replay or
#                           recording, e.g. timing jitter or dropped samples.
#
# In addition, each ADC gate must be recorded in every repetition with the expected number of samples and position.


@dataclass(frozen=True)
class Tolerance:
    """Tolerance of a test value, the absolute value must not exceed the limit."""

    limit: float
    unit: str  # "%" (value is a fraction) or "samples"

    def format(self, value: float) -> str:
        """Format a value in the unit of the tolerance."""
        return f"{value:+.2%}" if self.unit == "%" else f"{value:+.2f}"


TOLERANCES = {
    "Gain error": Tolerance(0.05, "%"),
    "Offset": Tolerance(0.005, "%"),
    "Delay": Tolerance(1.0, "samples"),
    "Delay skew": Tolerance(0.25, "samples"),
    "Gate delay deviation": Tolerance(0.25, "samples"),
    "RMS error": Tolerance(0.01, "%"),
    "Peak error": Tolerance(0.05, "%"),
    "Peak error at RF edges": Tolerance(0.20, "%"),
    "Repetition spread": Tolerance(0.02, "%"),
}
EDGE_SAMPLES = 3  # Samples on both sides of an RF switch-on/off evaluated with the edge tolerance
ACTIVE_THRESHOLD = 0.1  # A channel carries a waveform in an ADC gate if its peak exceeds this fraction of the amplitude

# =====================================================================================================================
# Device configuration
# =====================================================================================================================
# The test uses its own device configuration, only the device paths of the cards depend on the system. TX output and
# RX input ranges are equal and the waveforms use most of it for a high resolution. The conversion factors of RF and
# gradients are arbitrary, but not one and different per channel to verify the conversion to output voltages.
SAMPLING_RATE = 20  # Sampling rate of TX and RX in MHz
RANGE: Literal[200] = 200  # TX output and RX input range of channels 0-3 in mV (smallest RX range)
PEAK = 0.8 * RANGE  # Peak amplitude of the RF and gradient waveforms in mV (gradients are reduced by the FOV scaling)
RF_TO_MVOLT = 0.02  # Conversion of the RF amplitude in mV per Hz
GPA_GAIN = (1.0, 1.5, 2.0)  # Gradient amplifier gain in A/V
GRADIENT_EFFICIENCY = (0.4e-3, 0.45e-3, 0.5e-3)  # Gradient efficiency in T/m/A
SYSTEM_LIMITS = SystemLimits(
    max_grad=1e5,  # Hz/m, gradients of the test sequence are below 1e4 Hz/m
    max_slew=1e9,  # Hz/m/s
    rf_dead_time=20e-6,
    rf_ringdown_time=30e-6,
    adc_dead_time=75e-6,
    block_duration_raster=1e-6,
    rf_raster_time=1e-6,
    grad_raster_time=1e-6,
    adc_raster_time=1e-6,
)


def find_cards(system: SystemInfo) -> tuple[CardInfo, CardInfo]:
    """Return the transmit card (analog output) and the receive card (analog input, at least 4 channels)."""
    tx = [card for card in system.cards if card.function == TX]
    rx = [card for card in system.cards if card.function == RX and (card.num_channels or 0) >= 4]
    if len(tx) != 1 or len(rx) != 1:
        msg = f"Expected one TX card (analog output) and one RX card (analog input, 4+ channels):\n{system}"
        raise SystemExit(msg)
    return tx[0], rx[0]


def device_config(tx: CardInfo, rx: CardInfo) -> NexusConfiguration:
    """Return the device configuration of the loopback test for the given transmit and receive card."""
    num_rx = rx.num_channels or 0
    return NexusConfiguration(
        TxConfiguration=TxConfiguration(
            device_path=tx.path,
            sampling_rate=SAMPLING_RATE,
            channel_max_amplitude=(RANGE,) * 4,
            channel_filter_type=(0,) * 4,  # Output filters would delay the waveforms
            rf_terminated_50ohm=True,
            gradients_terminated_50ohm=True,
            gradient_efficiency=GRADIENT_EFFICIENCY,
            gpa_gain=GPA_GAIN,
            rf_to_mvolt=RF_TO_MVOLT,
        ),
        RxConfiguration=RxConfiguration(
            device_path=rx.path,
            sampling_rate=SAMPLING_RATE,
            max_available_channels=num_rx,
            channel_enable=(True,) * 4 + (False,) * (num_rx - 4),
            channel_max_amplitude=(RANGE,) * num_rx,
            channel_terminated_50ohm=(True,) * num_rx,
        ),
        SystemLimits=SYSTEM_LIMITS,
    )


# =====================================================================================================================
# Test sequence
# =====================================================================================================================
WIRING = """
Loopback test
-------------
Required wiring (RF and gradient amplifiers off/disconnected):
    TX ch0 (RF)              -> RX ch0
    TX ch1 (Gx)              -> RX ch1
    TX ch2 (Gy)              -> RX ch2
    TX ch3 (Gz)              -> RX ch3
    TX X1  (ADC gate)        -> RX X1
    TX X2  (phase reference) -> RX X2
    RX Clk Out               -> TX Clk In
    TX X3  (RF unblanking)   -> not connected
"""
RESTORE_NOTE = "\n(!) NOTE: Restore the default wiring of TX/RX cards, amplifiers and coils before measuring."
CHANNELS = ("ch0 (RF)", "ch1 (Gx)", "ch2 (Gy)", "ch3 (Gz)")
CHANNEL_COLORS = ("tab:blue", "tab:orange", "tab:green", "tab:red")

RAMP = 200e-6  # Gradient ramp time in s
RF_DURATION = 200e-6  # RF pulse duration in s
RF_AMP = 1 / RF_DURATION  # Peak RF amplitude in Hz, pypulseq magnitude of a 2 pi block pulse
NUM_AVERAGES = 10


def build_sequence(system: pp.Opts, gradient_amplitudes: np.ndarray) -> pp.Sequence:
    """Construct the test sequence, each test case is a block with an ADC event."""
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "loopback")
    gx_amp, gy_amp, gz_amp = gradient_amplitudes
    dead_time = system.rf_dead_time

    def add(*events: SimpleNamespace, bw: float = 20e3, adc_delay: float = 0., fit: bool = False,
            separate: bool = True, **adc_kwargs: float) -> None:
        """Add events with an ADC covering them (or fitting into them if `fit` is set), preceded by a delay block."""
        if separate:
            seq.add_block(pp.make_delay(1e-3))
        delay = system.adc_dead_time + adc_delay
        span = pp.calc_duration(*events) - delay
        num_samples = floor((span - system.adc_dead_time) * bw) if fit else ceil(span * bw)
        seq.add_block(*events, pp.make_adc(num_samples, dwell=1 / bw, delay=delay, system=system, **adc_kwargs))

    def peak_normalized(rf: SimpleNamespace) -> SimpleNamespace:
        """Scale an RF pulse to the peak amplitude RF_AMP."""
        rf.signal *= RF_AMP / np.max(np.abs(rf.signal))
        return rf

    # Gradients without and with (channel-individual) delay
    # Oversampled arbitrary gradients are omitted, pypulseq 1.5.0 fails their block duration check.
    t_arb = (np.arange(n := round(4 * RAMP / system.grad_raster_time)) + 0.5) / n
    t_ext = np.array([0., RAMP / 2, 2 * RAMP, 3 * RAMP, 4 * RAMP])
    for d in (0., RAMP):
        # Trapezoid, triangle (zero flat time), asymmetric trapezoid
        add(
            pp.make_trapezoid("x", amplitude=gx_amp, rise_time=RAMP, flat_time=2 * RAMP, delay=d, system=system),
            pp.make_trapezoid("y", amplitude=-gy_amp / 2, rise_time=RAMP, flat_time=0., delay=d / 2, system=system),
            pp.make_trapezoid(
                "z", amplitude=gz_amp, rise_time=RAMP, flat_time=2 * RAMP, fall_time=2 * RAMP, delay=2 * d,
                system=system,
            ),
        )
        # Arbitrary gradients
        add(
            pp.make_arbitrary_grad("x", gx_amp * np.sin(pi * t_arb), first=0., last=0., delay=d, system=system),
            pp.make_arbitrary_grad(
                "y", -gy_amp * np.sin(pi * t_arb) ** 2, first=0., last=0., delay=d / 2, system=system,
            ),
            pp.make_arbitrary_grad("z", gz_amp * np.sin(2 * pi * t_arb), first=0., last=0., delay=2 * d, system=system),
        )
        # Extended trapezoids on non-uniform time raster (first time point defines the delay), conversion to arbitrary
        add(
            pp.make_extended_trapezoid(
                "x", times=t_ext + d, amplitudes=gx_amp * np.array([0, 1, .5, .5, 0]), system=system,
            ),
            pp.make_extended_trapezoid(
                "y", times=t_ext + d / 2, amplitudes=gy_amp * np.array([0, -1, 0, 1, 0]), convert_to_arbitrary=True,
                system=system,
            ),
            pp.make_extended_trapezoid(
                "z", times=t_ext + 2 * d, amplitudes=gz_amp * np.array([0, .5, 1, -.5, 0]), system=system,
            ),
        )
    # Gradients spanning two consecutive blocks (non-zero amplitude at block boundary)
    t_split = np.array([0., RAMP, 2 * RAMP])
    split = tuple(zip("xyz", (gx_amp, -gy_amp, gz_amp), strict=True))
    add(*(pp.make_extended_trapezoid(c, times=t_split, amplitudes=np.array([0, a, a]), system=system)
          for c, a in split), fit=True)
    add(*(pp.make_extended_trapezoid(c, times=t_split, amplitudes=np.array([a, a, 0]), system=system)
          for c, a in split), adc_delay=RAMP / 2, separate=False)

    # RF block pulse (2-point shape) with delay equal to and larger than the dead time
    for d in (dead_time, dead_time + RF_DURATION / 2):
        add(pp.make_block_pulse(2 * pi, duration=RF_DURATION, delay=d, system=system), bw=100e3)
    # RF sinc pulse with frequency and phase offset
    add(peak_normalized(pp.make_sinc_pulse(
        2 * pi, duration=RF_DURATION, delay=dead_time, freq_offset=5e3, phase_offset=pi / 2, system=system,
    )), bw=100e3)
    # Complex arbitrary RF pulse (chirp) with custom dwell time, frequency and phase offset
    add(peak_normalized(pp.make_arbitrary_rf(
        signal=np.exp(1j * np.linspace(-1, 1, round(RF_DURATION / system.rf_raster_time)) ** 2),
        flip_angle=2 * pi,
        delay=dead_time + RF_DURATION / 4,
        freq_offset=-3e3,
        phase_offset=-pi / 4,
        system=system,
    )), bw=100e3)
    # RF overlapping with a gradient (RF unblanking is encoded on the Gz channel)
    add(
        peak_normalized(pp.make_sinc_pulse(2 * pi, duration=RF_DURATION, delay=max(dead_time, RAMP), system=system)),
        pp.make_trapezoid("z", amplitude=gz_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system),
        bw=100e3,
    )

    # ADC with delay, frequency and phase offset (dwell time and dead time are covered by all test cases)
    add(
        pp.make_trapezoid("x", amplitude=gx_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system),
        adc_delay=RAMP / 2, freq_offset=1e3, phase_offset=pi / 3,
    )
    return seq


# =====================================================================================================================
# Data extraction
# =====================================================================================================================

@dataclass
class Measurement:
    """Replayed sequence and recordings in mV, the recorded ADC gates are concatenated along the time axis."""

    replayed: np.ndarray  # Unrolled sequence, shape (4, sequence samples)
    recorded: np.ndarray  # Recordings of all repetitions, shape (repetitions, 4, recorded samples)
    index: np.ndarray  # Position of each recorded sample in the unrolled sequence, shape (recorded samples,)
    gate: np.ndarray  # ADC gate number of each recorded sample, shape (recorded samples,)
    gates: list[tuple[int, int]]  # Start and stop of each ADC gate in the unrolled sequence
    output_limits: np.ndarray  # TX output range per channel in mV, shape (4,)

    @property
    def amplitude(self) -> np.ndarray:
        """Channel amplitude: peak of the replayed waveform within the ADC gates in mV, shape (4,)."""
        return np.amax(np.abs(self.replayed[:, self.index]), axis=1)


def load_measurement(unrolled: UnrolledSequence, rx_data: list[RxData], num_gates: int) -> Measurement:
    """Convert the unrolled sequence and the recordings to mV, abort if an ADC gate was not recorded as expected."""
    seq = unrolled.seq.reshape(-1, 4).T
    # Bit 15 of the gradient channels carries digital signals (ADC gate, phase reference, RF unblanking), shifting
    # left removes it and restores the int16 waveform. The RF channel is a plain int16 waveform.
    waveforms = np.vstack([seq[:1], (seq[1:].view(np.uint16) << 1).view(np.int16)])
    output_limits = np.array([unrolled.rf_output_limit, *unrolled.gradient_output_limits])
    replayed = waveforms / np.iinfo(np.int16).max * output_limits[:, None]

    # ADC gates are encoded in bit 15 of channel 1
    edges = np.diff((seq[1].view(np.uint16) >> 15).astype(int), prepend=0, append=0)
    starts, stops = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    gates = [(int(start), int(stop)) for start, stop in zip(starts, stops, strict=True)]

    # Recording in mV and RX time stamp in samples per (repetition, ADC gate)
    recordings = {
        (rx.average_index, rx.index): (rx.raw_data[:4] * np.asarray(rx.scaling_factor[:4])[:, None],
                                       round(rx.time_stamp / unrolled.dwell_time))
        for rx in rx_data if rx.raw_data is not None and rx.scaling_factor is not None and rx.time_stamp is not None
    }
    num_averages = unrolled.parameter.num_averages
    errors = [] if len(gates) == num_gates else [f"{len(gates)} ADC gates in unrolled sequence, expected {num_gates}"]
    for avg in range(num_averages):
        for k, (start, stop) in enumerate(gates):
            if (avg, k) not in recordings or (avg, 0) not in recordings:
                errors.append(f"ADC gate {k}, repetition {avg}: not recorded")
            elif (num_samples := recordings[avg, k][0].shape[1]) != stop - start:
                errors.append(f"ADC gate {k}, repetition {avg}: {num_samples} samples, expected {stop - start}")
            # RX time stamps have an arbitrary offset per repetition, the distance to the first gate must match
            elif recordings[avg, k][1] - recordings[avg, 0][1] != start - gates[0][0]:
                errors.append(f"ADC gate {k}, repetition {avg}: recorded at a different position")
    if errors:
        msg = "\n".join(["Invalid ADC gates:", *errors, "\nResult: FAILED"])
        raise SystemExit(msg)

    recorded = np.array([np.hstack([recordings[avg, k][0] for k in range(len(gates))]) for avg in range(num_averages)])
    index = np.concatenate([np.arange(start, stop) for start, stop in gates])
    gate = np.repeat(np.arange(len(gates)), [stop - start for start, stop in gates])
    return Measurement(replayed, recorded, index, gate, gates, output_limits)


# =====================================================================================================================
# Analysis
# =====================================================================================================================
FIT_ITERATIONS = 20  # Max. number of iterations of the delay fit
FIT_CONVERGENCE = 1e-4  # The delay fit has converged if the delay update is below this value in samples


def delayed(waveform: np.ndarray, delay: float) -> tuple[np.ndarray, np.ndarray]:
    """Delay a waveform by a fractional number of samples (band-limited interpolation), return it and its slope."""
    omega = 2 * pi * np.fft.rfftfreq(waveform.size)  # Angular frequency in rad per sample
    spectrum = np.fft.rfft(waveform) * np.exp(-1j * omega * delay)
    return np.fft.irfft(spectrum, waveform.size), np.fft.irfft(1j * omega * spectrum, waveform.size)


def fit_channel(replayed: np.ndarray, recorded: np.ndarray, index: np.ndarray, use: np.ndarray,
                delay: float = 0.) -> tuple[float, float, float, np.ndarray]:
    """Fit recorded = gain * replayed(t - delay) + offset, return gain, delay in samples, offset and the model.

    The model is linearized around the current delay estimate (start value `delay`): gain * replayed(t - delay - d)
    is approximately gain * replayed(t - delay) - gain * d * slope(t - delay). The linear least squares fit of gain,
    -gain * d and offset is repeated until the delay update d is negligible (Gauss-Newton). Only the samples in `use`
    are fitted.
    """
    for _ in range(FIT_ITERATIONS):
        waveform, slope = delayed(replayed, delay)
        design = np.column_stack([waveform[index], slope[index], np.ones(index.size)])
        coefficients, *_ = np.linalg.lstsq(design[use], recorded[use])
        gain, update, offset = coefficients[0], -coefficients[1] / coefficients[0], coefficients[2]
        delay += update
        if abs(update) < FIT_CONVERGENCE:
            break
    return gain, delay, offset, design @ coefficients


def rf_edges(measurement: Measurement) -> np.ndarray:
    """Mark the recorded samples within EDGE_SAMPLES of the first and last non-zero RF sample of each ADC gate."""
    mask = np.zeros(measurement.replayed.shape[1], dtype=bool)
    for start, stop in measurement.gates:
        if (rf := np.flatnonzero(measurement.replayed[0, start:stop])).size:
            for edge in start + rf[[0, -1]]:
                mask[edge - EDGE_SAMPLES:edge + EDGE_SAMPLES + 1] = True
    return mask[measurement.index]


def analyze(measurement: Measurement) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """Evaluate all TOLERANCES per channel, return the values, the fitted model and the RF edge mask."""
    m = measurement
    mean, spread = m.recorded.mean(axis=0), m.recorded.std(axis=0, ddof=1)
    amplitude = m.amplitude
    edges = rf_edges(m)
    model = np.empty_like(mean)
    values = {name: np.empty(4) for name in TOLERANCES}
    for ch in range(4):
        gain, delay, offset, model[ch] = fit_channel(m.replayed[ch], mean[ch], m.index, ~edges)
        # Delay per ADC gate in which the channel carries a waveform, relative to the delay of the channel
        deviations = np.array([
            fit_channel(m.replayed[ch], mean[ch], m.index, ~edges & (m.gate == k), delay)[1] - delay
            for k, (start, stop) in enumerate(m.gates)
            if np.amax(np.abs(m.replayed[ch, start:stop])) > ACTIVE_THRESHOLD * amplitude[ch]
        ])
        error = np.abs(mean[ch] - model[ch]) / amplitude[ch]
        values["Gain error"][ch] = gain - 1
        values["Offset"][ch] = offset / m.output_limits[ch]
        values["Delay"][ch] = delay
        values["Gate delay deviation"][ch] = deviations[np.argmax(np.abs(deviations))]
        values["RMS error"][ch] = np.sqrt(np.mean(error[~edges] ** 2))
        values["Peak error"][ch] = np.amax(error[~edges])
        values["Peak error at RF edges"][ch] = np.amax(error[edges], initial=0)
        values["Repetition spread"][ch] = np.amax(spread[ch]) / amplitude[ch]
    values["Delay skew"] = values["Delay"] - np.mean(values["Delay"])
    return values, model, edges


# =====================================================================================================================
# Report and plot
# =====================================================================================================================

def print_report(values: dict[str, np.ndarray], measurement: Measurement, dwell_time: float, header: str) -> bool:
    """Print the test result to be reported in the pull request, return True if the test passed."""
    rows = [["Value", *CHANNELS, "Tolerance", "Result"]]
    passed = True
    for name, tolerance in TOLERANCES.items():
        ok = bool(np.all(np.abs(values[name]) <= tolerance.limit))  # NaN fails
        passed &= ok
        rows.append([name, *(tolerance.format(v) for v in values[name]), tolerance.format(tolerance.limit)[1:],
                     "PASS" if ok else "FAIL"])
    widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
    rows.insert(1, ["-" * w for w in widths])

    print("\n---------- Loopback test result (report in PR) ----------")
    print(f"Date: {datetime.now().astimezone():%Y-%m-%d %H:%M UTC%z}")
    print(header)
    print(f"ADC gates: {len(measurement.gates)}, repetitions: {measurement.recorded.shape[0]}, "
          f"1 sample = {dwell_time * 1e9:.1f} ns")
    print("Channel amplitude [mV]: " + ", ".join(f"{a:.1f}" for a in measurement.amplitude) + "\n")
    for row in rows:
        cells = zip(row, widths, strict=True)
        print("  ".join(cell.ljust(w) if col == 0 else cell.rjust(w) for col, (cell, w) in enumerate(cells)))
    print(f"\nResult: {'PASSED' if passed else 'FAILED'}\n")
    return passed


def plot_signals(measurement: Measurement, model: np.ndarray, edges: np.ndarray, adc_blocks: list[int],
                 dwell_time: float) -> None:
    """Plot the replayed and recorded signals and the error of all channels on a common time axis of all ADC gates.

    Two rows per channel: signals in mV (replayed, mean recording +/- standard deviation of the repetitions) and the
    error (mean recording - fitted model) +/- standard deviation in % of the channel amplitude.
    """
    mean, spread = measurement.recorded.mean(axis=0), measurement.recorded.std(axis=0, ddof=1)
    error, spread_rel = (100 * x / measurement.amplitude[:, None] for x in (mean - model, spread))
    time = np.arange(measurement.index.size) * dwell_time * 1e3
    bounds = time[np.cumsum([0, *(stop - start for start, stop in measurement.gates[:-1])])]
    peak_limit = 100 * TOLERANCES["Peak error"].limit

    fig, axes = plt.subplots(8, 1, sharex=True, figsize=(14, 12), layout="constrained",
                             gridspec_kw={"height_ratios": [2, 1] * 4})
    for ch, (name, color) in enumerate(zip(CHANNELS, CHANNEL_COLORS, strict=True)):
        ax, ax_err = axes[2 * ch], axes[2 * ch + 1]
        label = ch == 0  # Label the artists of the first channel for the legend
        ax.plot(time, measurement.replayed[ch, measurement.index], color=color, linewidth=2.5, alpha=0.4,
                label="replayed (unrolled sequence)" if label else None)
        ax.plot(time, mean[ch], color=color, linewidth=1, linestyle="--",
                label=f"recorded (mean of {measurement.recorded.shape[0]} repetitions)" if label else None)
        ax.fill_between(time, mean[ch] - spread[ch], mean[ch] + spread[ch], color="black", alpha=0.3,
                        label="± standard deviation of repetitions" if label else None)
        ax_err.plot(time, error[ch], color=color, linewidth=1,
                    label="error (recorded - fitted model)" if label else None)
        ax_err.fill_between(time, error[ch] - spread_rel[ch], error[ch] + spread_rel[ch], color="black", alpha=0.3)
        ax_err.plot(time[edges], error[ch, edges], "o", color="gray", markersize=3,
                    label="error at RF edges" if label else None)
        ax_err.axhline(peak_limit, color="tab:red", linewidth=0.8, linestyle=":")
        ax_err.axhline(-peak_limit, color="tab:red", linewidth=0.8, linestyle=":",
                       label="peak error tolerance" if label else None)
        ax.set_ylabel(f"{name}\n[mV]")
        ax_err.set_ylabel("error\n[%]")
        for a in (ax, ax_err):
            a.grid(alpha=0.3, axis="y")
            a.vlines(bounds, 0, 1, transform=a.get_xaxis_transform(), color="gray", linewidth=0.8)

    # Label each gate on top: "<ADC index> (block <block number>)"
    labels = axes[0].secondary_xaxis("top")
    labels.set_xticks(bounds + np.diff([*bounds, time[-1]]) / 2,
                      [f"{k} (block {block})" for k, block in enumerate(adc_blocks)], fontsize=8, rotation=90)
    labels.tick_params(length=0)
    axes[-1].set_xlabel("Concatenated ADC gate time [ms]")
    fig.legend(loc="outside lower left", ncol=6, fontsize=8, frameon=False)


# =====================================================================================================================
# Main
# =====================================================================================================================

def main() -> None:
    """Run the loopback test."""
    parser = argparse.ArgumentParser(description="Hardware loopback test: TX channels 0-3 -> RX channels 0-3.")
    parser.add_argument("-p", "--plot", action="store_true", help="Plot the measured signals and errors.")
    args = parser.parse_args()

    print(WIRING)
    input("(!) Confirm the wiring and press Enter to start the test...")
    # Cards are opened briefly to read their properties, this is only possible before the acquisition control uses them
    system = system_info()
    tx, rx = find_cards(system)

    config = device_config(tx, rx)
    opts = config.system.get_opts()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # The acquisition control loads the device configuration from a file
        config_file = Path(tmp_dir) / "device_config.yaml"
        config_file.write_text(yaml.safe_dump(config.model_dump(mode="json", by_alias=True), sort_keys=False))
        # Gradient amplitudes in Hz/m for an output of PEAK mV: U[mV] = G[Hz/m] / (gamma * 1e-3 * gpa_gain * efficiency)
        gradient_amplitudes = PEAK * opts.gamma * 1e-3 * np.array(GPA_GAIN) * np.array(GRADIENT_EFFICIENCY)
        sequence = build_sequence(opts, gradient_amplitudes)
        adc_blocks = [k for k in sequence.block_events if sequence.get_block(k).adc is not None]
        # Non-unity scalings to cover the scaling of RF and gradient waveforms, RF carrier at fs/10
        parameter = AcquisitionParameter(
            larmor_frequency=SAMPLING_RATE * 1e6 / 10,
            b1_scaling=PEAK / (RF_AMP * RF_TO_MVOLT),  # Peak RF amplitude RF_AMP -> PEAK mV
            fov_scaling=Dimensions(x=0.9, y=0.8, z=0.7),
            num_averages=NUM_AVERAGES,
            state_filepath=tmp_dir,
        )
        acq = AcquisitionControl(configuration_file=str(config_file), console_log_level=logging.WARNING)
        try:
            acq.set_sequence(sequence, parameter)
            data = acq.run(store_unprocessed=True)
            unrolled = acq.sequence
        finally:
            del acq
            print(RESTORE_NOTE)
    if unrolled is None:
        msg = "Sequence could not be unrolled."
        raise SystemExit(msg)

    measurement = load_measurement(unrolled, data.receive_data, len(adc_blocks))
    values, model, edges = analyze(measurement)
    passed = print_report(values, measurement, unrolled.dwell_time, str(system))
    if args.plot:
        print("Preparing plot...")
        plot_signals(measurement, model, edges, adc_blocks, unrolled.dwell_time)
        plt.show()
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
