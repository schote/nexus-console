"""Background sequence block streamer and memory adapter."""

import ctypes
import multiprocessing as mp
import queue
import threading
from functools import partial

import numpy as np

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.block_calculator import (
    BlockTask,
    WaveformConfig,
    calculate_block,
    generate_phase_reference,
)


class BlockStreamer:
    """Manages the background production of sequence blocks for playout."""

    MAX_WORKERS = max(1, mp.cpu_count() - 1)

    def __init__(
        self,
        execution_plan: list[BlockTask],
        parameter: AcquisitionParameter,
        config: WaveformConfig,
        sample_count: int,
        rx_data: list,
        max_queue_size: int = 50,
    ):
        self.execution_plan = execution_plan
        self.parameter = parameter
        self.config = config
        self.sample_count = sample_count
        self.rx_data = rx_data
        self.max_queue_size = max_queue_size

        if self.max_queue_size <= 0:
            self.queue = queue.Queue()
        else:
            self.queue = queue.Queue(maxsize=self.max_queue_size)

        self.phase_reference = generate_phase_reference(config.spcm_dwell_time)
        self.pool = None
        self.thread = None
        self._stop_event = threading.Event()

        # Streamer adapter state
        self.current_block = None
        self.block_offset = 0

    def _producer_thread(self):
        """Run producer thread core loop that calculates blocks and pushes to queue."""
        try:
            self.pool = mp.Pool(self.MAX_WORKERS)
            calc_func = partial(
                calculate_block,
                parameter=self.parameter,
                config=self.config,
                phase_reference=self.phase_reference,
            )

            for result_block in self.pool.imap(calc_func, self.execution_plan, chunksize=1):
                if self._stop_event.is_set():
                    break
                self.queue.put(result_block)

        except Exception as e:
            print(f"Error in BlockStreamer: {e}")
        finally:
            self.queue.put(None)  # EOF
            if self.pool is not None:
                self.pool.close()
                self.pool.join()

    def start(self):
        """Start generating blocks in the background."""
        if not self.execution_plan:
            self.queue.put(None)
            return

        self.thread = threading.Thread(
            target=self._producer_thread,
            daemon=True,
        )
        self.thread.start()

    def get_next_block(self) -> np.ndarray | None:
        """Fetch the next block from the queue. Returns None when depleted."""
        block = self.queue.get()
        return block

    def stop(self):
        """Stop production of blocks."""
        self._stop_event.set()

        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

        if self.thread and self.thread.is_alive():
            self.thread.join()

    def copy_to_memory(self, dest_ptr: int, n_bytes: int) -> bool:
        """Dynamically fetch calculated blocks from queue and fill hardware memory pointers."""
        bytes_written = 0
        while bytes_written < n_bytes:
            if self.current_block is None:
                self.current_block = self.get_next_block()
                self.block_offset = 0
                if self.current_block is None:
                    # EOF Reached, fill the rest with zeros
                    ctypes.memset(dest_ptr + bytes_written, 0, n_bytes - bytes_written)
                    return False

            block_bytes = self.current_block.nbytes
            available = block_bytes - self.block_offset
            to_copy = min(available, n_bytes - bytes_written)

            if to_copy > 0:
                src_ptr = self.current_block.ctypes.data + self.block_offset
                ctypes.memmove(dest_ptr + bytes_written, src_ptr, to_copy)

                bytes_written += to_copy
                self.block_offset += to_copy

            if self.block_offset == block_bytes:
                self.current_block = None

        return True

    def unroll_fully(self) -> UnrolledSequence:
        """Evaluate the entire sequence and return it as a populated UnrolledSequence object."""
        seq = np.zeros(self.sample_count * 4, dtype=np.int16)

        self.start()

        current_pos = 0
        while True:
            block = self.get_next_block()
            if block is None:
                break

            block_samples = len(block) // 4
            seq[current_pos * 4 : (current_pos + block_samples) * 4] = block
            current_pos += block_samples

        self.stop()

        return UnrolledSequence(
            seq=seq,
            sample_count=self.sample_count,
            rx_data=self.rx_data,
            gpa_gain=self.config.gpa_gain,
            gradient_efficiency=self.config.grad_eff,
            gradient_output_limits=self.config.gradient_out_limits,
            rf_to_mvolt=self.config.rf_to_mvolt,
            rf_output_limit=self.config.rf_out_limit,
            dwell_time=self.config.spcm_dwell_time,
            duration=self.sample_count * self.config.spcm_dwell_time,
            adc_count=len(self.rx_data),
            parameter=self.parameter,
            gamma=self.config.gamma,
        )
