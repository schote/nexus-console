"""Hardware loopback test of the transmit and receive path.

Requires measurement cards, therefore not collected by pytest. Run from the repository root:

    python tests/loopback.py -d <device_config.yaml>

Without a device configuration, only the wiring and the test sequence are displayed.

A test sequence covering all event configurations interpreted by the sequence provider is played on TX channels 0-3
and recorded on RX channels 0-3. Within each ADC gate, the recorded signals are compared to the unrolled sequence.
"""
import argparse
import logging
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil, floor, pi
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pypulseq as pp

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import NexusConfiguration
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.spcm_control.acquisition_control import AcquisitionControl
from console.utilities.load_configuration import load_nexus_config

EXAMPLE_CONFIG = Path(__file__).parents[2] / "examples" / "example_device_config.yaml"
RAMP = 200e-6   # with flip_angle = 2 pi, pypulseq RF magnitude is 5 kHz
RF_DURATION = 200e-6
GAMMA = 42.58e6 # Hz/T
WIRING = """
[Loopback] Required wiring (RF and gradient amplifiers off/disconnected):
    TX ch0 (RF)              -> RX ch0
    TX ch1 (Gx)              -> RX ch1
    TX ch2 (Gy)              -> RX ch2
    TX ch3 (Gz)              -> RX ch3
    TX X1  (ADC gate)        -> RX X1
    TX X2  (phase reference) -> RX X2
    RX Clk Out               -> TX Clk In
    TX X3  (RF unblanking)   -> not connected
"""
RESTORE_NOTE = "\n[Loopback] NOTE: Restore the default wiring of TX/RX cards, amplifiers and coils before measuring.\n"


@dataclass
class Result:
    """Comparison result of one ADC event."""

    block: int
    average: int
    error: np.ndarray  # Peak difference per channel, relative to the test amplitude
    issues: list[str] = field(default_factory=list)


def git_revision() -> str:
    """Return branch and commit hash of the repository, flagged if tracked files contain uncommitted changes."""
    def git(*args: str) -> str:
        cmd = ["git", "-C", str(Path(__file__).parent), *args]
        return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603

    try:
        dirty = " (uncommitted changes)" if git("status", "--porcelain", "--untracked-files=no") else ""
        return f"{git('rev-parse', '--abbrev-ref', 'HEAD')} @ {git('rev-parse', 'HEAD')}{dirty}"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def check_config(config: NexusConfiguration) -> None:
    """Abort if the device configuration does not allow a loopback measurement."""
    rx, tx = config.rx, config.tx
    prefix = "Error in device configuration:"
    if not all(rx.channel_enable[:4]):
        raise SystemExit(f"{prefix} RX channels 0-3 must be enabled in the device configuration.")
    if not all((*rx.channel_terminated_50ohm[:4], tx.rf_terminated_50ohm, tx.gradients_terminated_50ohm)):
        raise SystemExit(f"{prefix} 50 ohm termination must be enabled for RX channels 0-3 and all TX channels.")


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
                "z", amplitude=gz_amp, rise_time=RAMP, flat_time=2 * RAMP, fall_time=2 * RAMP, delay=2 * d, system=system,
            ),
        )
        # Arbitrary gradients
        add(
            pp.make_arbitrary_grad("x", gx_amp * np.sin(pi * t_arb), first=0., last=0., delay=d, system=system),
            pp.make_arbitrary_grad("y", -gy_amp * np.sin(pi * t_arb) ** 2, first=0., last=0., delay=d / 2, system=system),
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
    for d in (dead_time, dead_time + RAMP / 2):
        add(pp.make_block_pulse(2*pi, duration=RF_DURATION, delay=d, system=system), bw=100e3)
    # RF sinc pulse with frequency and phase offset
    add(pp.make_sinc_pulse(
        2*pi, duration=RF_DURATION, delay=dead_time, freq_offset=5e3, phase_offset=pi/2, system=system
    ), bw=100e3)
    # Complex arbitrary RF pulse (chirp) with custom dwell time, frequency and phase offset
    n_rf_samples = 200
    add(
        pp.make_arbitrary_rf(
            signal=np.exp(1j*np.linspace(-1, 1, n_rf_samples) ** 2),
            flip_angle=2*pi,
            no_signal_scaling=True,
            dwell=RF_DURATION/n_rf_samples,
            delay=dead_time + RAMP / 4,
            freq_offset=-3e3,
            phase_offset=-pi / 4,
            system=system,
        ),
        bw=100e3,
    )
    # RF overlapping with a gradient (RF unblanking is encoded on the Gz channel)
    sinc = pp.make_sinc_pulse(2*pi, duration=RF_DURATION, delay=max(dead_time, RAMP), system=system)
    add(sinc, pp.make_trapezoid("z", amplitude=gz_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system), bw=100e3)

    # ADC with delay, frequency and phase offset (dwell time and dead time are covered by all test cases)
    add(
        pp.make_trapezoid("x", amplitude=gx_amp, rise_time=RAMP, flat_time=2 * RAMP, system=system),
        adc_delay=RAMP / 2, freq_offset=1e3, phase_offset=pi / 3,
    )
    return seq


def evaluate(
    unrolled: UnrolledSequence, rx_data: list[RxData], adc_blocks: list[int], amplitudes: np.ndarray,
) -> list[Result]:
    """Compare recorded data against the waveforms of the unrolled sequence within each ADC gate."""
    seq = unrolled.seq.reshape(-1, 4)
    limits = np.array([unrolled.rf_output_limit, *unrolled.gradient_output_limits])
    replayed = np.column_stack([seq[:, 0], (seq[:, 1:].view(np.uint16) << 1).view(np.int16)]).T / 2**15
    replayed *= limits[:, None]

    # ADC gates are encoded in the 16th bit of channel 1
    edges = np.diff((seq[:, 1].view(np.uint16) >> 15).astype(np.int8), prepend=0, append=0)
    gates = list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1), strict=True))

    results = []
    for rx in rx_data:
        start, stop = gates[rx.index]
        result = Result(adc_blocks[rx.index], rx.average_index, np.full(4, np.nan))
        recorded = rx.raw_data[:4] * np.asarray(rx.scaling_factor[:4])[:, None]
        if recorded.shape[1] != stop - start:
            result.issues.append(f"{recorded.shape[1]}/{stop - start} samples")
        else:
            result.error = np.amax(np.abs(recorded - replayed[:, start:stop]), axis=-1) / amplitudes
        results.append(result)
    return results


def report(results: list[Result], num_expected: int, tolerance: float, device_config: str) -> bool:
    """Print test report and return True if the test passed."""
    errors = np.array([r.error for r in results]) if results else np.full((1, 4), np.nan)
    failed = [r for r in results if r.issues or np.any(r.error > tolerance)]
    passed = not failed and len(results) == num_expected
    print("\n---------- Test report ----------")
    print(f"Date: {datetime.now().astimezone():%Y-%m-%d %H:%M UTC%z}")
    print(f"Revision: {git_revision()}")
    print(f"Device configuration: {device_config}")
    print(f"ADC events: {len(results)}/{num_expected}")
    print(f"Peak difference (relative to test amplitude): mean {100 * np.nanmean(errors):.2f} %, "
          f"max {100 * np.nanmax(errors):.2f} %, tolerance {100 * tolerance:.1f} %")
    for r in failed:
        errs = ", ".join(f"{ch} {100 * e:.1f} %" for ch, e in zip(range(4), r.error, strict=True))
        print(f"  Mismatch {r.run}, block {r.block}, average {r.average}: {errs}"
              + "".join(f"; {issue}" for issue in r.issues))
    print(f"Result: {'PASSED' if passed else 'FAILED'}")
    return passed


def main() -> None:
    """Run the loopback test, or only display the test sequence if no device configuration is given."""
    parser = argparse.ArgumentParser(description="Hardware loopback test: TX channels 0-3 -> RX channels 0-3.")
    parser.add_argument(
        "-d", "--device_config", type=str, default=None,
        help="Path to device configuration. If omitted, the test sequence is displayed (example configuration).",
    )
    parser.add_argument("-t", "--tolerance", type=float, default=0.05, help="Max. relative peak difference.")
    parser.add_argument("-p", "--plot", action="store_true", help="If set, the loopback test sequence is plotted but not executed.")
    args = parser.parse_args()

    config = load_nexus_config(args.device_config or str(EXAMPLE_CONFIG))
    check_config(config)
    print(WIRING)

    # Calculate b1_scaling to set channel 0 output to 25% of maximum
    desired_output_mvolts = 0.25 * np.minimum(
        config.rx.channel_max_amplitude[0], config.tx.channel_max_amplitude[0],
    )
    rf_reference_amp = 1 / RF_DURATION
    b1_scaling = desired_output_mvolts / (rf_reference_amp * config.tx.rf_to_mvolt)
    print(f"Channel 0 amplitude: {desired_output_mvolts} mV (RF amplitude in pypulseq: {round(rf_reference_amp)} Hz)")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Non-unity scalings to cover the scaling of RF and gradient waveforms
        parameter = AcquisitionParameter(
            larmor_frequency=config.tx.sampling_rate * 1e6 / 10,
            b1_scaling=b1_scaling,
            fov_scaling=Dimensions(x=0.9, y=0.8, z=0.7),
            num_averages=10,
            state_filepath=tmp_dir,
        )
        opts = config.system.get_opts()

        # Calculate gradient amplitudes (20% of maximum)
        grad_tx_limits = np.array(config.tx.channel_max_amplitude[1:4])
        grad_amp_mvolts = 0.2 * np.minimum(config.rx.channel_max_amplitude[1:4], grad_tx_limits)
        grad_efficiency = np.array(config.tx.gradient_efficiency)
        grad_amp_hz = grad_amp_mvolts * GAMMA * 1e-3 * np.array(config.tx.gpa_gain) * grad_efficiency
        for k in range(3):
            print(f"Channel {k+1} amplitude: {grad_amp_mvolts[k]} mV ({round(grad_amp_hz[k])} Hz)")

        opts.rf_dead_time = 20e-6
        opts.rf_ringdown_time = 30e-6
        opts.adc_dead_time = 75e-6
        sequence = build_sequence(opts, grad_amp_hz)

        if args.plot:
            # No hardware available: only display the test sequences
            _ = sequence.plot(show_blocks=True, time_disp="ms")
            return

        input("[Loopback] Confirm the wiring and press Enter to start the test...")
        acq = AcquisitionControl(configuration_file=args.device_config, console_log_level=logging.WARNING)
        try:
            # Dead and ringdown times are not stored per event, the sequence provider takes them from its system
            acq.seq_provider.system = sequence.system
            acq.set_sequence(sequence, parameter)
            adc_blocks = [k for k in sequence.block_events if sequence.get_block(k).adc is not None]
            data = acq.run(store_unprocessed=True)
            result = evaluate(acq.sequence, data.receive_data, adc_blocks, amplitudes)
            passed = report(result, NUM_AVERAGES * len(adc_blocks), args.tolerance, args.device_config)
        finally:
            del acq
            print(RESTORE_NOTE)
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
