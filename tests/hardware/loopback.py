"""Hardware loopback test.

Requires measurement cards, therefore not collected by pytest. Run from the repository root:

    python tests/hardware/loopback.py [-v]

The test detects the available TX and RX modules and defines its own device configuration.
The loopback wiring is printed and requires confirmation.
A test sequence with different events is replayed by the TX module and recorded by the RX module.
The result shows the worst value of all channels per metric, copy it into the pull request.
With -v (verbose), the values of all channels are printed and the recorded signals and errors are plotted.

Evaluation
----------
Each channel is compared to a model of the DAC -> ADC transfer function:

    model(t) = gain * transfer(replayed)(t) + offset

where `replayed` is the unrolled sequence from the SequenceProvider and `transfer` applies the sample-and-hold of the
DAC, a 2nd-order low-pass (analog bandwidth) and a delay. The parameters are fitted to the measurement `recorded` by
least squares: the low-pass on the RF channel (applied to all channels), gain, delay and offset per channel.
The error is the deviation of the averaged recording from the model.
Unless stated otherwise, all metrics in % are relative to the designed peak amplitude of the channel.

Metrics used for the loopback test:

    Gain error          Relative deviation of the fitted gain (gain 1.0 corresponds to no gain error)
    Bandwidth           -3 dB bandwidth of the fitted low-pass in MHz
    Offset              Relative output offset of the channel
    Latency             Fitted delay of the RF channel relative to the ADC gate in samples
    Channel skew        Fitted delay of the gradient channels minus fitted delay of the RF channel in samples.
    Noise               RMS of an ADC which only contains noise (after subtracting the offset)
    RMS error           RMS of the error, i.e. averaged recording vs. model, to detect distortion, scaling or shift
    Peak error          Max. absolute error to detect local glitches, e.g. single wrong samples.
    Repetition spread   Max. std. dev. of a sample over all repetitions to detect timing jitter or dropped samples

The test passes if all metrics are within their tolerance, see `TOLERANCES`
"""
import argparse
import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime
from math import ceil, pi
from types import SimpleNamespace
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np
import pypulseq as pp
from scipy.optimize import least_squares
from system_info import RX, TX, CardInfo, SystemInfo, system_info

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import NexusConfiguration, RxConfiguration, SystemLimits, TxConfiguration
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.spcm_control.acquisition_control import AcquisitionControl

# =====================================================================================================================
# Tolerances
# =====================================================================================================================


@dataclass(frozen=True)
class Tolerance:
    """Allowed range of a test value."""

    name: str
    low: float
    high: float
    unit: str  # "%" (value is a fraction), "samples" or "MHz"

    def format(self, value: float, sign: str = "+") -> str:
        """Format a value in the unit of the tolerance, returns "-" if the value is NaN."""
        if np.isnan(value):
            return "-"
        return f"{value:{sign}.2%}" if self.unit == "%" else f"{value:{sign}.2f}"

    def __str__(self) -> str:
        """Return the allowed range, e.g. "±0.50%", "-0.50 ±0.25 samples" or "≥ 4.00 MHz"."""
        unit = "" if self.unit == "%" else f" {self.unit}"
        if self.high == np.inf:
            return f"≥ {self.format(self.low, '')}{unit}"
        center, width = (self.high + self.low) / 2, (self.high - self.low) / 2
        return f"{self.format(center) + ' ' if center else ''}±{self.format(width, '')}{unit}"

    def margins(self, values: np.ndarray) -> np.ndarray:
        """Return the distance of each value to the closer limit: negative if outside, NaN if not evaluated."""
        return np.minimum(values - self.low, self.high - values)


def within(name: str, limit: float, unit: str) -> Tolerance:
    """Return a tolerance for values between -limit and limit."""
    return Tolerance(name, -limit, limit, unit)


GAIN_ERROR = within("Gain error", 0.01, "%")
BANDWIDTH = Tolerance("Bandwidth", 4.0, np.inf, "MHz")
OFFSET = within("Offset", 0.005, "%")
LATENCY = Tolerance("Latency", -0.75, -0.25, "samples")
CHANNEL_SKEW = within("Channel skew", 0.25, "samples")
NOISE = within("Noise", 0.005, "%")
RMS_ERROR = within("RMS error", 0.005, "%")
PEAK_ERROR = within("Peak error", 0.02, "%")
REPETITION_SPREAD = within("Repetition spread", 0.005, "%")
TOLERANCES = (GAIN_ERROR, BANDWIDTH, OFFSET, LATENCY, CHANNEL_SKEW, NOISE, RMS_ERROR, PEAK_ERROR, REPETITION_SPREAD)

# =====================================================================================================================
# Device configuration
# =====================================================================================================================
# The test uses its own device configuration and enabled 4 transmit and receive channels.
# Device paths and total number of available channels are automatically obtained from the detected cards.

SAMPLING_RATE = 20  # Sampling rate of TX and RX in MHz
RANGE: Literal[200] = 200  # TX output and RX input range of channels 0-3 in mV (smallest RX range)
PEAK = 0.8 * RANGE  # Peak amplitude of the RF and gradient waveforms in mV
RF_TO_MVOLT = 0.02  # Conversion of the RF amplitude in mV per Hz
GPA_GAIN = (1.0, 1.5, 2.0)  # Gradient amplifier gain in A/V
GRADIENT_EFFICIENCY = (0.4e-3, 0.45e-3, 0.5e-3)  # Gradient efficiency in T/m/A


def find_cards(system: SystemInfo) -> tuple[CardInfo, CardInfo]:
    """Detect and return the available transmit and receive modules."""
    tx = [card for card in system.cards if card.function == TX]
    rx = [card for card in system.cards if card.function == RX]
    if len(tx) != 1 or len(rx) != 1:
        msg = f"Expected one TX card (analog output) and one RX card (analog input):\n{system}"
        raise SystemExit(msg)
    # The test replays and records the RF and the 3 gradient channels in parallel
    for card in (tx[0], rx[0]):
        if (card.num_channels or 0) < len(CHANNELS):
            msg = f"Loopback test requires {len(CHANNELS)} channels, {card.function} card: {card}"
            raise SystemExit(msg)
    return tx[0], rx[0]


def device_config(tx: CardInfo, rx: CardInfo) -> NexusConfiguration:
    """Return the device configuration of the test for the given cards."""
    num_rx = rx.num_channels or 4  # At least 4, see find_cards
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
        SystemLimits=SystemLimits(
            max_grad=1e5,  # Hz/m, gradients of the test sequence are below 1e4 Hz/m
            max_slew=1e10,  # Hz/m/s, steps of the channel skew pulse within one gradient raster time
            rf_dead_time=20e-6,
            rf_ringdown_time=30e-6,
            adc_dead_time=75e-6,
            block_duration_raster=1e-6,
            rf_raster_time=1e-6,
            grad_raster_time=1e-6,
            adc_raster_time=1e-6,
        ),
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
SKEW_PULSE = 20e-6  # Duration of each polarity of the bipolar pulse for the channel skew in s
RF_DURATION = 200e-6  # RF pulse duration in s
RF_AMP = 1 / RF_DURATION  # Peak RF amplitude in Hz, pypulseq magnitude of a 2 pi block pulse
ADC_DWELL = 10e-6  # ADC dwell time in s
NUM_AVERAGES = 10


def build_sequence(system: pp.Opts, gradient_amplitudes: np.ndarray) -> pp.Sequence:
    """Construct the test sequence, each test case is a block with an ADC covering it, preceded by a delay block.

    ADC gates:
        0. Empty: no output, but ADC gate and phase reference active (noise and crosstalk)
        1. Gradients: one gradient type per channel, shape and sign differ to detect swapped channels
        2. Channel skew: bipolar pulse on all gradient channels (steps size within one gradient raster time).
           The delay fit is weighted by the squared slope, the pulse is used to determine the delay of
           the gradient channels.
        3. All event types in parallel
    """
    seq = pp.Sequence(system=system)
    seq.set_definition("Name", "loopback")

    def add(*events: SimpleNamespace) -> None:
        """Add the events with an ADC covering them, preceded by a delay block."""
        seq.add_block(pp.make_delay(1e-3))
        delay = system.adc_dead_time
        num_samples = ceil((pp.calc_duration(*events) - delay) / ADC_DWELL)
        seq.add_block(*events, pp.make_adc(num_samples, dwell=ADC_DWELL, delay=delay, system=system))

    gx_amp, gy_amp, gz_amp = gradient_amplitudes
    t_arb = (np.arange(n := round(4 * RAMP / system.grad_raster_time)) + 0.5) / n
    gradients = (
        pp.make_trapezoid("x", amplitude=gx_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system),
        pp.make_arbitrary_grad("y", -gy_amp * np.sin(pi * t_arb) ** 2, first=0., last=0., system=system),
        pp.make_extended_trapezoid(
            "z", times=np.array([0., RAMP / 2, 2 * RAMP, 3 * RAMP, 4 * RAMP]),
            amplitudes=gz_amp * np.array([0, .5, 1, -.5, 0]), system=system,
        ),
    )
    step = system.grad_raster_time
    skew_times = RAMP + np.cumsum([0., step, SKEW_PULSE, 2 * step, SKEW_PULSE, step])  # Middle step from +1 to -1
    skew_pulses = [
        pp.make_extended_trapezoid(axis, times=skew_times, amplitudes=amp * np.array([0, 1, 1, -1, -1, 0]),
                                   system=system)
        for axis, amp in zip("xyz", gradient_amplitudes, strict=True)
    ]
    add(pp.make_delay(4 * RAMP))
    add(*gradients)
    add(*skew_pulses, pp.make_delay(skew_times[-1] + SKEW_PULSE))  # Recording continues after the last step
    add(pp.make_block_pulse(2 * pi, duration=RF_DURATION, delay=RAMP, system=system), *gradients)
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
    num_recorded: int  # Number of recorded ADC gates over all repetitions

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
    # Bit 15 of the gradient channels carries ADC gate, phase reference and RF unblanking, RF channel is plain int16
    waveforms = np.vstack([seq[:1], (seq[1:].view(np.uint16) << 1).view(np.int16)])
    output_limits = np.array([unrolled.rf_output_limit, *unrolled.gradient_output_limits])
    replayed = waveforms / np.iinfo(np.int16).max * output_limits[:, None]

    # ADC gates are encoded in bit 15 of channel 1
    edges = np.diff((seq[1].view(np.uint16) >> 15).astype(int), prepend=0, append=0)
    starts, stops = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    gates = list(zip(starts.tolist(), stops.tolist(), strict=True))

    # Check completeness of ADC events
    num_averages = unrolled.parameter.num_averages
    rx_data = sorted(rx_data, key=lambda rx: (rx.average_index, rx.index))
    errors = []
    if len(gates) != num_gates or len(rx_data) != num_gates * num_averages:
        errors.append(f"{len(gates)}/{num_gates} in sequence, {len(rx_data)}/{num_gates * num_averages} recorded")
    else:
        for rx, (start, stop) in zip(rx_data, gates * num_averages, strict=True):
            if rx.raw_data is None or rx.raw_data.shape[-1] != stop - start:
                errors.append(f"Gate {rx.index}, repetition {rx.average_index}: incorrect number of samples")
            elif rx.phase_reference is None or not rx.phase_reference.any():
                errors.append(f"Gate {rx.index}, repetition {rx.average_index}: missing phase reference")
    if errors:
        msg = "\n".join(["Invalid ADC gates:", *errors, "\nResult: FAILED"])
        raise SystemExit(msg)

    # Recordings in mV, ADC gates of each repetition concatenated
    data = [rx.raw_data[:4] * np.asarray(rx.scaling_factor[:4])[:, None] for rx in rx_data]
    recorded = np.array([np.hstack(data[avg * num_gates:(avg + 1) * num_gates]) for avg in range(num_averages)])
    index = np.concatenate([np.arange(start, stop) for start, stop in gates])
    return Measurement(replayed, recorded, index, gates, output_limits, len(rx_data))


# =====================================================================================================================
# Analysis
# =====================================================================================================================
MAX_DELAY = 32  # Max. delay in samples searched by the correlation which provides the start value of the fit


def transfer_function(freq: np.ndarray, delay: float, corner: float, quality: float) -> np.ndarray:
    """Return the DAC -> ADC transfer function, normalized to 1 at DC.

    Product of the sample-and-hold of the DAC (sinc, half a sample delay), a 2nd-order low-pass (`corner`, `quality`)
    and a delay (`delay`, excluding the sample-and-hold).

    Parameters
    ----------
    freq
        Frequencies in cycles per sample, i.e. normalized to the sampling rate (0.5 is the Nyquist frequency).
    delay
        Delay in samples, excluding the half sample of the sample-and-hold. Can be fractional.
    corner
        Corner frequency of the low-pass in cycles per sample, i.e. its natural (undamped) frequency.
        Equals the -3 dB bandwidth only for a Butterworth low-pass, see `bandwidth`.
    quality
        Quality factor of the low-pass: 0.5 is critically damped, 1/sqrt(2) is Butterworth (maximally flat),
        higher values cause a resonance peak at the corner frequency and overshoot in the step response.

    Returns
    -------
        Complex frequency response at `freq`.
    """
    s = 1j * freq / corner
    return np.sinc(freq) * np.exp(-2j * pi * freq * (delay + 0.5)) / (1 + s / quality + s ** 2)


def bandwidth(corner: float, quality: float) -> float:
    """Return the -3 dB bandwidth of the transfer function in cycles per sample, at most the Nyquist frequency (0.5).

    Includes the sample-and-hold of the DAC, the delay does not affect the magnitude.

    Parameters
    ----------
    corner
        Corner frequency of the low-pass in cycles per sample, see `transfer_function`.
    quality
        Quality factor of the low-pass, see `transfer_function`.

    Returns
    -------
        First frequency at which the magnitude drops below 1/sqrt(2), in cycles per sample (resolution 1e-4).
    """
    freq = np.linspace(0, 0.5, 5001)
    below = np.flatnonzero(np.abs(transfer_function(freq, 0, corner, quality)) < np.sqrt(0.5))
    return float(freq[below[0]]) if below.size else 0.5


def latency(delay: float, corner: float, quality: float) -> float:
    """Return the total delay of the transfer function at low frequencies in samples.

    Sum of the delay, half a sample of the sample-and-hold and the group delay of the low-pass at DC.

    Parameters
    ----------
    delay
        Delay in samples, excluding the half sample of the sample-and-hold, see `transfer_function`.
    corner
        Corner frequency of the low-pass in cycles per sample, see `transfer_function`.
    quality
        Quality factor of the low-pass, see `transfer_function`.

    Returns
    -------
        Total delay in samples.
    """
    return delay + 0.5 + 1 / (2 * pi * corner * quality)


def fit_channel(
    replayed: np.ndarray, recorded: np.ndarray, index: np.ndarray, lowpass: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit recorded = gain * transfer(replayed) + offset.

    Return the transfer parameters (delay, corner, quality), gain and offset, and the fitted model.
    The transfer function (`transfer_function`) is applied to the replayed sequence in the frequency domain,
    the model is evaluated at the recorded samples (`index`).
    For given transfer parameters, gain and offset follow from linear least squares.
    Delay and low-pass are fitted by nonlinear least squares, a given `lowpass` (corner, quality) is kept fixed.
    The fit starts at the whole-sample delay of max. correlation, otherwise a shift by several samples would end
    in a wrong period of the RF carrier.
    """
    spectrum, freq = np.fft.rfft(replayed), np.fft.rfftfreq(replayed.size)
    lags = np.arange(-MAX_DELAY, MAX_DELAY + 1)
    start = lags[np.argmax([recorded @ replayed[index - lag] for lag in lags])]

    def model(params: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return transfer parameters, gain and offset, and the model for the fitted parameters."""
        transfer_params = np.array([params[0], *(params[1:] if lowpass is None else lowpass)])
        waveform = np.fft.irfft(spectrum * transfer_function(freq, *transfer_params), replayed.size)[index]
        design = np.column_stack([waveform, np.ones_like(waveform)])
        coefficients = np.linalg.lstsq(design, recorded)[0]
        return transfer_params, coefficients, design @ coefficients

    def residual(params: np.ndarray) -> np.ndarray:
        return model(params)[2] - recorded

    if lowpass is None:  # Fit delay and low-pass, starting at a Butterworth low-pass at 0.3 times the sampling rate
        result = least_squares(residual, [start, 0.3, 0.7], bounds=([-np.inf, 0.02, 0.1], [np.inf, np.inf, 3]))
    else:  # Fit the delay only
        result = least_squares(residual, [start])
    return model(result.x)


def analyze(measurement: Measurement) -> tuple[dict[Tolerance, np.ndarray], np.ndarray]:
    """Evaluate all TOLERANCES per channel, return the values (NaN if not evaluated) and the fitted model."""
    mean = measurement.recorded.mean(axis=0)
    spread = measurement.recorded.std(axis=0, ddof=1)
    values = {tolerance: np.full(4, np.nan) for tolerance in TOLERANCES}
    model = np.empty_like(mean)
    lowpass: np.ndarray | None = None  # Fitted on the RF channel, the gradient waveforms carry no information on it
    rf_delay = 0.
    for ch in range(4):
        transfer_params, (gain, offset), model[ch] = fit_channel(
            measurement.replayed[ch], mean[ch], measurement.index, lowpass,
        )
        values[GAIN_ERROR][ch] = gain - 1
        values[OFFSET][ch] = offset / measurement.output_limits[ch]
        if ch == 0:  # Bandwidth and latency are precise on the RF channel only (carrier and steps)
            lowpass, rf_delay = transfer_params[1:], transfer_params[0]
            values[BANDWIDTH][ch] = bandwidth(*lowpass) * SAMPLING_RATE  # Cycles per sample -> MHz
            values[LATENCY][ch] = latency(*transfer_params)
        else:  # Same low-pass, the delays are comparable
            values[CHANNEL_SKEW][ch] = transfer_params[0] - rf_delay
    empty_gate = measurement.gate_slices[0]
    noise = measurement.recorded[..., empty_gate] - model[:, empty_gate] # Get noise by substracting the fitted offset
    values[NOISE] = np.sqrt(np.mean(noise ** 2, axis=(0, 2))) / measurement.amplitude # Noise scaled by max. ch. amp.
    error = np.abs(mean - model) / measurement.amplitude[:, None]
    values[RMS_ERROR] = np.sqrt(np.mean(error ** 2, axis=1))
    values[PEAK_ERROR] = np.amax(error, axis=1)
    values[REPETITION_SPREAD] = np.amax(spread, axis=1) / measurement.amplitude
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


def print_details(values: dict[Tolerance, np.ndarray], measurement: Measurement) -> None:
    """Print the values of all channels."""
    print("\n---------- Loopback test details ----------")
    print("Channel amplitudes [mV]: " + ", ".join(f"{a:.1f}" for a in measurement.amplitude) + "\n")
    print_table([["Value", *CHANNELS, "Tolerance"]] + [
        [tolerance.name, *(tolerance.format(v) for v in values[tolerance]), str(tolerance)] for tolerance in TOLERANCES
    ])


def print_gates(measurement: Measurement, model: np.ndarray) -> None:
    """Print RMS and peak error per ADC gate and channel, mean ± standard deviation of the repetitions.

    Unlike the test values, the error is evaluated for each repetition and therefore includes its noise.
    """
    error = np.abs(measurement.recorded - model) / measurement.amplitude[:, None]  # (repetitions, 4, samples)
    gates = measurement.gate_slices
    metrics = {  # (gates, repetitions, 4)
        "RMS error": np.array([np.sqrt(np.mean(error[..., gate] ** 2, axis=-1)) for gate in gates]),
        "Peak error": np.array([np.amax(error[..., gate], axis=-1) for gate in gates]),
    }
    for name, metric in metrics.items():
        mean = metric.mean(axis=1)
        std = metric.std(axis=1, ddof=1)
        rows = [
            [str(k), *(f"{m:.2%} ± {s:.2%}" for m, s in zip(gate_mean, gate_std, strict=True))]
            for k, (gate_mean, gate_std) in enumerate(zip(mean, std, strict=True))
        ]
        print(f"\n{name} per ADC gate, mean ± std. dev. of {metric.shape[1]} repetitions:")
        print_table([["ADC gate", *CHANNELS], *rows])


def print_summary(values: dict[Tolerance, np.ndarray], measurement: Measurement, header: str) -> bool:
    """Report the worst value of all channels per test, return True if the test passed."""
    rows = [["Value", "Worst", "Channel", "Tolerance", "Result"]]
    for tolerance in TOLERANCES:
        margins = tolerance.margins(values[tolerance])
        ch = int(np.nanargmin(margins))  # Channel with the value closest to or farthest beyond a limit
        result = "PASS" if margins[ch] >= 0 else "FAIL"
        rows.append([tolerance.name, tolerance.format(values[tolerance][ch]), CHANNELS[ch], str(tolerance), result])
    passed = all(row[-1] == "PASS" for row in rows[1:])

    print("\n---------- Loopback test result (report in PR) ----------")
    print(f"Date: {datetime.now().astimezone():%Y-%m-%d %H:%M UTC%z}")
    print(header)
    repetitions = measurement.recorded.shape[0]
    print(f"Recorded: {measurement.num_recorded}/{len(measurement.gates) * repetitions} ({repetitions} repetitions)\n")
    print_table(rows)
    print(f"\nResult: {'PASSED' if passed else 'FAILED'}\n")
    return passed


def plot_signals(measurement: Measurement, model: np.ndarray, dwell_time: float) -> None:
    """Plot the calculated and recorded waveforms and the error for each channel.

    Two axis per channel:
        1. Signals in mV (replayed, mean recording +/- standard deviation of the repetitions)
        2. Residual (mean recording - fitted model) +/- standard error of the mean (noise) in % of the channel
           amplitude: where the residual leaves the noise band, the model does not fit.
    """
    m = measurement
    mean, spread = m.recorded.mean(axis=0), m.recorded.std(axis=0, ddof=1)
    noise = spread / np.sqrt(m.recorded.shape[0])  # Standard error of the mean
    error, noise_rel = (100 * x / m.amplitude[:, None] for x in (mean - model, noise))
    time = np.arange(m.index.size) * dwell_time * 1e3
    bounds = time[[gate.start for gate in m.gate_slices]]
    peak_limit = 100 * PEAK_ERROR.high

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
        ax_err.plot(time, error[ch], color=color, linewidth=1, label="residual (recorded - fitted model)")
        ax_err.fill_between(time, -noise_rel[ch], noise_rel[ch], color=color, alpha=0.3,
                            label="± standard error of mean (noise)")
        ax_err.hlines([-peak_limit, peak_limit], 0, 1, transform=ax_err.get_yaxis_transform(), color="tab:red",
                      linewidth=0.8, linestyle=":", label="peak error tolerance")
        ax.set_ylabel(f"{name}\n[mV]")
        ax_err.set_ylabel("error\n[%]")
        for a in (ax, ax_err):
            a.grid(alpha=0.3, axis="y")
            a.vlines(bounds, 0, 1, transform=a.get_xaxis_transform(), color="gray", linewidth=0.8)

    # Number each ADC gate on top
    top = axes[0].secondary_xaxis("top")
    top.set_xticks(bounds + np.diff([*bounds, time[-1]]) / 2, [str(k) for k in range(bounds.size)], fontsize=8)
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
    parser = argparse.ArgumentParser(description="Hardware loopback test")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print the values of all channels and plot the measured signals and errors.",
    )
    args = parser.parse_args()

    print(WIRING)
    input("(!) Confirm the wiring and press Enter to start the test...")

    # Cards are opened briefly to read their properties, this is only possible before the acquisition control uses them
    system = system_info()
    config = device_config(*find_cards(system))
    opts = config.system.get_opts()

    with tempfile.TemporaryDirectory() as tmp_dir:

        # Gradient amplitudes in Hz/m for an output of PEAK mV: U[mV] = G[Hz/m] / (gamma * 1e-3 * gpa_gain * efficiency)
        gradient_amplitudes = PEAK * opts.gamma * 1e-3 * np.array(GPA_GAIN) * np.array(GRADIENT_EFFICIENCY)
        sequence = build_sequence(opts, gradient_amplitudes)
        adc_blocks = [k for k in sequence.block_events if sequence.get_block(k).adc is not None]
        parameter = AcquisitionParameter(
            larmor_frequency=SAMPLING_RATE * 1e6 / 10,  # RF carrier at fs/10
            b1_scaling=PEAK / (RF_AMP * RF_TO_MVOLT),  # Peak RF amplitude RF_AMP -> PEAK mV
            num_averages=NUM_AVERAGES,
            state_filepath=tmp_dir,
        )
        acq = AcquisitionControl(configuration=config, console_log_level=logging.WARNING)
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
        print_details(values, measurement)
        print_gates(measurement, model)
    passed = print_summary(values, measurement, str(system))
    if args.verbose:
        print("Preparing plot...")
        plot_signals(measurement, model, unrolled.dwell_time)
        plt.show()
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
