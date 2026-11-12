"""Hardware loopback test: TX channels 0-3 are recorded by RX channels 0-3 and compared to the replayed sequence.

Requires measurement cards, therefore not collected by pytest. Run from the repository root:

    python tests/hardware/loopback.py [-v]

The result shows the worst value of all channels per test value, copy it into the pull request. With -v, the values of
all channels are printed in addition and the measured signals and errors are plotted.

Procedure:
1. The transmit and receive cards are detected, the test uses its own device configuration (DEVICE CONFIGURATION).
2. A test sequence covering all event types interpreted by the sequence provider is replayed NUM_AVERAGES times.
3. The replayed waveforms (unrolled sequence) and the recordings of all ADC gates are converted to mV.
4. Per channel, gain, delay, analog bandwidth and offset of the DAC -> ADC chain are fitted over all ADC gates.
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
from scipy.optimize import least_squares
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
#     recorded(t) = gain * chain(replayed)(t) + offset
#
# with the replayed waveform from the unrolled sequence and the recording averaged over all repetitions, both in mV.
# The chain consists of the sample-and-hold of the DAC, a 2nd-order low-pass for the analog bandwidth and a delay. The
# bandwidth attenuates the RF carrier and rounds steps of the waveforms, e.g. the edges of block pulses. The low-pass
# (corner frequency and quality factor) is fitted on the RF channel and applied to all channels, the slow gradient
# waveforms carry no information on it. Gain, delay and offset are fitted per channel over all ADC gates.
# The error is the deviation of the recording from the model, relative to the channel amplitude (peak of the replayed
# waveform). The tolerances assume precise cards (output filters disabled) and short cables:
#
# Gain error                gain - 1 (at DC): conversion between int16 values and mV on TX and RX.
# Bandwidth                 -3 dB bandwidth of the chain in MHz (at most the Nyquist frequency): a degrading analog
#                           path, e.g. an enabled output filter, fails here instead of being absorbed by the fit.
#                           Preliminary minimum, set it from a calibration run.
# Offset                    Offset relative to the output range of the channel.
# Latency                   Total delay of the chain at low frequencies in samples (`latency`), fitted on the RF
#                           channel. It is relative to the digital ADC gate signal and negative if the analog path is
#                           faster than the gate signal. A code change which shifts the replay or acquisition by whole
#                           samples (e.g. the pre-trigger cut) is absorbed by the fit and only changes the latency,
#                           therefore it is compared to EXPECTED_LATENCY. Recalibrate after changing cards, cables or
#                           the sampling rate.
# RMS error                 RMS of the error: distorted, scaled or shifted waveforms in single gates.
# Peak error                Max. absolute error: local glitches, e.g. single wrong samples, or a shifted RF gate.
# Repetition spread         Max. standard deviation of a sample over all repetitions: irreproducible replay or
#                           recording, e.g. timing jitter or dropped samples.
#
# Before, the recording must be complete (every ADC gate in every repetition, no additional ones) and each ADC gate
# must have the expected number of samples and position.


@dataclass(frozen=True)
class Tolerance:
    """Allowed range of a test value."""

    low: float
    high: float
    unit: str  # "%" (value is a fraction), "samples" or "MHz"

    def format(self, value: float, sign: str = "+") -> str:
        """Format a value in the unit of the tolerance, "-" if the value is not evaluated (NaN)."""
        if np.isnan(value):
            return "-"
        return f"{value:{sign}.2%}" if self.unit == "%" else f"{value:{sign}.2f}"

    def __str__(self) -> str:
        """Return the allowed range, e.g. "±0.50%", "-0.66 ±0.50 samples" or "≥ 4.00 MHz"."""
        unit = "" if self.unit == "%" else f" {self.unit}"
        if self.high == np.inf:
            return f"≥ {self.format(self.low, '')}{unit}"
        center, width = (self.high + self.low) / 2, (self.high - self.low) / 2
        return f"{self.format(center) + ' ' if center else ''}±{self.format(width, '')}{unit}"

    def margins(self, values: np.ndarray) -> np.ndarray:
        """Return the distance of each value to the closer limit: negative if outside, NaN if not evaluated."""
        return np.minimum(values - self.low, self.high - values)


def within(limit: float, unit: str) -> Tolerance:
    """Return a tolerance for values between -limit and limit."""
    return Tolerance(-limit, limit, unit)


# Preliminary, measured at 20 MHz with 15 cm cables before the bandwidth was modelled. Confirm with a known-good commit.
EXPECTED_LATENCY = -0.66
TOLERANCES = {
    "Gain error": within(0.03, "%"),
    "Bandwidth": Tolerance(4.0, np.inf, "MHz"),
    "Offset": within(0.005, "%"),
    "Latency": Tolerance(EXPECTED_LATENCY - 0.5, EXPECTED_LATENCY + 0.5, "samples"),  # Any whole-sample shift fails
    "RMS error": within(0.005, "%"),
    "Peak error": within(0.02, "%"),
    "Repetition spread": within(0.02, "%"),
}

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
CHANNELS = ("ch0 (RF)", "ch1 (Gx)", "ch2 (Gy)", "ch3 (Gz)")

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
    gates: list[tuple[int, int]]  # Start and stop of each ADC gate in the unrolled sequence
    output_limits: np.ndarray  # TX output range per channel in mV, shape (4,)

    @property
    def amplitude(self) -> np.ndarray:
        """Channel amplitude: peak of the replayed waveform within the ADC gates in mV, shape (4,)."""
        return np.amax(np.abs(self.replayed[:, self.index]), axis=1)

    @property
    def gate_slices(self) -> list[slice]:
        """Position of each ADC gate in the concatenated recording."""
        stops = np.cumsum([stop - start for start, stop in self.gates]).tolist()
        return [slice(start, stop) for start, stop in zip([0, *stops[:-1]], stops, strict=True)]


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
    gates = list(zip(starts.tolist(), stops.tolist(), strict=True))

    # Recording in mV and RX time stamp in samples per (repetition, ADC gate)
    recordings = {
        (rx.average_index, rx.index): (rx.raw_data[:4] * np.asarray(rx.scaling_factor[:4])[:, None],
                                       round(rx.time_stamp / unrolled.dwell_time))
        for rx in rx_data if rx.raw_data is not None and rx.scaling_factor is not None and rx.time_stamp is not None
    }
    # Completeness: every ADC gate in every repetition, exactly once (the console only warns about missing gates)
    num_averages = unrolled.parameter.num_averages
    expected = {(avg, k) for avg in range(num_averages) for k in range(num_gates)}
    errors = [] if len(gates) == num_gates else [f"{len(gates)} ADC gates in unrolled sequence, expected {num_gates}"]
    if len(rx_data) != len(expected) or recordings.keys() != expected:
        errors.append(f"{len(rx_data)} ADC gates recorded, expected {num_gates} gates x {num_averages} repetitions")
        for avg in range(num_averages):
            if missing := [k for k in range(num_gates) if (avg, k) not in recordings]:
                errors.append(f"Repetition {avg}: " + ("not recorded" if len(missing) == num_gates
                                                       else f"ADC gates {missing} not recorded"))
    if not errors:
        for avg, k in sorted(expected):
            (data, time_stamp), (start, stop) = recordings[avg, k], gates[k]
            if data.shape[1] != stop - start:
                errors.append(f"ADC gate {k}, repetition {avg}: {data.shape[1]} samples, expected {stop - start}")
            # RX time stamps have an arbitrary offset per repetition, the distance to the first gate must match
            elif time_stamp - recordings[avg, 0][1] != start - gates[0][0]:
                errors.append(f"ADC gate {k}, repetition {avg}: recorded at a different position")
    if errors:
        msg = "\n".join(["Invalid ADC gates:", *errors, "\nResult: FAILED"])
        raise SystemExit(msg)

    recorded = np.array([np.hstack([recordings[avg, k][0] for k in range(len(gates))]) for avg in range(num_averages)])
    index = np.concatenate([np.arange(start, stop) for start, stop in gates])
    return Measurement(replayed, recorded, index, gates, output_limits)


# =====================================================================================================================
# Analysis
# =====================================================================================================================
MAX_DELAY = 32  # Max. delay in samples searched by the correlation which provides the start value of the fit


def chain_response(freq: np.ndarray, delay: float, corner: float, quality: float) -> np.ndarray:
    """Frequency response of the DAC -> ADC chain without gain.

    The chain consists of the sample-and-hold of the DAC (sinc, half a sample delay), a 2nd-order low-pass with
    corner frequency and quality factor for the analog bandwidth, and a delay. Frequencies are given in cycles per
    sample (fraction of the sampling rate), the delay in samples.
    """
    s = 1j * freq / corner
    return np.sinc(freq) * np.exp(-2j * pi * freq * (delay + 0.5)) / (1 + s / quality + s ** 2)


def bandwidth(corner: float, quality: float) -> float:
    """Return the -3 dB bandwidth of the chain in cycles per sample, at most the Nyquist frequency (0.5)."""
    freq = np.linspace(0, 0.5, 5001)
    below = np.flatnonzero(np.abs(chain_response(freq, 0, corner, quality)) < np.sqrt(0.5))
    return float(freq[below[0]]) if below.size else 0.5


def latency(delay: float, corner: float, quality: float) -> float:
    """Return the total delay of the chain at low frequencies in samples.

    Sum of the delay, half a sample of the sample-and-hold and the group delay of the low-pass at DC.
    """
    return delay + 0.5 + 1 / (2 * pi * corner * quality)


def fit_channel(
    replayed: np.ndarray, recorded: np.ndarray, index: np.ndarray, lowpass: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit recorded = gain * chain(replayed) + offset.

    Return the chain parameters (delay, corner, quality), gain and offset, and the fitted model. The chain
    (`chain_response`) is applied to the replayed sequence in the frequency domain, the model is evaluated at the
    recorded samples (`index`). For a given chain, gain and offset follow from linear least squares. Delay and low-pass
    are fitted by nonlinear least squares, a given `lowpass` (corner, quality) is kept fixed. The fit starts at the
    whole-sample delay of max. correlation, otherwise a shift by several samples would end in a wrong period of the RF
    carrier.
    """
    spectrum, freq = np.fft.rfft(replayed), np.fft.rfftfreq(replayed.size)
    lags = np.arange(-MAX_DELAY, MAX_DELAY + 1)
    start = lags[np.argmax([recorded @ replayed[index - lag] for lag in lags])]

    def model(params: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return chain parameters, gain and offset, and the model for the fitted parameters."""
        chain = np.array([params[0], *(params[1:] if lowpass is None else lowpass)])
        waveform = np.fft.irfft(spectrum * chain_response(freq, *chain), replayed.size)[index]
        design = np.column_stack([waveform, np.ones_like(waveform)])
        coefficients = np.linalg.lstsq(design, recorded)[0]
        return chain, coefficients, design @ coefficients

    def residual(params: np.ndarray) -> np.ndarray:
        return model(params)[2] - recorded

    if lowpass is None:  # Fit delay and low-pass, starting at a Butterworth low-pass at 0.3 times the sampling rate
        result = least_squares(residual, [start, 0.3, 0.7], bounds=([-np.inf, 0.02, 0.1], [np.inf, np.inf, 3]))
    else:  # Fit the delay only
        result = least_squares(residual, [start])
    return model(result.x)


def analyze(measurement: Measurement) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Evaluate all TOLERANCES per channel, return the values (NaN if not evaluated) and the fitted model."""
    m = measurement
    mean, spread = m.recorded.mean(axis=0), m.recorded.std(axis=0, ddof=1)
    values = {name: np.full(4, np.nan) for name in TOLERANCES}
    model = np.empty_like(mean)
    lowpass: np.ndarray | None = None  # Fitted on the RF channel, the gradient waveforms carry no information on it
    for ch in range(4):
        chain, (gain, offset), model[ch] = fit_channel(m.replayed[ch], mean[ch], m.index, lowpass)
        values["Gain error"][ch] = gain - 1
        values["Offset"][ch] = offset / m.output_limits[ch]
        if ch == 0:  # Bandwidth and latency are precise on the RF channel only (carrier and steps)
            lowpass = chain[1:]
            values["Bandwidth"][ch] = bandwidth(*lowpass) * SAMPLING_RATE  # Cycles per sample -> MHz
            values["Latency"][ch] = latency(*chain)
    error = np.abs(mean - model) / m.amplitude[:, None]
    values["RMS error"] = np.sqrt(np.mean(error ** 2, axis=1))
    values["Peak error"] = np.amax(error, axis=1)
    values["Repetition spread"] = np.amax(spread, axis=1) / m.amplitude
    return values, model


# =====================================================================================================================
# Report and plot
# =====================================================================================================================

def print_table(rows: list[list[str]]) -> None:
    """Print a table with a header row, the first column is left-aligned, the others right-aligned."""
    widths = [max(len(row[col]) for row in rows) for col in range(len(rows[0]))]
    for row in (rows[0], ["-" * w for w in widths], *rows[1:]):
        cells = enumerate(zip(row, widths, strict=True))
        print("  ".join(cell.ljust(w) if col == 0 else cell.rjust(w) for col, (cell, w) in cells))


def print_details(values: dict[str, np.ndarray], measurement: Measurement, dwell_time: float) -> None:
    """Print the values of all channels."""
    print("\n---------- Loopback test details ----------")
    print(f"1 sample = {dwell_time * 1e9:.1f} ns, channel amplitude [mV]: "
          + ", ".join(f"{a:.1f}" for a in measurement.amplitude) + "\n")
    print_table([["Value", *CHANNELS, "Tolerance"]] + [
        [name, *(tolerance.format(v) for v in values[name]), str(tolerance)] for name, tolerance in TOLERANCES.items()
    ])


def print_gates(measurement: Measurement, model: np.ndarray, labels: list[str]) -> None:
    """Print RMS and peak error per ADC gate and channel, mean ± standard deviation of the repetitions.

    Unlike the test values, the error is evaluated for each repetition and therefore includes its noise.
    """
    m = measurement
    error = np.abs(m.recorded - model) / m.amplitude[:, None]  # Shape (repetitions, 4, recorded samples)
    metrics = {  # Per ADC gate, shape (repetitions, 4)
        "RMS error": [np.sqrt(np.mean(error[..., gate] ** 2, axis=-1)) for gate in m.gate_slices],
        "Peak error": [np.amax(error[..., gate], axis=-1) for gate in m.gate_slices],
    }
    for name, gates in metrics.items():
        print(f"\n{name} per ADC gate, mean ± standard deviation of {m.recorded.shape[0]} repetitions:")
        print_table([["ADC gate", *CHANNELS]] + [
            [label, *(f"{mean:.2%} ± {std:.2%}" for mean, std in zip(
                values.mean(axis=0), values.std(axis=0, ddof=1), strict=True))]
            for label, values in zip(labels, gates, strict=True)
        ])


def print_summary(values: dict[str, np.ndarray], measurement: Measurement, header: str) -> bool:
    """Print the worst value of all channels per test value (report in PR), return True if the test passed."""
    rows = [["Value", "Worst", "Channel", "Tolerance", "Result"]]
    for name, tolerance in TOLERANCES.items():
        margins = tolerance.margins(values[name])
        ch = int(np.nanargmin(margins))  # Channel with the value closest to or farthest beyond a limit
        result = "PASS" if margins[ch] >= 0 else "FAIL"
        rows.append([name, tolerance.format(values[name][ch]), CHANNELS[ch], str(tolerance), result])
    passed = all(row[-1] == "PASS" for row in rows[1:])

    print("\n---------- Loopback test result (report in PR) ----------")
    print(f"Date: {datetime.now().astimezone():%Y-%m-%d %H:%M UTC%z}")
    print(header)
    print(f"Recorded: {len(measurement.gates)} ADC gates x {measurement.recorded.shape[0]} repetitions, complete\n")
    print_table(rows)
    print(f"\nResult: {'PASSED' if passed else 'FAILED'}\n")
    return passed


def plot_signals(measurement: Measurement, model: np.ndarray, labels: list[str], dwell_time: float) -> None:
    """Plot the replayed and recorded signals and the error of all channels on a common time axis of all ADC gates.

    Two rows per channel: signals in mV (replayed, mean recording +/- standard deviation of the repetitions) and the
    error (mean recording - fitted model) +/- standard deviation in % of the channel amplitude.
    """
    m = measurement
    mean, spread = m.recorded.mean(axis=0), m.recorded.std(axis=0, ddof=1)
    error, spread_rel = (100 * x / m.amplitude[:, None] for x in (mean - model, spread))
    time = np.arange(m.index.size) * dwell_time * 1e3
    bounds = time[[gate.start for gate in m.gate_slices]]
    peak_limit = 100 * TOLERANCES["Peak error"].high

    fig, axes = plt.subplots(8, 1, sharex=True, figsize=(14, 12), layout="constrained",
                             gridspec_kw={"height_ratios": [2, 1] * 4})
    for ch, name in enumerate(CHANNELS):
        ax, ax_err, color = axes[2 * ch], axes[2 * ch + 1], f"C{ch}"
        ax.plot(time, m.replayed[ch, m.index], color=color, linewidth=2.5, alpha=0.4,
                label="replayed (unrolled sequence)")
        ax.plot(time, mean[ch], color=color, linewidth=1, linestyle="--",
                label=f"recorded (mean of {m.recorded.shape[0]} repetitions)")
        ax.fill_between(time, mean[ch] - spread[ch], mean[ch] + spread[ch], color="black", alpha=0.3,
                        label="± standard deviation of repetitions")
        ax_err.plot(time, error[ch], color=color, linewidth=1, label="error (recorded - fitted model)")
        ax_err.fill_between(time, error[ch] - spread_rel[ch], error[ch] + spread_rel[ch], color="black", alpha=0.3)
        ax_err.hlines([-peak_limit, peak_limit], 0, 1, transform=ax_err.get_yaxis_transform(), color="tab:red",
                      linewidth=0.8, linestyle=":", label="peak error tolerance")
        ax.set_ylabel(f"{name}\n[mV]")
        ax_err.set_ylabel("error\n[%]")
        for a in (ax, ax_err):
            a.grid(alpha=0.3, axis="y")
            a.vlines(bounds, 0, 1, transform=a.get_xaxis_transform(), color="gray", linewidth=0.8)

    # Label each gate on top
    top = axes[0].secondary_xaxis("top")
    top.set_xticks(bounds + np.diff([*bounds, time[-1]]) / 2, labels, fontsize=8, rotation=90)
    top.tick_params(length=0)
    axes[-1].set_xlabel("Concatenated ADC gate time [ms]")
    # The channels share the styles, the legend shows the first channel only
    handles = [*axes[0].get_legend_handles_labels()[0], *axes[1].get_legend_handles_labels()[0]]
    fig.legend(handles=handles, loc="outside lower left", ncol=6, fontsize=8, frameon=False)


# =====================================================================================================================
# Main
# =====================================================================================================================

def main() -> None:
    """Run the loopback test."""
    parser = argparse.ArgumentParser(description="Hardware loopback test: TX channels 0-3 -> RX channels 0-3.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print the values of all channels and plot the measured signals and errors.")
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
        labels = [f"{k} (block {block})" for k, block in enumerate(adc_blocks)]
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
            print("\n(!) NOTE: Restore the default wiring of TX/RX cards, amplifiers and coils before measuring.")
    if unrolled is None:
        msg = "Sequence could not be unrolled."
        raise SystemExit(msg)

    measurement = load_measurement(unrolled, data.receive_data, len(adc_blocks))
    values, model = analyze(measurement)
    if args.verbose:
        print_details(values, measurement, unrolled.dwell_time)
        print_gates(measurement, model, labels)
    passed = print_summary(values, measurement, str(system))
    if args.verbose:
        print("Preparing plot...")
        plot_signals(measurement, model, labels, unrolled.dwell_time)
        plt.show()
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
