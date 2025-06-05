from dataclasses import dataclass

import numpy as np
from scipy import signal
import multiprocessing as mp
import queue
import threading

from console.interfaces.acquisition_parameter import DDCMethod
from console.utilities import ddc


@dataclass
class RxData:
    """Receive data object containing both the data and metadata of each receive event."""

    # Rx data event number
    index: int

    # Data characteristics, defined by the ADC event in sequence defintion
    num_pnts: int
    dwell_time: float

    # Data offsets from sequence definition
    phase_offset: float
    freq_offset: float

    # ADC labels
    labels: dict | None = None

    # Raw dwell time of the receive cards
    dwell_time_raw: None | float = None

    # Set the larmor frequency for each object
    larmor_frequency: None | float = None

    # Frequency with which the data are demodulated
    demod_frequency: None | float = None

    # Used for demodulation, value set in post init
    decimation_factor: None | int = None

    # Set the default demod method to FIR (though technically its IIR)
    ddc_method: DDCMethod = DDCMethod.FIR

    # Raw data is the raw data coming from the Rx cards, prior to demodulation and decimation
    raw_data: None | np.ndarray = None

    # Proc data is the demodulated and decimated data
    proc_data: None | np.ndarray = None


    def __post_init__(self) -> None:
        """Post init method to calculate the decimation factor."""
        self.decimation_factor = round(self.dwell_time/self.dwell_time_raw)

    def demod_and_phase_data(self):
        """Demodulate and phase the data contained in raw_data."""
        if self.raw_data is None:
            raise RuntimeError("No raw data found")
        time_axis = np.arange(np.size(self.raw_data,-1)) * self.dwell_time_raw
        self.raw_data = np.exp(1j*self.phase_offset) * self.raw_data * np.exp(2j * np.pi * time_axis * self.demod_frequency)

    def decimate_data(self) -> np.ndarray:
        """Decimate the data using the passed method."""
        if self.raw_data is None:
            raise RuntimeError("No raw data found")
        elif self.decimation_factor <= 1 or not isinstance(self.decimation_factor, int):
            raise ValueError(f"Invalid decimation factor {self.decimation_factor}")

        match self.ddc_method:
            case DDCMethod.CIC:
                return ddc.filter_cic_fir_comp(self.raw_data, decimation=self.decimation_factor, number_of_stages=5)
            case DDCMethod.AVG:
                return ddc.filter_moving_average(self.raw_data, decimation=self.decimation_factor, overlap=8)
            case _:
                # Default case is FIR decimation
                return signal.decimate(self.raw_data, q=self.decimation_factor, ftype="iir", axis = -1)

    def process_data(self, store_unprocessed: bool = True) -> None:
        """Proces (demodulate, phase and downsample) the raw data contained in the rx object."""
        if self.larmor_frequency is None:
            raise RuntimeError("Larmor frequency not set, please set prior to processing data")
        self.demod_frequency = self.larmor_frequency + self.freq_offset
        self.demod_and_phase_data()

        # Creating the processed data output array first and copying the values of the output of the decimation
        # avoids an apparent memory leak when using the scipy.decimate with the 'iir' ftype
        output_shape = list(np.shape(self.raw_data))
        output_shape[-1] = round(output_shape[-1]/self.decimation_factor)
        self.proc_data = np.zeros(output_shape, dtype = complex)
        self.proc_data[:] = self.decimate_data()[:]

        if not store_unprocessed:
            self.raw_data = None

    def set_and_process_data(self, raw_data: np.ndarray, 
                             store_unprocessed: bool = True) -> None:
        """Sets the raw data and processes it within a function, used for the multiprocessing implementation."""
        self.raw_data = raw_data
        self.process_data(store_unprocessed=store_unprocessed)


class MultiprocessingProcessor:
    """Multiproc way of processing data concurrently on multiple processors"""
    def __init__(self, max_workers=4):
        self.pool = mp.Pool(processes=max_workers)
        self.results = []

    def add_item(self, item: RxData, raw_data: np.ndarray, larmor_freq: float) -> None:
        """Add and immediately submit item for processing"""
        result = self.pool.apply_async(RxData.set_and_process_data, (item,raw_data))
        self.results.append(result)

    def wait_completion(self, timeout=None) -> list[RxData]:
        """Wait for all items to complete."""
        processed_items = []
        for result in self.results:
            try:
                processed_item = result.get(timeout=timeout)
                processed_items.append(processed_item)
            except Exception as e:
                print(f"Error processing item: {e}")
        return processed_items

    def shutdown(self) -> None:
        """Shutdown the processor"""
        self.pool.close()
        self.pool.join()
        self.pool = None
        self.results.clear()

class MultiThreadingProcessor:
    """Multi threading way or processing data."""
    def __init__(self, max_workers=4):
        self.data_queue = queue.Queue()
        self.workers = []
        self.running = True

        for _ in range(max_workers):
            t = threading.Thread(target=self._worker_loop)
            t.daemon = True
            self.workers.append(t)
            t.start()

    def _worker_loop(self):
        """Worker thread function that continuously processes items"""
        while self.running:
            try:
                # Block with timeout to periodically check if still running
                obj = self.data_queue.get(timeout=1.0)
                if obj is None:  # Sentinel value to handle shut down
                    self.data_queue.put(None)  # Put back for other workers
                    break
                obj.process_data(store_unprocessed = True)

                # Mark as done
                self.data_queue.task_done()
            except queue.Empty:
                # Queue is empty, don't need to process item
                continue

    def add_items(self, rx_data: list[RxData], larmor_freq: list | float):
        """Add list of RxData objects to queue for processing."""
        if isinstance(larmor_freq, list):
            if len(list) != len(rx_data):
                raise IndexError("rx_data and larmor frequency list are not the same length")
            else: 
                for rx_object, freq in zip(rx_data, larmor_freq):
                    rx_object.larmor_frequency=freq
                    self.data_queue.put(rx_object)
        elif isinstance(larmor_freq, (float, int)):
            for rx_object in rx_data:
                rx_object.larmor_frequency=larmor_freq
                self.data_queue.put(rx_object)
        else:
            raise TypeError("Invalid data type for larmor freq")


    def shutdown(self):
        """Cleanly handle waiting for data processing to finish."""
        # Wait for queue to empty
        self.data_queue.join()
        self.running = False

        # Add a None object in to the queue to signify shutdown
        self.data_queue.put(None)

        # Wait for workers to finish processing
        for worker in self.workers:
            if worker.is_alive():
                worker.join()
