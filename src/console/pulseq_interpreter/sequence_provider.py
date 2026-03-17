"""Sequence provider class."""
import contextlib
import ctypes
import logging
import multiprocessing as mp
import queue
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict
from functools import partial
from math import floor
from multiprocessing.pool import Pool
from types import SimpleNamespace
from typing import Any

import numpy as np
from pypulseq.opts import Opts
from pypulseq.Sequence.sequence import Sequence

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.block_calculator import WaveformConfig, calculate_block


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
        max_queue_size: int = 50,
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
        system
            Pypulseq sequence system
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
        self.config = WaveformConfig(
            spcm_dwell_time=spcm_dwell_time,
            rf_to_mvolt=rf_to_mvolt,
            gpa_gain=gpa_gain,
            grad_eff=gradient_efficiency,
            rf_out_limit=rf_out_limit,
            gradient_out_limits=gradient_out_limits,
            gamma=self.system.gamma,
        )

        # Setup queue for sequence block processing
        self.max_queue_size = max_queue_size
        self.queue: queue.Queue = queue.Queue() if max_queue_size <= 0 else queue.Queue(maxsize=max_queue_size)
        self.processing_plan: list[tuple[int, SimpleNamespace]] = []
        self.num_sequence_samples: int = 0
        self.sequence_size: int = 0
        self.current_block = None
        self.block_offset = 0
        self.num_blocks_obtained = 0

        self.pool: Pool | None = None
        self.thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # -------- PyPulseq interface -------- #

    def from_pypulseq(self, seq: Sequence) -> None:
        """Read a pypulseq sequence to sequence provider.

        Parameters
        ----------
        seq
            Pypulseq ``Sequence`` instance

        Raises
        ------
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

    def to_pypulseq(self) -> Sequence | None:
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
            "config": asdict(self.config),
        }


    def start(self, parameter: AcquisitionParameter, num_worker: int = 0) -> None:
        """Start generating blocks in the background."""
        # Strict concurrency guard
        if self.thread is not None and self.thread.is_alive():
            msg = (
                "A sequence computation is already running. \
                You must wait for it to finish or call stop() before restarting."
            )
            raise RuntimeError(msg)

        self._stop_event.clear()

        # Clear the queue cleanly just in case previous interrupted runs left debris
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

        self._prepare_rx_data(parameter)
        self.thread = threading.Thread(target=self._producer_thread, args=(num_worker, parameter), daemon=True)
        self.thread.start()


    def stop(self) -> None:
        """Stop production of blocks."""
        self._stop_event.set()

        # Drain the queue continuously while the producer is still alive
        while self.thread is not None and self.thread.is_alive():
            try:
                self.queue.get(timeout=0.05)
            except queue.Empty:
                pass

        if self.thread and self.thread.is_alive():
            self.thread.join()


    def copy_to_memory(self, dest_ptr: int, n_bytes: int) -> bool:
        """Dynamically fetch calculated blocks from queue and fill hardware memory pointers."""
        bytes_written = 0
        while bytes_written < n_bytes:

            block = self.current_block

            if block is None:
                block = self.queue.get()

                if isinstance(block, Exception):
                    self.stop()
                    msg = "Background block calculation failed during hardware streaming."
                    raise RuntimeError(msg) from block

                if block is None:
                    # EOF Reached, fill the rest with zeros
                    ctypes.memset(dest_ptr + bytes_written, 0, n_bytes - bytes_written)
                    if self.num_blocks_obtained < len(self.block_events):
                        self.stop()
                        raise RuntimeError(
                            f"Premature EOF: Expected {len(self.block_events)} blocks, "
                            f"got {self.num_blocks_obtained}."
                        )
                    return False

                self.num_blocks_obtained += 1
                self.current_block = block
                self.block_offset = 0

            block_bytes = block.nbytes
            available = block_bytes - self.block_offset
            to_copy = min(available, n_bytes - bytes_written)

            if to_copy > 0:
                src_ptr = block.ctypes.data + self.block_offset
                ctypes.memmove(dest_ptr + bytes_written, src_ptr, to_copy)

                bytes_written += to_copy
                self.block_offset += to_copy

            if self.block_offset == block_bytes:
                self.current_block = None

        return True


    def unroll_sequence(self, parameter: AcquisitionParameter) -> UnrolledSequence:
        """Evaluate the entire sequence and return it as a populated UnrolledSequence object."""
        self.start(parameter)

        seq = np.zeros(self.num_sequence_samples * 4, dtype=np.int16)
        self.num_blocks_obtained = 0
        block_position = 0

        while True:
            block = self.queue.get()

            if isinstance(block, Exception):
                self.stop()
                msg = "Background calculation failed."
                raise RuntimeError(msg) from block

            if block is None:
                if self.num_blocks_obtained < len(self.block_events):
                    self.stop()
                    msg = f"Premature EOF: Expected {len(self.block_events)} blocks, got {self.num_blocks_obtained}."
                    raise RuntimeError(msg)
                break

            block_samples = block.size // 4

            if block_position + block_samples > self.num_sequence_samples:
                self.stop()
                raise RuntimeError(
                    f"Buffer Overflow: Calculated sequence exceeded pre-allocated size of "
                    f"{self.num_sequence_samples} samples."
                )

            seq[block_position * 4 : (block_position + block_samples) * 4] = block
            block_position += block_samples
            self.num_blocks_obtained += 1

        self.stop()

        return UnrolledSequence(
            seq=seq,
            sample_count=self.num_sequence_samples,
            rx_data=self.rx_data,
            gpa_gain=self.config.gpa_gain,
            gradient_efficiency=self.config.grad_eff,
            gradient_output_limits=self.config.gradient_out_limits,
            rf_to_mvolt=self.config.rf_to_mvolt,
            rf_output_limit=self.config.rf_out_limit,
            dwell_time=self.config.spcm_dwell_time,
            duration=self.num_sequence_samples * self.config.spcm_dwell_time,
            adc_count=len(self.rx_data),
            parameter=parameter,
            gamma=self.config.gamma,
        )


    # -------- Private methods -------- #

    def _prepare_rx_data(self, parameter: AcquisitionParameter) -> None:
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

        self.rx_data = []
        self.num_sequence_samples = 0
        self.sequence_size = 0
        self.num_blocks_obtained = 0
        adc_count: int = 0
        labels = {}
        self.processing_plan = []

        for index, key in enumerate(self.block_events):
            block = self.get_block(key)
            # Sequence block indexing starts at 1
            self.processing_plan.append((index+1, block))
            self.num_sequence_samples += round(block.block_duration / self.config.spcm_dwell_time)

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
                num_samples_raw = round(total_gate_duration / self.config.spcm_dwell_time)

                self.rx_data.append(
                    RxData(
                        index=adc_count,
                        num_samples=block.adc.num_samples,
                        num_samples_raw=num_samples_raw,
                        num_samples_discard=num_samples_discard,
                        dwell_time=block.adc.dwell,
                        dwell_time_raw=self.config.spcm_dwell_time,
                        phase_offset=block.adc.phase_offset,
                        freq_offset=block.adc.freq_offset,
                        total_averages=parameter.num_averages,
                        ddc_method=parameter.ddc_method,
                        labels=labels,
                    ),
                )
                adc_count += 1
                labels = {}  # Reset labels dict

        self.log.info("Prepared sequence for calculation: Got %s ADC events.", len(self.rx_data))
        # Sequence memory = num_samples * 4 (channels) * 2 (bytes per sample)
        self.sequence_size = self.num_sequence_samples * 8

    def _producer_thread(self, num_workers: int, parameter: AcquisitionParameter) -> None:
        """Run producer thread core loop that calculates blocks and pushes to queue."""
        try:
            calc_func = partial(
                calculate_block,
                parameter=parameter,
                config=self.config,
            )

            if num_workers == 0:
                for result_block in map(calc_func, self.processing_plan):
                    if self._stop_event.is_set():
                        break
                    self.queue.put(result_block)
            else:
                self.pool = mp.Pool(num_workers)
                for result_block in self.pool.imap(calc_func, self.processing_plan, chunksize=1):
                    if self._stop_event.is_set():
                        break
                    self.queue.put(result_block)

        except Exception as e:
            self.log.error(f"Error in BlockStreamer: {e}")
            with contextlib.suppress(queue.Full):
                self.queue.put(e, timeout=1.0)
        finally:
            with contextlib.suppress(queue.Full):
                self.queue.put(None, timeout=1.0)  # EOF
            if self.pool is not None:
                if self._stop_event.is_set() or isinstance(sys.exc_info()[1], Exception):
                    self.pool.terminate()
                else:
                    self.pool.close()
                self.pool.join()


    def _check_gradient_amplitude(self, idx: int, rel_value: float) -> None:
        """Raise error if amplitude exceeds output limit."""
        limit = self.config.gradient_out_limits[idx]
        if np.abs(rel_value) > 1.0:
            msg = f"Amplitude of gradient channel {idx + 1} ({rel_value * limit}) exceeded output limit ({limit}))"
            raise ValueError(msg)


    def _check_parameter(self, parameter: AcquisitionParameter) -> None:
        """Check acquisition parameter and raise error if invalid."""
        # Check larmor frequency
        f0_limit = 1 / (2 * self.config.spcm_dwell_time)
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
