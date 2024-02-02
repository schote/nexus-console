"""Acquisition Control Class."""

import logging
import logging.config
import os
import time
from datetime import datetime

import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter
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
        configuration_file: str = "../../../device_config.yaml",
        data_storage_path: str = os.path.expanduser("~") + "/spcm-console",
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
        data_storage_path
            Directory of storage location.
            Within the storage location the acquisition control will create a session folder
            (currently the convention is used: one day equals one session).
            All data written during one session will be stored in the session folder.
        file_log_level
            Set the logging level for log file. Logfile is written to the session folder.
        console_log_level
            Set the logging level for the terminal/console output.
        """
        # Create session path (contains all acquisitions of one day)
        self.session_path = os.path.join(data_storage_path, "") + datetime.now().strftime("%Y-%m-%d") + "-session/"
        os.makedirs(self.session_path, exist_ok=True)

        self._setup_logging(console_level=console_log_level, file_level=file_log_level)
        self.log = logging.getLogger("AcqCtrl")
        self.log.info("--- Acquisition control started\n")

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

        self.sqnc: UnrolledSequence | None = None

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

    def set_sequence(self, sequence: str | Sequence, parameter: AcquisitionParameter) -> None:
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
            else:
                raise AttributeError("Invalid sequence, must be either string to .seq file or Sequence instance")

        except (FileNotFoundError, AttributeError) as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Calculate sequence
        self.sqnc = None
        self.log.info(
            "Unrolling sequence: %s",
            self.seq_provider.definitions["Name"].replace(" ", "_"),
        )
        self.sqnc = self.seq_provider.unroll_sequence(
            larmor_freq=parameter.larmor_frequency,
            b1_scaling=parameter.b1_scaling,
            fov_scaling=parameter.fov_scaling,
            grad_offset=parameter.gradient_offset,
        )
        self.parameter = parameter


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
            if self.sqnc is None:
                raise ValueError("No sequence set, call set_sequence() to set a sequence and acquisition parameter.")
        except (RuntimeError, ValueError) as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Define timeout for acquisition process: 5 sec + sequence duration
        timeout = 5 + self.sqnc.duration
        self.log.info("Sequence duration: %s s", self.sqnc.duration)

        self._unproc = []
        self._raw = []

        for k in range(self.parameter.num_averages):
            self.log.info("Acquisition %s/%s", k + 1, self.parameter.num_averages)

            # Start masurement card operations
            self.rx_card.start_operation()
            time.sleep(0.5)
            self.tx_card.start_operation(self.sqnc)

            # Get start time of acquisition
            time_start = time.time()

            while len(self.rx_card.rx_data) < self.sqnc.adc_count:
                # Delay poll by 10 ms
                time.sleep(0.01)

                if len(self.rx_card.rx_data) >= self.sqnc.adc_count:
                    break

                if time.time() - time_start > timeout:
                    # Could not receive all the data before timeout
                    self.log.warning(
                        "Acquisition Timeout: Only received %s/%s adc events",
                        len(self.rx_card.rx_data),
                        self.sqnc.adc_count,
                        stack_info=True,
                    )
                    break

            if len(self.rx_card.rx_data) > 0:
                self.post_processing(self.parameter)

            self.tx_card.stop_operation()
            self.rx_card.stop_operation()

            if self.parameter.averaging_delay > 0:
                time.sleep(self.parameter.averaging_delay)

        try:
            # if not self._raw.size > 0:
            if not len(self._raw) > 0:
                raise ValueError("No raw data acquired...")
            # if len(self._raw) != parameter.num_averages:
            if not all(gate.shape[0] == self.parameter.num_averages for gate in self._raw):
                raise ValueError(
                    "Missing averages: %s/%s",
                    [gate.shape[0] for gate in self._raw],
                    self.parameter.num_averages,
                )
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        return AcquisitionData(
            _raw=self._raw,
            unprocessed_data=self._unproc if len(self._unproc) > 1 else self._unproc[0],
            sequence=self.seq_provider,
            storage_path=self.session_path,
            meta={
                self.tx_card.__name__: self.tx_card.dict(),
                self.rx_card.__name__: self.rx_card.dict(),
                self.seq_provider.__name__: self.seq_provider.dict()
            },
            dwell_time=self.parameter.decimation / self.f_spcm,
            acquisition_parameters=self.parameter,
        )

    def post_processing(self, parameter: AcquisitionParameter) -> None:
        """Proces acquired NMR data.

        Data is sorted according to readout size which might vary between different reout windows.
        Unprocessed and raw data are stored in class attributes _raw and _unproc.
        Both attributes are list, which store numpy arrays of readout data with the same number of readout sample points.

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
        grouped_gates: dict[int, list] = {readout_sizes[k]: [] for k in sorted(np.unique(readout_sizes, return_index=True)[1])}
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

            # Demodulation and decimation
            data = data * np.exp(2j * np.pi * np.arange(data.shape[-1]) * parameter.larmor_frequency / self.f_spcm)

            # data = ddc.filter_cic_fir_comp(data, decimation=parameter.decimation, number_of_stages=5)
            data = ddc.filter_moving_average(data, decimation=parameter.decimation, overlap=8)

            # Apply phase correction
            data = data[:-1, ...] * np.exp(-1j * np.angle(data[-1, ...]))

            # Append to global raw data list
            if raw_size > 0:
                self._raw[k] = np.concatenate((self._raw[k], data[None, ...]), axis=0)
            else:
                self._raw.append(data[None, ...])
