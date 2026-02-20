import logging
import logging.config
import multiprocessing
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

import matplotlib as mpl
import numpy as np

from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import NexusConfiguration
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.processing_worker import ProcessingWorker
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.utilities.load_configuration import load_nexus_config
from console.utilities.plot import plot_unrolled_sequence

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

        # Load device configuration and create instances
        # TODO: Generalize Nexus configuration to allow different setups
        self.config: NexusConfiguration = load_nexus_config(configuration_file)
        # Create sequence provider instance
        self.seq_provider: SequenceProvider = SequenceProvider(
            gradient_efficiency=self.config.tx.gradient_efficiency,
            gpa_gain=self.config.tx.gpa_gain,
            gradients_50ohms=self.config.tx.gradients_terminated_50ohm,
            rf_50ohms=self.config.tx.rf_terminated_50ohm,
            gradient_output_limits=self.config.tx.channel_max_amplitude[1:],
            rf_output_limit=self.config.tx.channel_max_amplitude[0],
            spcm_dwell_time=self.config.rx.spcm_dwell_time,
            rf_to_mvolt=self.config.tx.rf_to_mvolt,
            num_rx_channels=sum(self.config.rx.channel_enable),
            system_limits=self.config.system,
        )
        # >> Multiprocessing setup
        # Create Queues
        self.rx_command_queue = multiprocessing.Queue()
        self.rx_input_queue = multiprocessing.Queue()
        self.rx_processing_queue = multiprocessing.Queue()
        self.rx_result_queue = multiprocessing.Queue()
        self.tx_command_queue = multiprocessing.Queue()

        # Create transmit card instance
        self.tx_card: TxCard = TxCard(
            path=self.config.tx.device_path,
            max_amplitude=self.config.tx.channel_max_amplitude,
            filter_type=self.config.tx.channel_filter_type,
            sample_rate=self.config.tx.sampling_rate,
            command_queue=self.tx_command_queue,
        )
        # Create receive card instance
        self.rx_card: RxCard = RxCard(
            path=self.config.rx.device_path,
            sample_rate=self.config.rx.sampling_rate,
            channel_enable=self.config.rx.channel_enable,
            max_amplitude=self.config.rx.channel_max_amplitude,
            impedance_50_ohms=self.config.rx.channel_terminated_50ohm,
            command_queue=self.rx_command_queue,
            input_queue=self.rx_input_queue,
            processing_queue=self.rx_processing_queue,
        )
        # Create processing worker
        self.proc_worker = ProcessingWorker(
            processing_queue=self.rx_processing_queue,
            result_queue=self.rx_result_queue,
        )

        # Start processes
        self.tx_card.start()
        self.rx_card.start()
        self.proc_worker.start()

        self.is_setup: bool = True  # We assume setup happens in subprocesses

        # Get the rx sampling rate for DDC
        self.f_spcm = self.rx_card.sample_rate * 1e6
        # Set sequence provider max. amplitude per channel according to values from tx_card
        self.seq_provider.max_amp_per_channel = self.tx_card.max_amplitude

        self.sequence: UnrolledSequence | None = None

        # Attributes for data and dwell time of downsampled signal
        self._raw: list[np.ndarray] = []
        self._unproc: list[np.ndarray] = []

    def shutdown(self):
        """Shutdown all subprocesses."""
        self.log.info("Shutting down processes...")
        if self.tx_card:
            self.tx_card.shutdown()
        if self.rx_card:
            self.rx_card.shutdown()
        if self.proc_worker:
            self.rx_processing_queue.put(None)  # Shutdown sentinel
            self.proc_worker.join()

        if self.sequence:
            self.sequence.shm_tx.close()
            self.sequence.shm_tx.unlink()
            self.sequence.shm_rx.close()
            self.sequence.shm_rx.unlink()

        self.log.info("Acquisition control terminated")

    def __del__(self):
        """Class destructor."""
        # Note: We don't want to call complex shutdown here if already called.
        pass

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
        seq_name = str(self.seq_provider.get_definition("Name"))
        if not seq_name:
            seq_name = str(self.seq_provider.get_definition("name"))
            if not seq_name:
                seq_name = "unknown"
        self.log.info("Unrolling sequence: %s", seq_name.replace(" ", "_"))
        # Calculate sequence with parameter
        if self.sequence:
            self.sequence.shm_tx.close()
            self.sequence.shm_tx.unlink()
            self.sequence.shm_rx.close()
            self.sequence.shm_rx.unlink()

        self.sequence = self.seq_provider.unroll_sequence(parameter=parameter)
        self.log.info("Sequence duration: %s s", self.sequence.duration)

    def run(self, store_unprocessed: bool = False) -> AcquisitionData:
        """Run an acquisition job."""
        if not self.is_setup:
            raise RuntimeError("Measurement cards are not setup.")
        if self.sequence is None:
            raise ValueError("No sequence set.")

        self.log.info("Starting acquisition orchestration...")

        # Populate input queue with pre-allocated RxData objects
        for rx_data in self.sequence.rx_data:
            rx_data.larmor_frequency = self.sequence.parameter.larmor_frequency
            self.rx_input_queue.put(rx_data)

        # Start acquisition
        self.rx_card.start_operation()
        self.tx_card.start_operation(self.sequence)

        # Collect results
        total_events = len(self.sequence.rx_data)
        collected_data = []

        self.log.info(f"Waiting for {total_events} ADC events...")
        timeout = self.sequence.duration + 5
        start_time = time.time()

        while len(collected_data) < total_events:
            try:
                rx_data = self.rx_result_queue.get(timeout=1.0)
                collected_data.append(rx_data)
                if len(collected_data) % 10 == 0:
                    self.log.info(f"Collected {len(collected_data)}/{total_events} events")
            except Exception:
                if time.time() - start_time > timeout:
                    self.log.error(f"Acquisition timeout! Only collected {len(collected_data)}/{total_events}")
                    break

        self.log.info("Acquisition completed.")

        # Sort collected data by index/average to ensure correct order
        collected_data.sort(key=lambda x: (x.average_index, x.index))

        return AcquisitionData(
            receive_data=collected_data,
            sequence=self.seq_provider.to_pypulseq(),
            session_path=self.session_path,
            meta={"device_configuration": self.config.model_dump()},
            acquisition_parameters=self.sequence.parameter,
        )

    def get_device_configuration(self) -> NexusConfiguration:
        """Get nexus device configuration."""
        return self.config

    def plot_waveforms(
        self,
        time_range: tuple[float, float],
    ) -> tuple[mpl.figure.Figure, np.ndarray] | None:
        """Plot internally stored waveforms."""
        if self.sequence is not None:
            return plot_unrolled_sequence(self.sequence, time_range=time_range)
        self.log.warning("No sequence to plot. Set sequence first.")
        return None
