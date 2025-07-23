""""Define the dataclass and processing of receiver data."""
from dataclasses import asdict, dataclass, field

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
    num_samples: int
    num_samples_raw: int
    dwell_time: float
    dwell_time_raw: float

    # Data offsets from sequence definition
    phase_offset: float
    freq_offset: float

    # Averages tracking
    total_averages: int
    average_index: int = 0

    # ADC labels
    labels: dict | None = None

    # Used for demodulation, value set in post init
    decimation_factor: int = field(init=False)

    # Set the larmor frequency for each object
    larmor_frequency: None | float = None

    # Frequency with which the data are demodulated
    demod_frequency: None | float = None

    # Set the default demod method to FIR
    ddc_method: DDCMethod = DDCMethod.FIR

    # Scaling factor for each receive channel
    scaling_factor: None | np.ndarray | list[float] = None

    # Raw data is the raw data coming from the Rx cards, prior to demodulation and decimation
    # Shape of Raw data is (num_channels_enabled, raw number of samples)
    raw_data: None | np.ndarray = None

    # Timestamp of start of data acquisition
    time_stamp: None | float = None

    # Proc data is the demodulated, phased and decimated data
    processed_data: None | np.ndarray = None

    def __post_init__(self) -> None:
        """Post init method to calculate the decimation factor."""
        self.decimation_factor = round(self.dwell_time / self.dwell_time_raw)

    def __str__(self) -> str:
        """Return string representation of information contained within RxData class."""
        lines = ["RxData:"]
        lines.append("-" * 30)
        for key, value in self.dict():
            lines.append(f"{key:<20}: {value}")
        return "\n".join(lines)

    def dict(self) -> dict:
        """Return RxData meta information as string."""
        _dict = asdict(self)
        for key, value in _dict.items():
            # Remove private/protected attributes
            if key.startswith("_"):
                _dict.pop(key)
            # Stringify none values
            if value is None:
                _dict[key] = "None"
            # Replace data attributes by their shape
            if key in ["processed_data", "raw_data"]:
                _dict[key] = value.shape
        return _dict

    def decimate_data(self, data) -> np.ndarray:
        """Decimate the data using the passed method."""
        if self.decimation_factor <= 1 or not isinstance(self.decimation_factor, int):
            raise ValueError(f"Invalid decimation factor {self.decimation_factor}")

        match self.ddc_method:
            case DDCMethod.CIC:
                return ddc.filter_cic_fir_comp(data, decimation=self.decimation_factor, number_of_stages=5)
            case DDCMethod.AVG:
                return ddc.filter_moving_average(data, decimation=self.decimation_factor, overlap=8)
            case _:
                # Default case is FIR decimation
                return signal.decimate(data, q=self.decimation_factor, ftype="fir", axis=-1)

    def demod_and_phase_data(self, data) -> np.ndarray:
        """Demodulate and phase the data contained in raw_data."""
        if self.demod_frequency is None:
            raise RuntimeError("Demodulation frequency not set")
        # Demodulate the data
        time_axis = np.arange(np.size(data, -1)) * self.dwell_time_raw
        data_demod = data * np.exp(-2j * np.pi * time_axis * self.demod_frequency)

        # Apply receive phase correction to data and return data
        return data_demod * np.exp(1j * self.phase_offset)

    def scale_data(self, data) -> np.ndarray:
        """Scale the receive data to go from ADC units to mV."""
        if self.scaling_factor is not None:
            return data * np.expand_dims(self.scaling_factor, axis=-1)
        else:
            # If no scaling data is provided then just return the array as an array of floats for consistency
            return data.astype(float)

    def process_data(self, store_unprocessed: bool = True) -> None:
        """Proces (demodulate, phase and downsample) the raw data contained in the rx object."""
        if self.larmor_frequency is None:
            raise RuntimeError("Larmor frequency not set, please set prior to processing data")

        if self.raw_data is None:
            raise RuntimeError("Can't process data; No raw data present in RxData object")

        if np.size(self.raw_data, axis=-1) != self.num_samples_raw:
            raise ValueError(f"Number of collected samples is different from expected: "
                             f"{np.size(self.raw_data, axis = -1)} collected vs {self.num_samples_raw} expected")

        self.demod_frequency = self.larmor_frequency + self.freq_offset

        scaled_data = self.scale_data(self.raw_data)

        demod_data = self.demod_and_phase_data(scaled_data)

        # Creating the processed data output array first and copying the values of the output of the decimation
        # avoids an apparent memory leak when using the scipy.decimate with the 'iir' ftype
        output_shape = list(np.shape(demod_data))
        output_shape[-1] = self.num_samples
        self.processed_data = np.zeros(output_shape, dtype=complex)
        self.processed_data[:] = self.decimate_data(demod_data)[:]

        if not store_unprocessed:
            self.raw_data = None
