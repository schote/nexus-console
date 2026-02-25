"""Sequence provider class."""
import logging
from collections.abc import Callable
from math import floor
from types import SimpleNamespace
from typing import Any
import tempfile
from multiprocessing import Pool
from dataclasses import asdict

import numpy as np
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence
from scipy.signal import resample

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.waveform_calculator import WaveformConfig, calculate_block

try:
    from line_profiler import profile
except ImportError:
    def profile(func: Callable[..., Any]) -> Callable[..., Any]:
        """Define placeholder for profile decorator."""
        return func

NUM_REFERENCE_SAMPLES = 1000
REFERENCE_FREQUENCY = 1.095e6


class SequenceProvider(Sequence):
    """Sequence provider class.

    This object is inherited from pulseq sequence object, so that all methods of the
    pypulseq ``Sequence`` object can be accessed.

    The main functionality of the ``SequenceProvider`` is to unroll a given pulseq sequence.
    Usually the first step is to read a sequence file. The unrolling step can be achieved using
    the ``unroll_sequence()`` function.

    Example
    -------
    >>> seq_provider = SequenceProvider()
    >>> seq_provider.read("./seq_file.seq")
    >>> unrolled = seq_provider.unroll_sequence(acquisition_parameter)
    """

    __name__: str = "SequenceProvider"

    def __init__(
        self,
        gradient_efficiency: tuple[float, float, float],
        gpa_gain: tuple[float, float, float],
        gradient_output_limits: tuple[int, int, int],
        gradients_50ohms: bool,
        rf_output_limit: int,
        rf_50ohms: bool,
        rf_to_mvolt: float,
        spcm_dwell_time: float,
        system: Opts,
        system: Opts,
    ):
        """Initialize sequence provider class which is used to unroll a pulseq sequence.

        Parameters
        ----------
        gradient_efficiency
            Efficiency of the gradient coils in mT/m/A, e.g. [0.4e-3, 0.4e-3, 0.4e-3].
        gpa_gain
            Gain factor of the GPA per gradient channel, e.g. [4.7, 4.7, 4.7].
        gradient_output_limits
            Integer output limit per gradient channel in mV, e.g. [6000, 6000, 6000].
        gradients_50ohms
            Boolean flag which indicates if the gradient output is terminated into 50 ohms or high impedance.
            If terminated into high impedance, the card output doubles,
            what needs to be considered when calculating the sequence.
        rf_output_limit
            Integer output limit of the RF channel in mV.
        rf_50ohms
            Boolean flag which indicates if the rf output is terminated into 50 ohms (see gradients_50ohms).
        rf_to_mvolt, optional
            Translation of RF waveform from pulseq (Hz) to mV.
        spcm_dwell_time, optional
            Sampling time raster of the output waveform (depends on spectrum card).
        system_limits
            Absolute maximum system limits defined in the device configuration.
            Used to instantiate the pypulseq `Opts()` class.
        """
        if not isinstance(system, Opts):
            raise AttributeError("Invalid system: Pypulseq `Opts` definition required.")
        super().__init__(system=system)
        self.log = logging.getLogger("SeqProv")

        # Scale output limit dependent on high impedance flags:
        # If output is terminated into high impedance (flag is true), the channel output is doubled.
        # Otherwise, if output is terminated into 50 ohms impedance, output limit remains unchanged.
        rf_out_limit = rf_output_limit if rf_50ohms else int(2 * rf_output_limit)
        # Ensure tuple[int, int, int] for mypy typing
        gradient_out_limits = (
            gradient_output_limits[0] if gradients_50ohms else int(2 * gradient_output_limits[0]),
            gradient_output_limits[1] if gradients_50ohms else int(2 * gradient_output_limits[1]),
            gradient_output_limits[2] if gradients_50ohms else int(2 * gradient_output_limits[2]),
        )

        # Configuration for calculator
        self.waveform_config = WaveformConfig(
            spcm_dwell_time=spcm_dwell_time,
            rf_to_mvolt=rf_to_mvolt,
            gpa_gain=gpa_gain,
            grad_eff=gradient_efficiency,
            rf_out_limit=rf_out_limit,
            gradient_out_limits=gradient_out_limits,
            gamma=self.system.gamma,
        )

        # Setup phase reference signal
        time = np.arange(NUM_REFERENCE_SAMPLES) * spcm_dwell_time
        signal = np.exp(2j * np.pi * REFERENCE_FREQUENCY * time)
        self.phase_reference = np.zeros(NUM_REFERENCE_SAMPLES, dtype=np.uint16)
        self.phase_reference[signal > 0] = np.uint16(2**15)

    # -------- PyPulseq interface -------- #

    def from_pypulseq(self, seq: Sequence) -> None:
        """Read a pypulseq sequence to sequence provider.
        """Read a pypulseq sequence to sequence provider.

        Parameters
        ----------
        seq
            Pypulseq ``Sequence`` instance

        Raises
        ------
        AttributeError
        AttributeError
            seq is not a valid pypulseq ``Sequence`` instance
        """
        if not isinstance(seq, Sequence):
            raise AttributeError("Invalid sequence.")
        # Re-initialize the parent to start from a clean pypulseq sequence
        super().__init__(system=self.system)
        for block_index, _ in seq.block_events.items():
            block = seq.get_block(block_index)
            self.add_block(block)
        # Set definitions
        self.definitions = seq.definitions
        """
        if not isinstance(seq, Sequence):
            raise AttributeError("Invalid sequence.")
        # Re-initialize the parent to start from a clean pypulseq sequence
        super().__init__(system=self.system)
        for block_index, _ in seq.block_events.items():
            block = seq.get_block(block_index)
            self.add_block(block)
        # Set definitions
        self.definitions = seq.definitions

    def to_pypulseq(self) -> Sequence | None:
        """Create a pypulseq sequence from sequence provider."""
        seq = Sequence(system=self.system)
        for block_index, _ in self.block_events.items():
            block = self.get_block(block_index)
            seq.add_block(block)
        seq.definitions = self.definitions
        """Create a pypulseq sequence from sequence provider."""
        seq = Sequence(system=self.system)
        for block_index, _ in self.block_events.items():
            block = self.get_block(block_index)
            seq.add_block(block)
        seq.definitions = self.definitions
        return seq

    # -------- Public interface -------- #

    def dict(self) -> dict:
        """Abstract method which returns variables for logging in dictionary."""
        return {
            "system": vars(self.system),
            "config": asdict(self.waveform_config),
        }

    @profile
    def unroll_sequence(self, parameter: AcquisitionParameter, num_processes: int = 1) -> UnrolledSequence:
        """Unroll the pypulseq sequence description.

        Parameters
        ----------
        parameter
            Instance of AcquisitionParameter containing all necessary parameters to
            calculate the sequence waveforms, i.e. larmor frequency, gradient offsets, etc.
        num_processes
            Number of processes to use for parallel calculation. Default is 1 (sequential).
            If > 1, multiprocessing is used.

        Returns
        -------
                signal encoded by 15th bit. Only the RF channel does not contain a digital signal.
                In addition, all receive events are described and returned in a list within the unrolled
                sequence object.
        """
        try:
            self._check_parameter(parameter)
            self._check_sequence()
        except Exception:
            self.log.exception("Checks not passed")
            raise

        spcm_dwell = self.waveform_config.spcm_dwell_time

        # Get list of all events and list
        events_list = self.block_events
        # Calculate sequence duration and number of samples
        seq_duration, _, _ = self.duration()
        seq_samples = round(seq_duration / spcm_dwell)
        # Calculate the start time (and sample position) and duration of each block
        block_durations = np.array(
            [self.get_block(block_idx).block_duration for block_idx in list(events_list.keys())]
        )
        block_samples = np.round(block_durations / spcm_dwell).astype(int)
        block_pos = np.cumsum(block_samples, dtype=np.int64)
        block_pos = np.insert(block_pos, 0, 0)

        if seq_samples != block_pos[-1]:
            # Adjust if simple rounding error
            if abs(seq_samples - block_pos[-1]) <= 1:
                seq_samples = block_pos[-1]
            else:
                msg = "Number of sequence samples does not match total number of block samples"
                raise IndexError(msg)

        # Create temporary file for memmap and resize
        self._temp_file = tempfile.NamedTemporaryFile(delete=True)
        self._temp_file.truncate(4 * seq_samples * 2)  # 2 bytes per int16
        # Create memmap
        _seq = np.memmap(
            self._temp_file.name, dtype=np.int16, mode="r+", shape=(4 * seq_samples,)
        )

        _rx_data = []
        adc_count: int = 0
        labels = {}
        tasks = []

        for event_idx, (event_key, event) in enumerate(events_list.items()):
            block = self.get_block(event_key)
            current_block_pos = block_pos[event_idx]
            waveform_start = current_block_pos * 4

            # Handle Labels
            if block.label is not None:
                for label in block.label.values():
                    labels[label.label] = label.value

            # Handle ADC (Metadata + Gate)
            if block.adc is not None:
                # Calculate the number of samples to be discarded from the decimated signal
                num_samples_discard = floor(block.adc.dead_time / block.adc.dwell)
                # Calculate the total gate duration, given by number of samples
                # and two times the number of discarded samples for symmetric adc dead time
                # Note: The total gate duration is only increased if the dead time is a multiple of the adc dwell time.
                total_gate_duration = (block.adc.num_samples + 2 * num_samples_discard) * block.adc.dwell
                num_samples_raw = round(total_gate_duration / spcm_dwell)

                # Remaining delay = dead_time minus pre- and post-sampling fractions
                remaining_delay = block.adc.dead_time - num_samples_discard * block.adc.dwell
                num_delay_samples = round(remaining_delay / spcm_dwell)

                adc_start = (current_block_pos + num_delay_samples) * 4
                adc_end = (current_block_pos + num_delay_samples + num_samples_raw) * 4

                # Add ADC gate to 16th bit of output channel 1 (first gradient channel)
                _seq[slice(adc_start + 1, adc_end + 1, 4)] |= np.uint16(2**15)

                # Add phase reference signal to 16th bit of output channel 2 (second gradient channel)
                num_samples_reference = min(num_samples_raw, self.phase_reference.size)
                phase_ref_end = adc_start + num_samples_reference * 4
                _seq[adc_start + 2:phase_ref_end + 2:4] |= self.phase_reference[:num_samples_reference]

                _rx_data.append(
                    RxData(
                        index=adc_count,
                        num_samples=block.adc.num_samples,
                        num_samples_raw=num_samples_raw,
                        num_samples_discard=num_samples_discard,
                        dwell_time=block.adc.dwell,
                        dwell_time_raw=spcm_dwell,
                        phase_offset=block.adc.phase_offset,
                        freq_offset=block.adc.freq_offset,
                        total_averages=parameter.num_averages,
                        ddc_method=parameter.ddc_method,
                        labels=labels,
                    )
                )
                adc_count += 1
                labels = {}  # Reset labels dict

            # Handle RF Unblanking (Digital Signal)
            if block.rf is not None:
                 # Calculate timing (replaces logic from original _calculate_rf)
                num_samples_delay = round(max(block.rf.dead_time, block.rf.delay) / spcm_dwell)
                num_samples_dead_time = round(block.rf.dead_time / spcm_dwell)
                num_samples = round(block.rf.shape_dur / spcm_dwell)

                rf_unblanking_start = num_samples_delay - num_samples_dead_time
                rf_unblanking_end = num_samples_delay + num_samples

                # Start index in _seq
                abs_start = waveform_start + rf_unblanking_start * 4
                abs_end = waveform_start + rf_unblanking_end * 4

                # Add RF unblanking to 16th bit of output channel 4 (last gradient channel)
                _seq[abs_start + 3 : abs_end + 3 : 4] |= np.uint16(2**15)

            # Handle RF and gradient Waveforms: Prepare calculation tasks for phase 2
            # Check if block has any analog components
            block_has_waveform = (
                (block.rf is not None) or (block.gx is not None) or (block.gy is not None) or (block.gz is not None)
            )
            if block_has_waveform:
                tasks.append(
                    (
                        self._temp_file.name,
                        _seq.shape,
                        _seq.dtype,
                        event_idx,
                        current_block_pos,
                        block,
                        parameter,
                        self.waveform_config,
                    )
                )

        self.log.info(f"Generated {len(tasks)} calculation tasks.")

        # Phase 2: Parallel Waveform Calculation
        if num_processes > 1 and len(tasks) > 0:
            self.log.info(f"Starting pool with {num_processes} processes.")
            # Pool context manager avoids leaking processes
            with Pool(processes=num_processes) as pool:
                pool.starmap(calculate_block, tasks)
        elif len(tasks) > 0:
            self.log.info("Executing sequentially.")
            for task in tasks:
                calculate_block(*task)

        self.log.debug(
            "Unrolled sequence; Total sample points: %s; Total block events: %s",
            seq_samples,
            len(block_durations),
        )

        return UnrolledSequence(
            seq=_seq,
            sample_count=seq_samples,
            gpa_gain=self.waveform_config.gpa_gain,
            gradient_efficiency=self.waveform_config.grad_eff,
            rf_to_mvolt=self.waveform_config.rf_to_mvolt,
            dwell_time=spcm_dwell,
            gradient_output_limits=self.waveform_config.gradient_out_limits,
            rf_output_limit=self.waveform_config.rf_out_limit,
            duration=self.duration()[0],
            adc_count=adc_count,
            parameter=parameter,
            rx_data=_rx_data,
        )


    # -------- Private validation methods -------- #

    def _check_gradient_amplitude(self, idx: int, rel_value: float) -> None:
        """Raise error if amplitude exceeds output limit."""
        limit = self.waveform_config.gradient_out_limits[idx]
        if np.abs(rel_value) > 1.:
            msg = f"Amplitude of gradient channel {idx+1} ({rel_value*limit}) exceeded output limit ({limit}))"
            raise ValueError(msg)

    def _check_parameter(self, parameter: AcquisitionParameter) -> None:
        """Check acquisition parameter and raise error if invalid."""
        # Check larmor frequency
        f0_limit = 1 / (2 * self.waveform_config.spcm_dwell_time)
        if parameter.larmor_frequency >= f0_limit:
            msg = f"Larmor frequency too high ({parameter.larmor_frequency * 1e-6} MHz), violating sampling theorem"
            raise ValueError(msg)
        if parameter.larmor_frequency <= 0:
            msg = "Larmor frequency invalid (<= 0)."
            raise ValueError(msg)

        # Validate channel assignment
        grad_ch: Dimensions = parameter.channel_assignment
        if not all(isinstance(v, int) for v in (grad_ch.x, grad_ch.y, grad_ch.z)):
            raise TypeError("All channel_assignment values must be integers.")
        if {grad_ch.x, grad_ch.y, grad_ch.z} != {1, 2, 3}:
            msg = f"Invalid channel assignment, must contain each of 1, 2, and 3 exactly once, got: {grad_ch}"
            raise ValueError(msg)

    def _check_sequence(self) -> None:
        """Check sequence."""
        # Check number of block events
        if not len(self.block_events) > 0:
            raise ValueError("No block events found")
        # Perform sequence timing check
        check, seq_err = self.check_timing()
        if not check:
            raise ValueError(f"Sequence timing check failed: {seq_err}")
