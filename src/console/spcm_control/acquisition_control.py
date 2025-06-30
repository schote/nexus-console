"""Acquisition Control Class."""

import logging
import logging.config
import os
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.dimensions import Dimensions
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
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

        # Get instances from configuration file
        ctx = get_instances(configuration_file)
        self.seq_provider: SequenceProvider = ctx[0]
        self.tx_card: TxCard = ctx[1]
        self.rx_card: RxCard = ctx[2]

        self.seq_provider.output_limits = self.tx_card.max_amplitude

        # Setup the cards
        self.is_setup: bool = False
        try:
            if self.tx_card.connect() and self.rx_card.connect():
                self.log.info("Setup of measurement cards successful.")
                self.is_setup = True
        except Exception:
            self.log.exception("Error during card connection.")
            if self.tx_card:
                self.tx_card.disconnect()
            if self.rx_card:
                self.rx_card.disconnect()

        # Get the rx sampling rate for DDC
        self.f_spcm = self.rx_card.sample_rate * 1e6
        # Set sequence provider max. amplitude per channel according to values from tx_card
        self.seq_provider.max_amp_per_channel = self.tx_card.max_amplitude

        self.sequence: UnrolledSequence | None = None

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
        self.log.info("Acquisition control terminated\n---------------------------------------------------\n")

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
        log_console = logging.StreamHandler()
        log_console.setLevel(console_level)
        formatter = logging.Formatter("%(name)-7s: %(levelname)-8s >> %(message)s")
        log_console.setFormatter(formatter)
        logging.getLogger("").addHandler(log_console)

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

        except (FileNotFoundError, AttributeError) as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Reset unrolled sequence
        self.sequence = None
        self.log.info(
            "Unrolling sequence: %s",
            self.seq_provider.definitions["Name"].replace(" ", "_"),
        )
        # Update sequence parameter hash and calculate sequence
        self.sequence = self.seq_provider.unroll_sequence(parameter=parameter)
        self.log.info("Sequence duration: %s s", self.sequence.duration)

    def run(self, store_unprocessed: bool = False) -> AcquisitionData:
        """Run an acquisition job.

        Parameters
        ----------
        store_unprocessed
            Flag for whether to keep the raw, undecimated data after decimation
        realtime_proccessing
            flag for processing the data in real time using the multiprocessing or
            using threading to process the data after it has all been acquired.

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
            if self.sequence is None:
                raise ValueError("No sequence set, call set_sequence() to set a sequence and acquisition parameter.")
        except (RuntimeError, ValueError) as err:
            self.log.exception(err, exc_info=True)
            raise err

        # Define timeout for acquisition process: 5 sec + sequence duration
        timeout = 5 + self.sequence.duration

        self._unproc = []
        self._raw = []

        # Create a list to store rx_data for all averages
        self.receive_data = []

        # Set gradient offset values
        self.tx_card.set_gradient_offsets(
            self.sequence.parameter.gradient_offset, self.seq_provider.high_impedance[1:]
        )

        for k in range(self.sequence.parameter.num_averages):
            # Create a copy of rx_data to store the current acquisition in
            self.receive_data.append(self.sequence.rx_data.copy())
            self.log.info("Acquisition %s/%s", k + 1, self.sequence.parameter.num_averages)

            # Start masurement card operations
            self.rx_card.start_operation(rx_data=self.receive_data[k])

            time.sleep(0.01)

            while not self.rx_card.is_receiving.is_set():
                time.sleep(0.01)
                # self.log.debug("Waiting for RX card to start receiving...")
            self.tx_card.start_operation(self.sequence)

            # Get start time of acquisition
            time_start = time.time()

            while (num_gates := self.rx_card.total_gates) < self.sequence.adc_count or num_gates == 0:
                # Delay poll by 10 ms
                time.sleep(0.01)

                if (time.time() - time_start) > timeout:
                    # Could not receive all the data before timeout
                    self.log.warning(
                        "Acquisition Timeout: Only received %s/%s adc events",
                        num_gates, self.sequence.adc_count
                    )
                    break

                if num_gates >= self.sequence.adc_count and num_gates > 0:
                    break

            if num_gates > 0:
                self.post_processing(self.sequence.parameter,
                                     store_unprocessed = store_unprocessed)
            self.tx_card.stop_operation()
            self.rx_card.stop_operation()

            if self.sequence.parameter.averaging_delay > 0:
                time.sleep(self.sequence.parameter.averaging_delay)

        # Reset gradient offset values
        self.tx_card.set_gradient_offsets(Dimensions(x=0, y=0, z=0), self.seq_provider.high_impedance[1:])

        try:
            # if len(self._raw) != parameter.num_averages:
            if not all(gate.shape[0] == self.sequence.parameter.num_averages for gate in self._raw):
                raise ValueError(
                    "Missing averages: %s/%s",
                    [gate.shape[0] for gate in self._raw],
                    self.sequence.parameter.num_averages,
                )
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        return AcquisitionData(
            receive_data=self.receive_data,
            sequence=self.seq_provider,
            session_path=self.session_path,
            meta={
                self.tx_card.__name__: self.tx_card.dict(),
                self.rx_card.__name__: self.rx_card.dict(),
                self.seq_provider.__name__: self.seq_provider.dict()
            },
            dwell_time=self.sequence.parameter.decimation / self.f_spcm,
            acquisition_parameters=self.sequence.parameter,
        )

    def post_processing(self, parameter: AcquisitionParameter, store_unprocessed = False) -> None:
        """Proces acquired NMR data.

        Post processing contains the following steps (per readout sample size):
        (1) Scaling of receive data
        (2) Demodulation along readout dimensions
        (3) Decimation along readout dimension

        Parameters
        ----------
        parameter
            Acquisition parameter
        """
        # Scale the data
        for rx_data in self.receive_data[-1]:
            rx_data.raw_data = rx_data.raw_data.astype(np.int16) \
                * np.expand_dims(self.rx_card.rx_scaling[:self.rx_card.num_channels.value], axis=-1)
            rx_data.larmor_frequency = parameter.larmor_frequency

        # Process the data in parallel
        with ThreadPoolExecutor() as executor:
            executor.map(lambda rx_data_obj: \
                rx_data_obj.process_data(store_unprocessed)
                , self.receive_data[-1])
