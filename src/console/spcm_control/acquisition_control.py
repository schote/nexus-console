"""Acquisition Control Class."""

import logging
import logging.config
import os
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import signal

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import AcquisitionParameter, DDCMethod
from console.interfaces.dimensions import Dimensions
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider, params
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.utilities import ddc
from console.utilities.load_config import get_instances

LOG_LEVELS = [
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
]


class AcquisitionControl:
    """Acquisition control class.

    The main functionality of the acquisition control is to orchestrate transmit and receive cards using
    ``TxCard`` and ``RxCard`` instances.
    """

    def __init__(
        self,
        configuration_file: str,
        nexus_data_dir: str = os.path.join(Path.home(), "nexus-console"),
        file_log_level: int = logging.INFO,
        console_log_level: int = logging.INFO,
    ):
        """Construct acquisition control class.

        Create instances of sequence provider, tx and rx card.
        Setup the measurement cards and get parameters required for a measurement.

        Parameters
        ----------
        configuration_file
            Path to configuration yaml file which is used to create measurement card and sequence
            provider instances.
        nexus_data_dir:
            Nexus console default directory to store logs, states and acquisition data.
            If none, the default directory is create in the home directory, default is None.
        file_log_level
            Set the logging level for log file. Logfile is written to the session folder.
        console_log_level
            Set the logging level for the terminal/console output.
        """
        # Create session path (contains all acquisitions of one day)
        session_folder_name = datetime.now().strftime("%Y-%m-%d") + "-session/"
        self.session_path = os.path.join(nexus_data_dir, session_folder_name)
        os.makedirs(self.session_path, exist_ok=True)

        self._setup_logging(console_level=console_log_level, file_level=file_log_level)
        self.log = logging.getLogger("AcqCtrl")
        self.log.info("--- Acquisition control started\n")

        # Define global acquisition parameter object

        try:
            params = AcquisitionParameter.load(nexus_data_dir)
        except FileNotFoundError as exc:
            self.log.warning("Acquisition parameter state could not be loaded from dir: %s.\
                Creating new acquisition parameter object.", exc)
            params = AcquisitionParameter()
        # Store parameter hash to detect when a sequence needs to be recalculated
        self._current_parameter_hash: int = hash(params)

        # Get instances from configuration file
        ctx = get_instances(configuration_file)
        self.seq_provider: SequenceProvider = ctx[0]
        self.tx_card: TxCard = ctx[1]
        self.rx_card: RxCard = ctx[2]

        self.seq_provider.output_limits = self.tx_card.max_amplitude

        # Setup the cards
        self.is_setup: bool = False
        if self.tx_card.connect() and self.rx_card.connect():
            self.log.info("Setup of measurement cards successful.")
            self.is_setup = True

        # Get the rx sampling rate for DDC
        self.f_spcm = self.rx_card.sample_rate * 1e6
        # Set sequence provider max. amplitude per channel according to values from tx_card
        self.seq_provider.max_amp_per_channel = self.tx_card.max_amplitude

        self.unrolled_seq: UnrolledSequence | None = None

        # Attributes for data and dwell time of downsampled signal
        self._raw: list[np.ndarray] = []
        self._unproc: list[np.ndarray] = []

    def __del__(self):
        """Class destructor disconnecting measurement cards."""
        if self.tx_card:
            self.tx_card.disconnect()
        if self.rx_card:
            self.rx_card.disconnect()
        self.log.info("Measurement cards disconnected")
        self.log.info("\n--- Acquisition control terminated\n\n")

    def _setup_logging(self, console_level: int, file_level: int) -> None:
        # Check if log levels are valid
        if console_level not in LOG_LEVELS:
            raise ValueError("Invalid console log level")
        if file_level not in LOG_LEVELS:
            raise ValueError("Invalid file log level")

        # Disable existing loggers
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": True})  # type: ignore[attr-defined]

        # Set up logging to file
        logging.basicConfig(
            level=file_level,
            format="%(asctime)s %(name)-7s: %(levelname)-8s >> %(message)s",
            datefmt="%d-%m-%Y, %H:%M",
            filename=f"{self.session_path}console.log",
            filemode="a",
        )

        # Define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(console_level)
        formatter = logging.Formatter("%(name)-7s: %(levelname)-8s >> %(message)s")
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)

    def set_sequence(self, sequence: str | Sequence) -> None:
        """Set sequence and acquisition parameter.

        Parameters
        ----------
        sequence
            Path to pulseq sequence file.
        parameter
            Set of acquisition parameters which are required for the acquisition.

        Raises
        ------
        AttributeError
            Invalid sequence provided.
        FileNotFoundError
            Invalid file ending of sequence file.
        """
        try:
            # Check sequence
            if isinstance(sequence, Sequence):
                self.seq_provider.from_pypulseq(sequence)
            elif isinstance(sequence, str):
                if not sequence.endswith(".seq"):
                    raise FileNotFoundError("Invalid sequence file.")
                self.seq_provider.read(sequence)

        except (FileNotFoundError, AttributeError) as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Reset unrolled sequence
        self.unrolled_seq = None
        self.log.info(
            "Unrolling sequence: %s",
            self.seq_provider.definitions["Name"].replace(" ", "_"),
        )
        # Update sequence parameter hash and calculate sequence
        self._current_parameter_hash = hash(params)
        self.unrolled_seq = self.seq_provider.unroll_sequence()
        self.log.info("Sequence duration: %s s", self.unrolled_seq.duration)

    def run(self) -> AcquisitionData:
        """Run an acquisition job.

        Raises
        ------
        RuntimeError
            The measurement cards are not setup properly
        ValueError
            Missing raw data or missing averages
        """
        try:
            # Check setup
            if not self.is_setup:
                raise RuntimeError("Measurement cards are not setup.")
            if self.unrolled_seq is None:
                raise ValueError("No sequence set, call set_sequence() to set a sequence and acquisition parameter.")
        except (RuntimeError, ValueError) as err:
            self.log.exception(err, exc_info=True)
            raise err

        if self._current_parameter_hash != hash(params):
            # Redo sequence unrolling in case acquisition parameters changed, i.e. different hash
            self.unrolled_seq = None
            self.log.info(
                "Unrolling sequence: %s", self.seq_provider.definitions["Name"].replace(" ", "_")
            )
            # Update acquisition parameter hash value
            self._current_parameter_hash = hash(params)
            self.unrolled_seq = self.seq_provider.unroll_sequence()
            self.log.info("Sequence duration: %s s", self.unrolled_seq.duration)

        # Define timeout for acquisition process: 5 sec + sequence duration
        timeout = 5 + self.unrolled_seq.duration

        self._unproc = []
        self._raw = []

        # Set gradient offset values
        self.tx_card.set_gradient_offsets(params.gradient_offset, self.seq_provider.high_impedance[1:])

        for k in range(params.num_averages):
            self.log.info("Acquisition %s/%s", k + 1, params.num_averages)

            # Start masurement card operations
            self.rx_card.start_operation()
            time.sleep(0.01)
            self.tx_card.start_operation(self.unrolled_seq)

            # Get start time of acquisition
            time_start = time.time()

            while (num_gates := len(self.rx_card.rx_data)) < self.unrolled_seq.adc_count or num_gates == 0:
                # Delay poll by 10 ms
                time.sleep(0.01)

                if (time.time() - time_start) > timeout:
                    # Could not receive all the data before timeout
                    self.log.warning(
                        "Acquisition Timeout: Only received %s/%s adc events",
                        num_gates, self.unrolled_seq.adc_count
                    )
                    break

                if num_gates >= self.unrolled_seq.adc_count and num_gates > 0:
                    break

            if num_gates > 0:
                self.post_processing(params)

            self.tx_card.stop_operation()
            self.rx_card.stop_operation()

            if params.averaging_delay > 0:
                time.sleep(params.averaging_delay)

        # Reset gradient offset values
        self.tx_card.set_gradient_offsets(Dimensions(x=0, y=0, z=0), self.seq_provider.high_impedance[1:])

        try:
            # if len(self._raw) != parameter.num_averages:
            if not all(gate.shape[0] == params.num_averages for gate in self._raw):
                raise ValueError(
                    "Missing averages: %s/%s",
                    [gate.shape[0] for gate in self._raw],
                    params.num_averages,
                )
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        return AcquisitionData(
            _raw=self._raw,
            unprocessed_data=self._unproc,
            sequence=self.seq_provider,
            session_path=self.session_path,
            meta={
                self.tx_card.__name__: self.tx_card.dict(),
                self.rx_card.__name__: self.rx_card.dict(),
                self.seq_provider.__name__: self.seq_provider.dict()
            },
            dwell_time=params.decimation / self.f_spcm,
            acquisition_parameters=params,
        )

    def post_processing(self, parameter: AcquisitionParameter) -> None:
        """Proces acquired NMR data.

        Data is sorted according to readout size which might vary between different reout windows.
        Unprocessed and raw data are stored in class attributes _raw and _unproc.
        Both attributes are list, which store numpy arrays of readout data with the same number
        of readout sample points.

        Post processing contains the following steps (per readout sample size):
        (1) Extraction of reference signal and scaling to float values [mV]
        (2) Concatenate reference data and signal data in coil dimensions
        (3) Demodulation along readout dimensions
        (4) Decimation along readout dimension
        (5) Phase correction with reference signal

        Dimensions: [averages, coils, phase encoding, readout]

        Reference signal is stored in the last entry of the coil dimension.

        Parameters
        ----------
        parameter
            Acquisition parameter
        """
        readout_sizes = [data.shape[-1] for data in self.rx_card.rx_data]
        grouped_gates: dict[int, list] = {
            readout_sizes[k]: [] for k in sorted(np.unique(readout_sizes, return_index=True)[1])
        }
        for data in self.rx_card.rx_data:
            grouped_gates[data.shape[-1]].append(data)

        gate_lengths = [np.stack(group, axis=1) for group in grouped_gates.values()]
        raw_size = len(self._raw)

        # Define channel dependent scaling
        scaling = np.expand_dims(self.rx_card.rx_scaling[:self.rx_card.num_channels.value], axis=(-1, -2))

        for k, data in enumerate(gate_lengths):
            # Extract digital reference signal from channel 0
            _ref = (data[0, ...].astype(np.uint16) >> 15).astype(float)[None, ...]

            # Remove digital signal from channel 0
            data[0, ...] = data[0, ...] << 1
            data = data.astype(np.int16) * scaling

            # Stack signal and reference in coil dimension
            data = np.concatenate((data, _ref), axis=0)

            # Append unprocessed data without post processing (last coil dimension entry contains reference)
            if raw_size > 0:
                self._unproc[k] = np.concatenate((self._unproc[k], data[None, ...]), axis=0)
            else:
                self._unproc.append(data[None, ...])

            print("Demodulation at freq.:", parameter.larmor_frequency)

            # Demodulation and decimation
            data = data * np.exp(2j * np.pi * np.arange(data.shape[-1]) * parameter.larmor_frequency / self.f_spcm)

            # Always decimate the reference signal with moving average filter
            ref_dec = ddc.filter_moving_average(data[-1, ...], decimation=parameter.decimation, overlap=8)[None, ...]
            # Extract the demodulated signal data
            data = data[:-1, ...]

            # Switch case for DDC function
            match params.ddc_method:
                case DDCMethod.CIC:
                    data = ddc.filter_cic_fir_comp(data, decimation=parameter.decimation, number_of_stages=5)
                case DDCMethod.AVG:
                    data = ddc.filter_moving_average(data, decimation=parameter.decimation, overlap=8)
                case _:
                    # Default case is FIR decimation
                    data = signal.decimate(data, q=parameter.decimation, ftype="fir")

            # Apply phase correction with mean value
            # data = data * np.exp(-1j * np.mean(np.angle(ref_dec), axis = -1))[..., None]
            data = data * np.exp(-1j * np.angle(ref_dec))

            # Append to global raw data list
            if raw_size > 0:
                self._raw[k] = np.concatenate((self._raw[k], data[None, ...]), axis=0)
            else:
                self._raw.append(data[None, ...])
