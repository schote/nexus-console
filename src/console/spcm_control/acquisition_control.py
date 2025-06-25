"""Acquisition Control Class."""

import logging
import logging.config
import os
import threading
import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from queue import Queue
from signal import SIG_IGN, SIGINT, signal

import numpy as np
from numpy.fft import fft, fftshift, ifft, ifftshift
from scipy.signal import decimate

import console
from console.interfaces.acquisition_data import AcquisitionData
from console.interfaces.acquisition_parameter import AcquisitionParameter, DDCMethod
from console.interfaces.unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.utilities import QUEUE, ddc
from console.utilities.filter import filter_function
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
        self.session_path = Path(nexus_data_dir) / session_folder_name
        self.session_path.mkdir(exist_ok=True)
        if not self.session_path.is_dir():
            self.session_path.mkdir(parents=True)
            self.session_path.chmod(0o775)  # noqa: S103

        self._setup_logging(console_level=console_log_level, file_level=file_log_level)
        self.log = logging.getLogger("AcqCtrl")
        self.log.info("--- Acquisition control started\n")

        # Define global acquisition parameter object
        try:
            console.parameter = AcquisitionParameter.load(nexus_data_dir)
        except FileNotFoundError as exc:
            self.log.warning("Acquisition parameter state could not be loaded from dir: %s.\
                Creating new acquisition parameter object.", exc)
            console.parameter = AcquisitionParameter()
        console.parameter.save_on_mutation = True

        # Store parameter hash to detect when a sequence needs to be recalculated
        self._current_parameter_hash: int = hash(console.parameter)

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
        self.acq_finished = False
        self.queue = QUEUE

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

    def set_sequence(self, sequence: str | Sequence, num_repetitions: int) -> None:
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
        self._current_parameter_hash = hash(console.parameter)
        self.unrolled_seq = self.seq_provider.unroll_sequence(num_repetitions=num_repetitions)
        self.log.info("Sequence duration: %s s", self.unrolled_seq.duration)

    def run(self, return_unprocessed: bool = False) -> AcquisitionData:
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

        if self._current_parameter_hash != hash(console.parameter):
            # Redo sequence unrolling in case acquisition parameters changed, i.e. different hash
            self.unrolled_seq = None
            self.log.info(
                "Unrolling sequence: %s", self.seq_provider.definitions["Name"].replace(" ", "_")
            )
            # Update acquisition parameter hash value
            self._current_parameter_hash = hash(console.parameter)
            self.unrolled_seq = self.seq_provider.unroll_sequence()
            self.log.info("Sequence duration: %s s", self.unrolled_seq.duration)

        # Define timeout for acquisition process: 10 sec + sequence duration
        timeout = 10 + self.unrolled_seq.duration

        # Initialize variables
        self._unproc = []
        self._raw = []
        self.acq_finished = False

        processing_thread = threading.Thread(
            target=self.post_processing,
            args=(console.parameter, self.queue, return_unprocessed),
            daemon=True,
        )
        processing_thread.start()

        for k in range(console.parameter.num_averages):
            self.log.info("Acquisition %s/%s", k + 1, console.parameter.num_averages)

            # Start masurement card operations
            self.rx_card.start_operation()
            time.sleep(1)
            self.tx_card.start_operation(self.unrolled_seq)

            # Get start time of acquisition
            time_start = time.time()

            while (num_gates := self.rx_card.gates_received) < self.unrolled_seq.adc_count or num_gates == 0:
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

            self.tx_card.stop_operation()
            self.rx_card.stop_operation()

            # Wait for end of processing
            self.acq_finished = True
            processing_thread.join()

            if console.parameter.averaging_delay > 0:
                time.sleep(console.parameter.averaging_delay)

        return AcquisitionData(
            _raw=self._raw,
            unprocessed_data=self._unproc,
            sequence=self.seq_provider,
            session_path=str(self.session_path),
            meta={
                self.tx_card.__name__: self.tx_card.dict(),
                self.rx_card.__name__: self.rx_card.dict(),
                self.seq_provider.__name__: self.seq_provider.dict()
            },
            dwell_time=console.parameter.decimation / self.f_spcm,
            acquisition_parameters=console.parameter,
        )

    @staticmethod
    def process_channels(
        data: np.ndarray,
        ref_dec: np.ndarray,
        scaling: np.float64,
        f_spcm: float,
        parameter: AcquisitionParameter
    ):
        """Process a channel's data.

        Parameters
        ----------
        data
            Channel's data as an np.ndarray()
        ref_dec
            Decimated reference data.
        scaling
            Scaling factor of the channel. Allow to convert RxCard data to mV
        f_spcm
            RxCard sampling frequency
        parameter
            Acquisition parameter object

        Returns
        -------
            Processed channel data.
        """
        # Convert data to mV
        data = data.astype(np.int16) * scaling

        # Demodulation
        data = data * np.exp(-2j * np.pi * np.arange(data.shape[-1]) * parameter.larmor_frequency / f_spcm)

        # Decimation
        match console.parameter.ddc_method:
            case DDCMethod.CIC:
                data = ddc.filter_cic_fir_comp(data, decimation=parameter.decimation, number_of_stages=5)
            case DDCMethod.AVG:
                data = ddc.filter_moving_average(data, decimation=parameter.decimation, overlap=8)
            case _:
                data = decimate(data, q=parameter.decimation, ftype="fir")

        # Apply phase correction with mean value
        # A factor 2 is added to compensate for the halving due to the processing.
        data = data * 2 * np.exp(-1j * np.angle(ref_dec))

        # Filter data in the frequential domain
        data_fft = fftshift(fft(data))
        filter = filter_function(data.shape[-1])  # creating filter reponse
        data_fft = data_fft * filter  # filtering
        data = ifft(ifftshift(data_fft))

        return data

    def post_processing(self, parameter: AcquisitionParameter, queue: Queue, return_unprocessed: bool) -> None:
        """Proces acquired NMR data.

        Data is sorted according to readout size which might vary between different readout windows.
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

        Reference signal is stored in the last entry of the coil dimension of unprocessed data.

        Parameters
        ----------
        parameter
            Acquisition parameter
        """
        gate_sizes = []
        gates_received = 0
        raw_list: list = []
        unproc_list: list = []

        with Pool(processes=8, initializer=signal, initargs=(SIGINT, SIG_IGN)) as pool:
            while True:
                # Stop processing if everything processed and acquisition finished
                if gates_received >= self.rx_card.gates_received and self.acq_finished is True:
                    self._raw = [np.concatenate(r, axis=2) for r in raw_list]
                    if return_unprocessed:
                        self._unproc = [np.concatenate(r, axis=2) for r in unproc_list]
                    break

                if not queue.empty():
                    # Get gate data
                    gate_data = queue.get()
                    gate_length = gate_data.shape[-1]
                    gates_received += 1

                    # Extract and decimate reference signal
                    _ref = (gate_data[1, ...].astype(np.uint16) >> 15).astype(float)[None, ...]
                    ref_dec = decimate(_ref, q=parameter.decimation, ftype="fir")[None, ...]

                    # Remove digital signal from channel 1
                    gate_data[1, ...] = gate_data[1, ...] << 1

                    # Define channel dependent scaling
                    scaling = np.array(self.rx_card.rx_scaling[:self.rx_card.num_channels.value])

                    # Prepare arguments for parallel processing
                    args = [
                        (gate_data[ch, ...], ref_dec, scaling[ch], self.f_spcm, parameter)
                        for ch in range(gate_data.shape[0])
                    ]

                    # Parallel processing with starmap
                    data = pool.starmap(self.process_channels, args)

                    # Concatenate data together
                    data = np.concatenate(data, axis=0)
                    data_array = np.asarray(data)

                    # Prepare unprocessed data if needed
                    if return_unprocessed:
                        gate_data = gate_data.astype(np.int16) * np.expand_dims(scaling, axis=-1)
                        gate_data = np.concatenate((gate_data, _ref), axis=0)
                        gate_data = np.expand_dims(gate_data, 1)

                    # If the data has a new gate_length
                    if gate_length not in gate_sizes:
                        gate_sizes.append(gate_length)
                        raw_list.append([data_array[None, ...]])

                        if return_unprocessed:
                            unproc_list.append([gate_data[None, ...]])

                    else:  # If data with this gate_length has already been received
                        # Get index of this gate_length
                        _gate_index = gate_sizes.index(gate_length)

                        # Concatenate the data to the _raw object at the right gate_length index
                        raw_list[_gate_index].append(data_array[None, ...])

                        # If return processed is true, also add unprocessed data at the right index
                        if return_unprocessed:
                            unproc_list[_gate_index].append(gate_data[None, ...])
