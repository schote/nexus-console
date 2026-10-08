"""Hardware loopback test.

Requires measurement cards, therefore not collected by pytest. Run from the repository root:

    python tests/hardware/loopback.py -d <device_config.yaml> [-v]

Without a device configuration (or with -s), only the test sequence is displayed.

A test sequence covering all event configurations interpreted by the sequence provider is played on TX channels 0-3
and recorded on RX channels 0-3. The recording of each ADC gate is compared to the unrolled sequence:

1. Extraction: the unrolled sequence is decoded to mV and sliced into ADC gates, the recordings are scaled to mV and
   averaged over all repetitions.
2. Fit: per gate and channel, recorded = gain * replayed(t - delay) + offset is solved by linear least squares.
3. Criteria: timing (gate placement, waveform delay), amplitude (gain, offset), waveform shape (residual) and
   consistency of the repetitions are checked against LIMITS. The test passes if all criteria pass.

Copy the block printed under "Loopback test result (report in PR)" into the pull request.
With -v, the analysis per ADC gate is printed and the signals are plotted.
"""
import argparse
import logging
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil, floor, pi
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pypulseq as pp
from matplotlib.lines import Line2D
from system_info import SystemInfo, system_info

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import NexusConfiguration
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.load_configuration import load_nexus_config

EXAMPLE_CONFIG = Path(__file__).parents[2] / "examples" / "example_device_config.yaml"
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

# Test sequence
RAMP = 200e-6  # Gradient ramp time in s
RF_DURATION = 200e-6  # RF pulse duration in s
RF_AMP = 1 / RF_DURATION  # Peak RF amplitude in Hz, pypulseq magnitude of a 2 pi block pulse
GAMMA = 42.58e6  # Gyromagnetic ratio in Hz/T
NUM_AVERAGES = 10

# Analysis
ACTIVE_THRESHOLD = 0.1  # A channel is active in a gate, if its peak exceeds this fraction of the channel amplitude
# Delays are only evaluated if their standard error is below this value in samples. Slow waveforms (e.g. gradient
# sine lobes) carry little timing information, their delay estimate is dominated by noise.
DELAY_PRECISION = 0.1


@dataclass(frozen=True)
class Limit:
    """Upper limit of a test criterion and its unit for printing."""

    value: float
    unit: str  # "gates", "samples" (of the unrolled sequence) or "%" (fraction)
    description: str

    def format(self, value: float) -> str:
        """Format a value in the unit of the limit."""
        if np.isnan(value):
            return "n/a"
        if self.unit == "%":
            return f"{value:.2%}"
        if self.unit == "samples":
            return f"{value:.2f} smp"
        return f"{value:.0f}"

    def passed(self, value: float) -> bool:
        """Return True if the value is within the limit (NaN fails, i.e. the criterion could not be evaluated)."""
        return bool(value <= self.value)


# All criteria must pass. A timing limit of 0.5 samples detects any shift by one or more samples, the typical result
# of rounding or indexing errors. Relative amplitudes refer to the channel amplitude (peak of the replayed waveform).
LIMITS = {
    "Invalid ADC gates": Limit(0, "gates", "Gates missing or with wrong number of samples or repetitions"),
    "Gate timing": Limit(0.5, "samples", "Gate start on the sequence time line (RX time stamps)"),
    "Waveform timing": Limit(0.5, "samples", "Delay of the waveforms relative to the ADC gate"),
    # Includes the analog frequency response, e.g. about -4 % at the RF carrier (fs/10) on a M2p.6546
    "Gain error": Limit(0.10, "%", "Deviation of the gain from 1, i.e. errors in the conversion to mV"),
    "Gain spread": Limit(0.01, "%", "Gain variation between the gates of a channel"),
    "DC offset": Limit(0.01, "%", "DC offset relative to the TX output range"),
    "Residual RMS": Limit(0.02, "%", "RMS deviation from the fitted model"),
    # Steps in the RF envelope (block pulses) are rounded by the analog bandwidth, causing peaks of a few percent
    "Residual peak": Limit(0.10, "%", "Peak deviation from the fitted model"),
    "Repetition deviation": Limit(0.02, "%", "RMS deviation of single repetitions from their average"),
}


# ---------------------------------------------------------------------------------------------------------------------
# Test setup and sequence
# ---------------------------------------------------------------------------------------------------------------------

def check_config(config: NexusConfiguration) -> None:
    """Abort if the device configuration does not allow a loopback measurement."""
    rx, tx = config.rx, config.tx
    prefix = "Error in device configuration:"
    if not all(rx.channel_enable[:4]):
        raise SystemExit(f"{prefix} RX channels 0-3 must be enabled in the device configuration.")
    if not all((*rx.channel_terminated_50ohm[:4], tx.rf_terminated_50ohm, tx.gradients_terminated_50ohm)):
        raise SystemExit(f"{prefix} 50 ohm termination must be enabled for RX channels 0-3 and all TX channels.")
    if any(tx.channel_filter_type):
        raise SystemExit(f"{prefix} TX output filters delay the waveforms and must be disabled for the loopback test "
                         "(channel_filter_type: [0, 0, 0, 0]).")


def build_sequence(system: pp.Opts, gradient_amplitudes: np.ndarray) -> pp.Sequence:
    """Construct test sequence, each test case is a block with an ADC event."""
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
        add(pp.make_block_pulse(2*pi, duration=RF_DURATION, delay=d, system=system), bw=100e3)
    # RF sinc pulse with frequency and phase offset
    rf = pp.make_sinc_pulse(
        2*pi, duration=RF_DURATION, delay=dead_time, freq_offset=5e3, phase_offset=pi/2, system=system,
    )
    rf.signal *= RF_AMP / np.max(np.abs(rf.signal))
    add(rf, bw=100e3)

    # Complex arbitrary RF pulse (chirp) with custom dwell time, frequency and phase offset
    rf = pp.make_arbitrary_rf(
        signal=np.exp(1j*np.linspace(-1, 1, round(RF_DURATION/system.rf_raster_time)) ** 2),
        flip_angle=2*pi,
        delay=dead_time + RF_DURATION / 4,
        freq_offset=-3e3,
        phase_offset=-pi / 4,
        system=system,
    )
    rf.signal *= RF_AMP / np.max(np.abs(rf.signal))
    add(rf, bw=100e3)
    # RF overlapping with a gradient (RF unblanking is encoded on the Gz channel)
    rf = pp.make_sinc_pulse(2*pi, duration=RF_DURATION, delay=max(dead_time, RAMP), system=system)
    rf.signal *= RF_AMP / np.max(np.abs(rf.signal))
    add(rf, pp.make_trapezoid("z", amplitude=gz_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system), bw=100e3)

    # ADC with delay, frequency and phase offset (dwell time and dead time are covered by all test cases)
    add(
        pp.make_trapezoid("x", amplitude=gx_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system),
        adc_delay=RAMP / 2, freq_offset=1e3, phase_offset=pi / 3,
    )
    return seq


# ---------------------------------------------------------------------------------------------------------------------
# 1. Extraction of replayed and recorded signals per ADC gate
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Gate:
    """Replayed and recorded signals of one ADC gate in mV, arrays have shape (4, num_samples)."""

    index: int  # ADC event index
    block: int  # Block number in the sequence
    start: int  # First sample of the gate in the unrolled sequence
    num_repetitions: int  # Expected number of repetitions (averages)
    reference: np.ndarray  # Replayed waveform, empty if the gate is missing in the unrolled sequence
    repetitions: dict[int, np.ndarray] = field(default_factory=dict)  # Recording per average index
    time_stamps: dict[int, float | None] = field(default_factory=dict)  # RX time stamp in s per average index

    @property
    def valid(self) -> bool:
        """Return True if all repetitions were recorded with the expected number of samples."""
        return len(self.repetitions) == self.num_repetitions and all(
            rep.shape == self.reference.shape for rep in self.repetitions.values()
        )

    @property
    def recorded(self) -> np.ndarray | None:
        """Recording averaged over all repetitions, None if the gate is not valid."""
        return np.mean(list(self.repetitions.values()), axis=0) if self.valid else None


def output_limits(unrolled: UnrolledSequence) -> np.ndarray:
    """TX output range per channel in mV."""
    return np.array([unrolled.rf_output_limit, *unrolled.gradient_output_limits])


def extract_gates(unrolled: UnrolledSequence, rx_data: list[RxData], adc_blocks: list[int]) -> list[Gate]:
    """Extract the replayed waveforms and the recordings of each ADC gate and repetition in mV.

    Returns one gate per ADC event of the sequence, gates missing in the unrolled sequence are empty (invalid).
    """
    seq = unrolled.seq.reshape(-1, 4).T

    # Channel 0 (RF) is a plain int16 value. Gradient channels 1-3 carry a digital signal in the 16th bit
    # (ADC gate, phase reference, RF unblanking), shifting left removes it and restores the int16 waveform.
    reference = np.vstack([seq[:1], (seq[1:].view(np.uint16) << 1).view(np.int16)]) / np.iinfo(np.int16).max
    reference *= output_limits(unrolled)[:, None]

    # ADC gates are encoded in the 16th bit of channel 1
    edges = np.diff((seq[1].view(np.uint16) >> 15).astype(np.int8), prepend=0, append=0)
    bounds = list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True))
    if len(bounds) != len(adc_blocks):
        print(f"Found {len(bounds)} ADC gates in the unrolled sequence, expected {len(adc_blocks)}.")
    bounds += [(0, 0)] * (len(adc_blocks) - len(bounds))

    gates = [
        Gate(k, block, int(start), unrolled.parameter.num_averages, reference[:, start:stop])
        for k, (block, (start, stop)) in enumerate(zip(adc_blocks, bounds, strict=False))
    ]
    for rx in rx_data:
        if rx.index < len(gates):
            gate = gates[rx.index]
            gate.repetitions[rx.average_index] = rx.raw_data[:4] * np.asarray(rx.scaling_factor[:4])[:, None]
            gate.time_stamps[rx.average_index] = rx.time_stamp
    return gates


# ---------------------------------------------------------------------------------------------------------------------
# 2. Fit: recorded = gain * replayed(t - delay) + offset
# ---------------------------------------------------------------------------------------------------------------------

def fit_waveform(reference: np.ndarray, recorded: np.ndarray) -> tuple[float, float, float, float, np.ndarray]:
    """Fit gain, delay and offset of a recording to its replayed waveform.

    For small delays, replayed(t - delay) ~ replayed(t) - delay * replayed'(t). The model is then linear in gain,
    gain * delay and offset and is solved by least squares, the standard error of the delay follows from the
    covariance of the coefficients. The estimate is accurate for delays up to about one sample (RF carrier at fs/10),
    larger delays still yield a large delay estimate, a wrong gain or a large residual.

    Returns delay and its standard error in samples, gain, offset in mV and the residual (recorded - model) in mV.
    """
    design = np.column_stack([reference, np.gradient(reference), np.ones_like(reference)])
    (gain, slope, offset), *_ = np.linalg.lstsq(design, recorded)
    residual = recorded - design @ np.array([gain, slope, offset])
    variance = np.sum(residual ** 2) / max(recorded.size - 3, 1) * np.linalg.pinv(design.T @ design)[1, 1]
    return -slope / gain, np.sqrt(variance) / abs(gain), gain, offset, residual


# ---------------------------------------------------------------------------------------------------------------------
# 3. Test criteria
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Metrics:
    """Analysis results. Arrays have shape (num_gates, 4) per gate and channel, NaN if not applicable."""

    amplitude: np.ndarray  # Channel amplitude in mV: peak magnitude of the replayed waveform over all gates, (4,)
    active: np.ndarray  # Channel carries a waveform in this gate, delay and gain are fitted
    precise: np.ndarray  # Fitted delay is precise enough to be evaluated
    delay: np.ndarray  # Fitted delay in samples
    uncertainty: np.ndarray  # Standard error of the fitted delay in samples
    gain: np.ndarray  # Fitted gain
    offset: np.ndarray  # Fitted DC offset in mV (mean value for inactive channels)
    residual_rms: np.ndarray  # RMS of the residual relative to the channel amplitude
    residual_peak: np.ndarray  # Peak of the residual relative to the channel amplitude
    gate_timing: np.ndarray  # Max. deviation of the gate start over all repetitions in samples, (num_gates,)
    repetition_deviation: np.ndarray  # Max. RMS deviation of a single repetition from the average, (num_gates,)
    checks: dict[str, float]  # Worst value per criterion in LIMITS

    @property
    def passed(self) -> bool:
        """Return True if all criteria passed."""
        return all(LIMITS[name].passed(worst) for name, worst in self.checks.items())


def nan_max(values: np.ndarray) -> float:
    """Maximum ignoring NaN values, NaN if no value is available (i.e. the criterion can not be evaluated)."""
    values = np.asarray(values, dtype=float)
    return float(np.nanmax(values)) if np.any(~np.isnan(values)) else np.nan


def channel_mean(values: np.ndarray) -> np.ndarray:
    """Mean over all gates per channel ignoring NaN values."""
    return np.array([np.mean(v[~np.isnan(v)]) if np.any(~np.isnan(v)) else np.nan for v in values.T])


def gate_timing_error(gate: Gate, first: Gate, dwell_time: float) -> float:
    """Max. deviation of the gate start relative to the first gate over all repetitions in samples.

    The RX time stamps of each repetition have an arbitrary offset (software start of the cards), the distance to the
    first gate of the same repetition must match the distance in the unrolled sequence.
    """
    expected = gate.start - first.start
    deviations = [
        abs((time_stamp - first.time_stamps[rep]) / dwell_time - expected)
        for rep, time_stamp in gate.time_stamps.items()
        if time_stamp is not None and first.time_stamps.get(rep) is not None
    ]
    return max(deviations) if len(deviations) == gate.num_repetitions else np.nan


def analyze(gates: list[Gate], unrolled: UnrolledSequence) -> Metrics:
    """Fit each gate and channel and evaluate all test criteria."""
    valid = np.array([gate.valid for gate in gates], dtype=bool)
    peaks = np.array([np.amax(np.abs(gate.reference), axis=-1, initial=0) for gate in gates]).reshape(-1, 4)
    amplitude = np.amax(peaks, axis=0, initial=0)
    amplitude[amplitude == 0] = np.nan
    active = valid[:, None] & (peaks > ACTIVE_THRESHOLD * amplitude)

    # Fit active channels, inactive channels are expected to be constant (offset only)
    delay, uncertainty, gain, offset, residual_rms, residual_peak = (np.full((len(gates), 4), np.nan) for _ in range(6))
    repetition_deviation = np.full(len(gates), np.nan)
    for k in np.flatnonzero(valid):
        recorded = gates[k].recorded
        residual = np.empty_like(recorded)
        for ch in range(4):
            if active[k, ch]:
                delay[k, ch], uncertainty[k, ch], gain[k, ch], offset[k, ch], residual[ch] = fit_waveform(
                    gates[k].reference[ch], recorded[ch],
                )
            else:
                offset[k, ch] = np.mean(recorded[ch])
                residual[ch] = recorded[ch] - offset[k, ch]
        residual_rms[k] = np.sqrt(np.mean(residual ** 2, axis=-1)) / amplitude
        residual_peak[k] = np.amax(np.abs(residual), axis=-1) / amplitude
        repetition_deviation[k] = max(
            np.amax(np.sqrt(np.mean((rep - recorded) ** 2, axis=-1)) / amplitude)
            for rep in gates[k].repetitions.values()
        )

    precise = active & (uncertainty <= DELAY_PRECISION)
    gate_timing = np.array([gate_timing_error(gate, gates[0], unrolled.dwell_time) for gate in gates])
    checks = {
        "Invalid ADC gates": len(gates) - int(np.sum(valid)),
        "Gate timing": nan_max(gate_timing),
        "Waveform timing": nan_max(np.where(precise, np.abs(delay), np.nan)),
        "Gain error": nan_max(np.abs(gain - 1)),
        "Gain spread": nan_max([nan_max(g) / np.nanmin(g) - 1 for g in gain.T if np.any(~np.isnan(g))]),
        "DC offset": nan_max(np.abs(offset) / output_limits(unrolled)),
        "Residual RMS": nan_max(residual_rms),
        "Residual peak": nan_max(residual_peak),
        "Repetition deviation": nan_max(repetition_deviation),
    }
    return Metrics(amplitude, active, precise, delay, uncertainty, gain, offset, residual_rms, residual_peak,
                   gate_timing, repetition_deviation, checks)


# ---------------------------------------------------------------------------------------------------------------------
# Report and plots
# ---------------------------------------------------------------------------------------------------------------------

def per_channel(values: np.ndarray, fmt: str) -> str:
    """Format one value per channel."""
    formatted = ("n/a" if np.isnan(value) else format(value, fmt) for value in values)
    return ", ".join(f"{name} {value}" for name, value in zip(CHANNELS, formatted, strict=True))


def print_table(title: str, header: list[str], rows: list[list[str]]) -> None:
    """Print a table with right-aligned columns, the first column is left-aligned."""
    widths = [max(len(row[col]) for row in (header, *rows)) for col in range(len(header))]

    def line(row: list[str]) -> str:
        return "  ".join(cell.ljust(w) if col == 0 else cell.rjust(w)
                         for col, (cell, w) in enumerate(zip(row, widths, strict=True)))

    print(f"\n{title}")
    print(line(header))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(line(row))


def print_details(gates: list[Gate], metrics: Metrics) -> None:
    """Print the results per ADC gate (rows) and channel (columns)."""
    print("\n---------- Details per ADC gate ----------")
    print(f"Channel amplitudes [mV]: {per_channel(metrics.amplitude, '.1f')}")

    print_table("Gates", ["ADC (block)", "Repetitions", "Samples", "Gate timing [smp]", "Repetition deviation"], [
        [f"{g.index} ({g.block})", f"{len(g.repetitions)}/{g.num_repetitions}", str(g.reference.shape[1]),
         f"{metrics.gate_timing[k]:.2f}", f"{metrics.repetition_deviation[k]:.2%}"]
        for k, g in enumerate(gates)
    ])

    def channel_table(title: str, cell: Callable[[int, int], str], *, only_active: bool) -> None:
        """Print one value per gate (row) and channel (column), "-" marks inactive channels if `only_active`."""
        rows = []
        for k, gate in enumerate(gates):
            if not gate.valid:
                values = 4 * ["invalid"]
            else:
                values = [cell(k, ch) if metrics.active[k, ch] or not only_active else "-" for ch in range(4)]
            rows.append([f"{gate.index} ({gate.block})", *values])
        print_table(title, ["ADC (block)", *CHANNELS], rows)

    def delay(k: int, ch: int) -> str:
        mark = "" if metrics.precise[k, ch] else "*"
        return f"{metrics.delay[k, ch]:.2f} \u00b1 {metrics.uncertainty[k, ch]:.2f}{mark}"

    def residual(k: int, ch: int) -> str:
        return f"{100 * metrics.residual_rms[k, ch]:.2f} / {100 * metrics.residual_peak[k, ch]:.2f}"

    # Delay and gain are fitted for active channels only, offset and residual are evaluated for all channels
    channel_table("Delay [samples] \u00b1 standard error (* imprecise, not evaluated)", delay, only_active=True)
    channel_table("Gain", lambda k, ch: f"{metrics.gain[k, ch]:.4f}", only_active=True)
    channel_table("Offset [mV]", lambda k, ch: f"{metrics.offset[k, ch]:.2f}", only_active=False)
    channel_table("Residual RMS / peak [% of channel amplitude]", residual, only_active=False)


def print_result(metrics: Metrics, dwell_time: float, system: SystemInfo, device_config: str) -> None:
    """Print the test result to be reported in the pull request."""
    print("\n---------- Loopback test result (report in PR) ----------")
    print(f"Date: {datetime.now().astimezone():%Y-%m-%d %H:%M UTC%z}")
    print(system)
    print(f"Device configuration: {device_config}")
    print_table("Criteria", ["Criterion", "Worst", "Limit", "Result"], [
        [name, LIMITS[name].format(worst), LIMITS[name].format(LIMITS[name].value),
         "PASS" if LIMITS[name].passed(worst) else "FAIL"]
        for name, worst in metrics.checks.items()
    ])
    print(f"\nMean delay [ns]: {per_channel(channel_mean(metrics.delay) * dwell_time * 1e9, '.1f')}")
    print(f"Mean gain: {per_channel(channel_mean(metrics.gain), '.4f')}")
    print(f"Result: {'PASSED' if metrics.passed else 'FAILED'}\n")


def plot_signals(gates: list[Gate], dwell_time: float) -> plt.Figure:
    """Plot replayed (solid) and recorded (dashed) signals of all channels, including channels expected to be zero.

    One row per channel, all ADC gates are concatenated on a common time axis. The recorded signal is the measured
    data averaged over all repetitions, no fit is applied.
    """
    ms_per_sample = dwell_time * 1e3
    bounds = np.cumsum([0] + [gate.reference.shape[1] for gate in gates]) * ms_per_sample
    fig, axes = plt.subplots(4, 1, sharex=True, figsize=(14, 8), layout="constrained")
    axes[-1].set_xlabel("Concatenated ADC gate time [ms]")

    for ch, (ax, name, color) in enumerate(zip(axes, CHANNELS, CHANNEL_COLORS, strict=True)):
        ax.set_ylabel(f"{name}\n[mV]")
        ax.grid(alpha=0.3, axis="y")
        ax.vlines(bounds, 0, 1, transform=ax.get_xaxis_transform(), color="gray", linewidth=0.8)
        for gate, start in zip(gates, bounds, strict=False):
            time = start + np.arange(gate.reference.shape[1]) * ms_per_sample
            ax.plot(time, gate.reference[ch], color=color, linewidth=2.5, alpha=0.4)
            if gate.valid:
                ax.plot(time, gate.recorded[ch], color=color, linewidth=1, linestyle="--")

    # Label each gate on top of the first row: "<ADC index> (block <block number>)", "!" marks invalid gates
    labels = axes[0].secondary_xaxis("top")
    labels.set_xticks((bounds[:-1] + bounds[1:]) / 2,
                      [f"{g.index} (block {g.block})" + ("" if g.valid else " !") for g in gates],
                      fontsize=8, rotation=90)
    labels.tick_params(length=0)

    num_repetitions = gates[0].num_repetitions if gates else 0
    fig.legend(handles=[
        Line2D([], [], color="gray", linewidth=2.5, alpha=0.4, label="replayed (unrolled sequence)"),
        Line2D([], [], color="gray", linewidth=1, linestyle="--",
               label=f"recorded (average of {num_repetitions} measurements)"),
    ], loc="outside lower left", ncol=2, fontsize=8, frameon=False)
    return fig


# ---------------------------------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------------------------------

def test_amplitudes(config: NexusConfiguration, *, verbose: bool) -> tuple[float, np.ndarray]:
    """Return the B1 scaling and the gradient amplitudes in Hz/m of the test sequence.

    RF is played at 50 %, gradients at 20 % of the smaller TX and RX channel range.
    """
    rf_amp_mvolts = 0.5 * min(config.rx.channel_max_amplitude[0], config.tx.channel_max_amplitude[0])
    b1_scaling = rf_amp_mvolts / (RF_AMP * config.tx.rf_to_mvolt)
    grad_amp_mvolts = 0.2 * np.minimum(config.rx.channel_max_amplitude[1:4], config.tx.channel_max_amplitude[1:4])
    grad_amp_hz = (grad_amp_mvolts * GAMMA * 1e-3 * np.array(config.tx.gpa_gain)
                   * np.array(config.tx.gradient_efficiency))
    if verbose:
        print(f"Channel 0 amplitude: {rf_amp_mvolts} mV (RF amplitude in pypulseq: {round(RF_AMP)} Hz)")
        for k in range(3):
            print(f"Channel {k + 1} amplitude: {grad_amp_mvolts[k]} mV ({round(grad_amp_hz[k])} Hz)")
    return b1_scaling, grad_amp_hz


def main() -> None:
    """Run the loopback test, or only display the test sequence if no device configuration is given."""
    parser = argparse.ArgumentParser(description="Hardware loopback test: TX channels 0-3 -> RX channels 0-3.")
    parser.add_argument(
        "-d", "--device_config", type=str, default=None,
        help="Path to device configuration. If omitted, the test sequence is displayed (example configuration).",
    )
    parser.add_argument(
        "-s", "--seq_plot", action="store_true",
        help="If set, the loopback test sequence is plotted but not executed.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Print the analysis per ADC gate and plot the signals.",
    )
    args = parser.parse_args()
    run_test = args.device_config is not None and not args.seq_plot

    config = load_nexus_config(args.device_config or str(EXAMPLE_CONFIG))
    if run_test:
        check_config(config)
        print(WIRING)

    b1_scaling, grad_amp_hz = test_amplitudes(config, verbose=args.verbose)
    opts = config.system.get_opts()
    opts.rf_dead_time = 20e-6
    opts.rf_ringdown_time = 30e-6
    opts.adc_dead_time = 75e-6
    sequence = build_sequence(opts, grad_amp_hz)

    if not run_test:
        print("Preparing sequence plot...")
        sequence.plot(show_blocks=True, time_disp="ms")
        return

    input("\nConfirm the wiring and press Enter to start the test...")
    # Cards are opened briefly to read their models, this is only possible before the acquisition control uses them
    system = system_info()
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Non-unity scalings to cover the scaling of RF and gradient waveforms
        parameter = AcquisitionParameter(
            larmor_frequency=config.tx.sampling_rate * 1e6 / 10,
            b1_scaling=b1_scaling,
            fov_scaling=Dimensions(x=0.9, y=0.8, z=0.7),
            num_averages=NUM_AVERAGES,
            state_filepath=tmp_dir,
        )
        acq = AcquisitionControl(configuration_file=args.device_config, console_log_level=logging.WARNING)
        try:
            # Dead and ringdown times are not stored per event, the sequence provider takes them from its system
            acq.seq_provider.system = sequence.system
            acq.set_sequence(sequence, parameter)
            adc_blocks = [k for k in sequence.block_events if sequence.get_block(k).adc is not None]
            data = acq.run(store_unprocessed=True)
            unrolled = acq.sequence
            gates = extract_gates(unrolled, data.receive_data, adc_blocks)
        finally:
            del acq
            print(RESTORE_NOTE)

    metrics = analyze(gates, unrolled)
    if args.verbose:
        print_details(gates, metrics)
    print_result(metrics, unrolled.dwell_time, system, args.device_config)

    if args.verbose:
        print("Preparing plots...")
        plot_signals(gates, unrolled.dwell_time)
        plt.show()

    raise SystemExit(0 if metrics.passed else 1)


if __name__ == "__main__":
    main()
