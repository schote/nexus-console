""""Define the dataclass and processing of receiver data."""
from dataclasses import asdict, dataclass, field
from multiprocessing.shared_memory import SharedMemory

import numpy as np
from scipy import signal

from console.interfaces.acquisition_parameter import DDCMethod
from console.utilities import ddc


@dataclass
class RxData:
    """Receive data object containing both the data and metadata of each receive (ADC) event.

    Instances are created as templates by `SequenceProvider.unroll_sequence` (one per ADC event),
    filled with raw samples by the receive card during acquisition and finally processed by
    `process_data` (scaling, demodulation, phase correction, decimation).
    """

    index: int
    """Index of the ADC event within the sequence."""

    num_samples: int
    """Number of samples after decimation, as defined by the PyPulseq ADC event."""

    num_samples_raw: int
    """Number of samples at the receive card sampling rate (including discard samples)."""

    num_samples_discard: int
    """Number of (decimated) samples added before and after the ADC window, defined by the ADC dead time."""

    dwell_time: float
    """Dwell time of the decimated data in s."""

    dwell_time_raw: float
    """Dwell time of the raw data (receive card sampling interval) in s."""

    phase_offset: float
    """Phase offset of the ADC event from the sequence definition in rad."""

    freq_offset: float
    """Frequency offset of the ADC event from the sequence definition in Hz."""

    total_averages: int
    """Total number of averages of the acquisition."""

    average_index: int = 0
    """Index of the average this event belongs to."""

    labels: dict[str, int | None] | None = None
    """PyPulseq labels (e.g. ``LIN``, ``PAR``, ``ECO``) set since the preceding ADC event."""

    decimation_factor: int = field(init=False)
    """Decimation factor ``round(dwell_time / dwell_time_raw)``, computed on initialization."""

    larmor_frequency: float | None = None
    """Larmor frequency in Hz used for this acquisition."""

    demod_frequency: float | None = None
    """Demodulation frequency in Hz, i.e. Larmor frequency plus `freq_offset`; set by `process_data`."""

    phase_ref_frequency: float | None = None
    """Frequency of the digital phase reference signal in Hz."""

    ddc_method: DDCMethod = DDCMethod.FIR
    """Decimation filter method."""

    scaling_factor: np.ndarray | list[float] | None = None
    """Conversion factor from ADC values to mV per receive channel."""

    raw_data: np.ndarray | None = None
    """Raw int16 samples of the receive card, shape ``(num_channels_enabled, num_samples_raw)``.
    Removed after processing unless ``store_unprocessed`` is set."""

    phase_reference: np.ndarray | None = None
    """Digital phase reference sampled with channel 0 (0/1 values, at most 1000 samples)."""

    time_stamp: float | None = None
    """Start time of the ADC gate in s relative to the start of the receive card."""

    processed_data: np.ndarray | None = None
    """Demodulated, phase-corrected and decimated complex data,
    shape ``(num_channels_enabled, num_samples + 2 * num_samples_discard)``."""

    # Shared memory handle and (name, shape) needed to reattach after pickling.
    # track=False on both sides: the worker unlinks explicitly, avoiding a
    # spurious 'leaked shared_memory' warning from the resource tracker.
    _shm: SharedMemory | None = field(default=None, init=False, repr=False, compare=False)
    _shm_meta: tuple[str, tuple[int, ...]] | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post init method to calculate the decimation factor."""
        self.decimation_factor = round(self.dwell_time / self.dwell_time_raw)

    def __getstate__(self) -> dict:
        """Strip the live handle and raw_data view; keep the shm name/shape (custom pickle)."""
        state = self.__dict__.copy()
        if self._shm is not None:
            state["raw_data"] = None
            state["_shm"] = None
        return state

    def __setstate__(self, state: dict) -> None:
        """Reattach to shared memory if a name/shape pair is present (custom pickle)."""
        self.__dict__.update(state)
        if self._shm_meta is not None:
            name, shape = self._shm_meta
            try:
                self._shm = SharedMemory(name=name, create=False, track=False)
                self.raw_data = np.ndarray(shape, dtype=np.int16, buffer=self._shm.buf)
            except Exception as e:
                raise RuntimeError(f"Failed to reattach to shared memory '{name}': {e}") from e

    def write_raw_data(self, data: np.ndarray) -> None:
        """Copy ADC data into shared memory, allocating it on the first call.

        Parameters
        ----------
        data
            Raw int16 ADC data with shape (num_channels, num_samples_raw).
        """
        if self._shm is None:
            self._shm = SharedMemory(create=True, size=data.nbytes, track=False)
            self._shm_meta = (self._shm.name, data.shape)
            self.raw_data = np.ndarray(data.shape, dtype=np.int16, buffer=self._shm.buf)
        if self.raw_data is None:
            raise RuntimeError("Shared memory buffer not initialized.")
        self.raw_data[:] = data

    def materialize(self, keep: bool = False) -> None:
        """Finalize raw_data after processing, releasing shared memory.

        Parameters
        ----------
        keep
            If True, copy raw_data to a regular numpy array before releasing
            shared memory so the data survives. If False, raw_data is set to None.
        """
        if self._shm is None:
            return
        regular_array = self.raw_data.copy() if keep and self.raw_data is not None else None
        self._shm.close()
        self._shm.unlink()
        self._shm = None
        self._shm_meta = None
        self.raw_data = regular_array

    def __str__(self) -> str:
        """Return string representation of information contained within RxData class."""
        lines = ["RxData:"]
        lines.append("-" * 7)
        for key, value in self.dict().items():
            lines.append(f"{key:<20}: {value}")
        return "\n".join(lines)

    def dict(self) -> dict:
        """Return RxData meta information as string."""
        return {
            key: (
                value.shape if key in ("processed_data", "raw_data") and value is not None
                else "None" if value is None
                else value
            )
            for key, value in asdict(self).items()
            if not key.startswith("_")
        }

    def decimate_data(self, data: np.ndarray) -> np.ndarray:
        """Decimate the data using the defined `DDCMethod` method."""
        if self.decimation_factor <= 1 or not isinstance(self.decimation_factor, int):
            raise ValueError(f"Invalid decimation factor {self.decimation_factor}")

        # Recover 50% amplitude loss from filtering the 2*f_Larmor mixing term; at f=0, LO is 1 (identity)
        scaling = 1.
        if self.larmor_frequency is not None and self.larmor_frequency > 0.:
            scaling = 2.

        match self.ddc_method:
            case DDCMethod.CIC:
                return scaling * ddc.filter_cic_fir_comp(data, decimation=self.decimation_factor, number_of_stages=5)
            case DDCMethod.AVG:
                return scaling * ddc.filter_moving_average(data, decimation=self.decimation_factor, overlap=8)
            case _:
                # Default case is FIR decimation
                return scaling * signal.decimate(data, q=self.decimation_factor, ftype="fir", axis=-1)

    def demod_and_phase_data(self, data: np.ndarray) -> np.ndarray:
        """Demodulate and phase the data contained in raw_data.

        This step first demodulates the acquired data using the demodulation frequency,
        which is usually the Larmor frequency. If a phase reference has been acquired,
        the phase reference signal is demodulated at the phase reference frequency.
        The phase correction term calculated from the phase reference is used to correct the
        acquired MR data. In a last step the phase offset defined by the sequence is applied.
        """
        if self.demod_frequency is None:
            raise RuntimeError("Demodulation frequency not set")
        # Demodulate the data
        time = np.arange(np.size(data, -1)) * self.dwell_time_raw
        data_demod = data * np.exp(-2j * np.pi * time * self.demod_frequency)

        # Demodulate the reference signal if available and correct acquired data
        if self.phase_reference is not None and self.phase_ref_frequency is not None:
            # Demodulation of the phase reference signal
            time_reference = np.arange(self.phase_reference.size) * self.dwell_time_raw
            ref_demod = self.phase_reference * np.exp(-2j * np.pi * self.phase_ref_frequency * time_reference)
            # Calculation of the phase correction term for the acquired MR data
            phase_correction = np.angle(np.sum(ref_demod)) * (self.demod_frequency / self.phase_ref_frequency)
            # Apply phase correction in place
            data_demod *= np.exp(-1j * phase_correction)

        # Apply receive phase offset to data and return data
        return data_demod * np.exp(1j * self.phase_offset)

    def scale_data(self, data: np.ndarray) -> np.ndarray:
        """Scale the receive data to go from ADC units to mV."""
        if self.scaling_factor is not None:
            return data * np.expand_dims(self.scaling_factor, axis=-1)
        else:
            # If no scaling data is provided then just return the array as an array of floats for consistency
            return data.astype(float)

    def process_data(self, store_unprocessed: bool = True) -> None:
        """Process (demodulate, phase and downsample) the raw data contained in the rx object."""
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
        # Note that the processed data may contain samples from pre and post sampling
        output_shape = (*np.shape(demod_data)[:-1], self.num_samples + int(2*self.num_samples_discard))
        self.processed_data = np.zeros(output_shape, dtype=complex)
        self.processed_data[:] = self.decimate_data(demod_data)

        if not store_unprocessed:
            self.raw_data = None
