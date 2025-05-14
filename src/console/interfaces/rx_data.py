from dataclasses import dataclass

import numpy as np
from scipy import signal

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
        time_axis = np.arange(np.size(self.raw_data)) * self.dwell_time_raw        
        self.raw_data = np.exp(1j*self.phase_offset) *self.raw_data * np.exp(2j * np.pi * time_axis * self.demod_freq)

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
                return signal.decimate(self.raw_data, q=self.decimation_factor, ftype="iir")

    def process_data(self, larmor_freq: int | float, store_unprocessed: bool = False) -> None:
        """Proces (demodulate, phase and downsample) the raw data contained in the rx object."""
        self.demod_freq = larmor_freq + self.freq_offset
        self.demod_and_phase_data()

        # Creating the processed data output array first and copying the values of the output of the decimation
        # avoids an apparent memory leak when using the scipy.decimate with the 'iir' ftype
        self.proc_data = np.zeros(round(np.size(self.raw_data)/self.decimation_factor), dtype = complex)
        self.proc_data[:] = self.decimate_data()[:]

        if not store_unprocessed:
            self.raw_data = None
