"""Acquisition Control Class."""

import logging
import os
import time

import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.ddc import apply_ddc
from console.spcm_control.interface_acquisition_data import AcquisitionData
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.utilities.load_config import get_instances


class AcquistionControl:
    """Acquisition control class.

    The main functionality of the acquisition control is to orchestrate transmit and receive cards using
    ``TxCard`` and ``RxCard`` instances.

    TODO: Implementation of logging mechanism.
    Use two logs: a high level one as lab-book and a detailed one for debugging.
    """

    def __init__(
        self,
        configuration_file: str = "../../../device_config.yaml",
        file_log_level: int = logging.INFO,
        consol_log_level: int = logging.INFO,
    ):
        """Construct acquisition control class.

        Create instances of sequence provider, tx and rx card.
        Setup the measurement cards and get parameters required for a measurement.

        Parameters
        ----------
        configuration_file
            Path to configuration yaml file which is used to create measurement card and sequence
            provider instances.
        """
        self._setup_logging(console_level=consol_log_level, file_level=file_log_level)
        self.log = logging.getLogger("AcqCtrl")

        # Get instances from configuration file
        ctx = get_instances(configuration_file)
        self.seq_provider: SequenceProvider = ctx[0]
        self.tx_card: TxCard = ctx[1]
        self.rx_card: RxCard = ctx[2]

        # Setup the cards
        self.is_setup: bool = False
        if self.tx_card.connect() and self.rx_card.connect():
            self.log.info("Setup of measurement cards successful.")
            self.is_setup = True

        # Get the rx sampling rate for DDC
        self.f_spcm = self.rx_card.sample_rate * 1e6
        # Set sequence provider max. amplitude per channel according to values from tx_card
        self.seq_provider.max_amp_per_channel = self.tx_card.max_amplitude

        self.unrolled_sequence: UnrolledSequence | None = None

        # Attributes for data and dwell time of downsampled signal
        self._raw: np.ndarray | None = None

    def __del__(self):
        """Class destructor disconnecting measurement cards."""
        if self.tx_card:
            self.tx_card.disconnect()
        if self.rx_card:
            self.rx_card.disconnect()
        self.log.info("Measurement cards disconnected.")

    def _setup_logging(
        self, console_level: int, file_level: int, logfile_path: str = "/home/schote01/spcm-console/"
    ) -> None:
        # Check if log levels are valid
        if console_level not in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]:
            raise ValueError("Invalid console log level")
        if file_level not in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]:
            raise ValueError("Invalid file log level")

        # Disable existing loggers
        logging.config.dictConfig({"version": 1, "disable_existing_loggers": True})  # type: ignore[attr-defined]

        # Setup log file path
        logfile_path = os.path.join(logfile_path, "")
        os.makedirs(logfile_path, exist_ok=True)

        # Set up logging to file
        logging.basicConfig(
            level=file_level,
            format="%(asctime)s %(name)-7s: %(levelname)-8s >> %(message)s",
            datefmt="%d-%m-%Y, %H:%M",
            filename=f"{logfile_path}console.log",
            filemode="w",
        )

        # Define a Handler which writes INFO messages or higher to the sys.stderr
        console = logging.StreamHandler()
        console.setLevel(console_level)
        formatter = logging.Formatter("%(name)-7s: %(levelname)-8s >> %(message)s")
        console.setFormatter(formatter)
        logging.getLogger("").addHandler(console)

    def run(self, sequence: str, parameter: AcquisitionParameter) -> AcquisitionData:
        """Run an acquisition job.

        Parameters
        ----------
        sequence
            Path to pulseq sequence file.
        parameter
            Set of acquisition parameters which are required for the acquisition.

        Raises
        ------
        RuntimeError
            The measurement cards are not setup properly.
        FileNotFoundError
            Invalid file ending of sequence file.
        """
        try:
            if not self.is_setup:
                raise RuntimeError("Measurement cards are not setup.")

            if not sequence.endswith(".seq"):
                raise FileNotFoundError("Invalid sequence file.")
        except Exception as exc:
            self.log.exception(exc, exc_info=True)
            raise exc

        self.seq_provider.read(sequence)
        self.seq_provider.output_limits = self.tx_card.max_amplitude
        sqnc: UnrolledSequence = self.seq_provider.unroll_sequence(
            larmor_freq=parameter.larmor_frequency, b1_scaling=parameter.b1_scaling, fov_scaling=parameter.fov_scaling
        )
        # Save unrolled sequence
        self.unrolled_sequence = sqnc if sqnc else None

        # Define timeout for acquisition process: 5 sec + sequence duration
        timeout = 5 + sqnc.duration

        self._raw = None

        for k in range(parameter.num_averages):
            self.log.info("Acquisition %s/%s", k + 1, parameter.num_averages)

            # Start masurement card operations
            self.rx_card.start_operation()
            time.sleep(0.5)
            self.tx_card.start_operation(sqnc)

            # Get start time of acquisition
            time_start = time.time()

            while len(self.rx_card.rx_data) < sqnc.adc_count:
                # Delay poll by 10 ms
                time.sleep(0.01)

                if len(self.rx_card.rx_data) >= sqnc.adc_count:
                    break

                if time.time() - time_start > timeout:
                    # Could not receive all the data before timeout
                    self.log.warning(
                        "Acquisition Timeout: Only received %s/%s adc events",
                        len(self.rx_card.rx_data),
                        sqnc.adc_count,
                        stack_info=True,
                    )
                    break

            if len(self.rx_card.rx_data) > 0:
                self.post_processing(parameter)

            self.tx_card.stop_operation()
            self.rx_card.stop_operation()

        if self._raw is None:
            self._raw = np.empty([])
            self.log.warning("Empty raw data array", stack_info=True)

        return AcquisitionData(
            raw=self._raw,
            sequence=self.seq_provider,
            # Dwell time of down sampled signal: 1 / (f_spcm / kernel_size)
            dwell_time=parameter.downsampling_rate / self.f_spcm,
            acquisition_parameters=parameter,
        )

    def post_processing(self, parameter: AcquisitionParameter) -> None:
        """Perform data post processing.

        Apply DDC what contains demodulation, down-sampling and filtering for each gate and coil array.
        This step further includes the post-processing of the reference signal and phase correction.

        Parameters
        ----------
        parameter
            Acquisition parameters
        """
        kernel_size = int(2 * parameter.downsampling_rate)
        f_0 = parameter.larmor_frequency
        ro_start = int(parameter.adc_samples / 2)
        raw_list: list = []

        try:
            if not self.rx_card.rx_data:
                raise IndexError("No gate data available")
            if not (num_channels := len(self.rx_card.rx_data[0])) >= 1:
                raise IndexError("No channel data available")
            self.log.debug(
                "Post processing > Gates: %s; Coils: %s", len(self.rx_card.rx_data), len(self.rx_card.rx_data[0])
            )
        except IndexError as err:
            self.log.exception(err, exc_info=True)
            raise err

        for k, gate in enumerate(self.rx_card.rx_data):
            raw_channel_list = []

            # Process reference signal
            _ref = np.array(gate[0]).astype(np.uint16) >> 15
            self.log.debug("Gate %s: ADC samples per channel before down-sampling: %s", k, _ref.size)
            # Calculate start point of readout for adc truncation
            _ref = apply_ddc(_ref, kernel_size=kernel_size, f_0=f_0, f_spcm=self.f_spcm)
            ro_start = int(_ref.size / 2 - parameter.adc_samples / 2)
            _ref = _ref[ro_start : ro_start + parameter.adc_samples]

            # Process channel 0: Read signal data, apply DDC, truncate and append to list
            # Channel 0 should always exist
            _tmp = (np.array(gate[0]) << 1).astype(np.int16) * self.rx_card.rx_scaling[0]
            _tmp = apply_ddc(_tmp, kernel_size=kernel_size, f_0=f_0, f_spcm=self.f_spcm)
            _tmp = _tmp[ro_start : ro_start + parameter.adc_samples]
            raw_channel_list.append(_tmp * np.exp(-1j * np.angle(_ref)))

            if num_channels > 1:
                # Read all other channels if more than one channel is enabled
                # Separation of channel 0 and all other required, since channel 0 contains digital reference
                for channel_idx in range(len(gate) - 1):
                    # Read signal data, apply DDC and append to signal data list
                    _tmp = (np.array(gate[channel_idx + 1])).astype(np.int16) * self.rx_card.rx_scaling[channel_idx + 1]
                    _tmp = apply_ddc(_tmp, kernel_size=kernel_size, f_0=f_0, f_spcm=self.f_spcm)
                    _tmp = _tmp[ro_start : ro_start + parameter.adc_samples]
                    raw_channel_list.append(_tmp * np.exp(-1j * np.angle(_ref)))

            # Stack coils in axis 0: [coils, ro]
            raw_list.append(np.stack(raw_channel_list, axis=0))

        # Stack phase encoding in axis 1: [coil, pe, ro]
        raw: np.ndarray = np.stack(raw_list, axis=1)

        # Assign processed data to private class attributes
        # Stack average dimension
        self._raw = raw[None, ...] if self._raw is None else np.concatenate((self._raw, raw[None, ...]), axis=0)