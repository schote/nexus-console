"""Acquisition Control Class."""

import copy
import functools
import logging
import logging.config
import os
import time
from datetime import datetime
from pathlib import Path
from typing import cast

import matplotlib as mpl
import numpy as np
from pypulseq import Opts

from console.interfaces.acquisition_data import AcquisitionData
from collections.abc import Callable
from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.device_configuration import NexusConfiguration
from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.rx_device import RxCard
from console.spcm_control.rx_processor import RxProcessor
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

        self.config: NexusConfiguration = load_nexus_config(configuration_file)
        # Create sequence provider instance
        self.seq_provider: SequenceProvider = SequenceProvider(
            gradient_efficiency=self.config.tx.gradient_efficiency,
            gpa_gain=self.config.tx.gpa_gain,
            gradients_50ohms=self.config.tx.gradients_terminated_50ohm,
            rf_50ohms=self.config.tx.rf_terminated_50ohm,
            gradient_output_limits=self.config.tx.channel_max_amplitude[1:],
            rf_output_limit=self.config.tx.channel_max_amplitude[0],
            spcm_dwell_time=1 / (self.config.tx.sampling_rate * 1e6),
            rf_to_mvolt=self.config.tx.rf_to_mvolt,
            system=self.config.system.get_opts(),
            rf_gain_lut_path=self.config.tx.rf_gain_lut_path,
        )
        # Create transmit card instance
        self.tx_card: TxCard = TxCard(
            path=self.config.tx.device_path,
            max_amplitude=self.config.tx.channel_max_amplitude,
            filter_type=self.config.tx.channel_filter_type,
            sample_rate=self.config.tx.sampling_rate,
        )
        # Create receive card instance
        self.rx_card: RxCard = RxCard(
            path=self.config.rx.device_path,
            sample_rate=self.config.rx.sampling_rate,
            channel_enable=self.config.rx.channel_enable,
            max_amplitude=self.config.rx.channel_max_amplitude,
            impedance_50_ohms=self.config.rx.channel_terminated_50ohm,
        )

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

        # Persistent processing worker pool (None when num_processing_workers == 0)
        num_workers = self.config.rx.num_processing_workers
        if num_workers > 0:
            self._processor: RxProcessor | None = RxProcessor(num_workers=num_workers)
            self._processor.start()
            self.log.info("RxProcessor pool started with %d worker(s)", num_workers)
        else:
            self._processor = None
            self.log.info("RxProcessor disabled — using in-process fallback")

    def __del__(self):
        """Class destructor disconnecting measurement cards."""
        if self.tx_card:
            self.tx_card.disconnect()
        if self.rx_card:
            self.rx_card.disconnect()
        if self._processor is not None:
            self._processor.shutdown()
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
        seq_name = str(self.seq_provider.get_definition("Name"))
        if not seq_name:
            seq_name = str(self.seq_provider.get_definition("name"))
            if not seq_name:
                seq_name = "unknown"
        self.log.info("Unrolling sequence: %s", seq_name.replace(" ", "_"))
        # Calculate sequence with parameter
        self.sequence = self.seq_provider.unroll_sequence(parameter=parameter)
        self.log.info("Sequence duration: %s s", self.sequence.duration)

    def run(self, store_unprocessed: bool = False, progress_callback: Callable[[int], None] | None = None) -> AcquisitionData:
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

        self.store_unprocessed = store_unprocessed

        self.num_adc_events = len(self.sequence.rx_data)

        submit_fn = (
            functools.partial(self._processor.submit, store_unprocessed=store_unprocessed)
            if self._processor is not None else None
        )

        # Set gradient offset values
        self.tx_card.set_gradient_offsets(
            offsets=self.sequence.parameter.gradient_offset,
            is_50ohms=self.config.tx.gradients_terminated_50ohm,
        )

        # Accumulates (global_index, rx_data) pairs when processing in the main process
        inprocess_items: list[tuple[int, RxData]] = []

        for k in range(self.sequence.parameter.num_averages):
            rx_data_list = copy.deepcopy(self.sequence.rx_data)
            for data in rx_data_list:
                data.average_index = k
                data.larmor_frequency = self.sequence.parameter.larmor_frequency

            self.rx_card.rx_data = cast(list[RxData | None], rx_data_list)

            self.log.info("Acquisition %s/%s", k + 1, self.sequence.parameter.num_averages)

            self.rx_card.start_operation(submit_fn=submit_fn, index_offset=k * self.num_adc_events)

            while not self.rx_card.is_receiving.is_set():
                time.sleep(0.01)
            self.tx_card.start_operation(self.sequence)

            # Get start time of acquisition
            time_start = time.time()
            last_progress_step = -1

            while (num_gates := self.rx_card.total_gates) < self.sequence.adc_count or num_gates == 0:
                if callable(progress_callback):
                    progress = int(100 * num_gates / self.sequence.adc_count)
                    if progress > last_progress_step + 2:
                        last_progress_step = progress
                        progress_callback(progress)

                # Delay poll by 100 ms
                time.sleep(0.1)

                if (time.time() - time_start) > timeout:
                    # Could not receive all the data before timeout
                    self.log.warning(
                        "Acquisition Timeout: Only received %s/%s adc events", num_gates, self.sequence.adc_count
                    )
                    break

                if num_gates >= self.sequence.adc_count and num_gates > 0:
                    break

            if self._processor is None:
                for j, rx in enumerate(rx_data_list):
                    if rx is not None:
                        inprocess_items.append((k * self.num_adc_events + j, rx))

            self.rx_card.rx_data = None

            self.tx_card.stop_operation()
            self.rx_card.stop_operation()

            if self.sequence.parameter.averaging_delay > 0:
                time.sleep(self.sequence.parameter.averaging_delay)

        # Reset gradient offset values
        self.tx_card.set_gradient_offsets(
            offsets=Dimensions(x=0, y=0, z=0),
            is_50ohms=self.config.tx.gradients_terminated_50ohm,
        )

        total_expected = self.sequence.parameter.num_averages * self.num_adc_events
        total_raw_samples = (
            sum(rx.num_samples_raw for rx in self.sequence.rx_data) * self.sequence.parameter.num_averages
        )
        processing_timeout = max(30.0, total_raw_samples * 1e-5)

        if self._processor is not None:
            self.receive_data = self._processor.collect(
                expected_count=total_expected,
                timeout=processing_timeout,
            )
        else:
            for _, rx in inprocess_items:
                rx.process_data(store_unprocessed=store_unprocessed)
                rx.materialize(keep=store_unprocessed)
            self.receive_data = [rx for _, rx in sorted(inprocess_items, key=lambda x: x[0])]

        if len(self.receive_data) == 0:
            raise RuntimeError("No ADC events present")

        self.log.debug("Total number of ADC events: %d", len(self.receive_data))

        try:
            averages = [data.average_index for data in self.receive_data]
            if not (np.unique(averages).size == self.sequence.parameter.num_averages):
                averages_idc = np.arange(self.sequence.parameter.num_averages)
                missing_averages = [avg + 1 for avg in averages_idc if avg not in averages]
                raise ValueError(f"Missing averages: {missing_averages} out of {self.sequence.parameter.num_averages}")
        except ValueError as err:
            self.log.exception(err, exc_info=True)
            raise err

        return AcquisitionData(
            receive_data=self.receive_data,
            sequence=self.seq_provider.to_pypulseq(),
            session_path=self.session_path,
            meta={"device_configuration": self.config.model_dump()},
            acquisition_parameters=self.sequence.parameter,
        )

    def get_device_configuration(self) -> NexusConfiguration:
        """Get nexus device configuration."""
        return self.config

    def get_sequence_system(self) -> Opts:
        """Get pypulseq sequence system from sequence provider."""
        return self.seq_provider.system

    def plot_waveforms(
        self,
        time_range: tuple[float, float],
    ) -> tuple[mpl.figure.Figure, np.ndarray] | None:
        """Plot internally stored waveforms."""
        if self.sequence is not None:
            return plot_unrolled_sequence(self.sequence, time_range=time_range)
        self.log.warning("No sequence to plot. Set sequence first.")
        return None
