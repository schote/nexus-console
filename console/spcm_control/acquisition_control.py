"""Acquisition Control Class."""

import time

import numpy as np

from console.pulseq_interpreter.interface_unrolled_sequence import UnrolledSequence
from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.utilities.load_config import get_instances
from console.utilities.processing import apply_ddc


class AcquistionControl:
    """Acquisition control class.

    The main functionality of the acquisition control is to orchestrate transmit and receive cards using
    ``TxCard`` and ``RxCard`` instances.

    TODO: Implementation of logging mechanism.
    Use two logs: a high level one as lab-book and a detailed one for debugging.
    """

    def __init__(self, configuration_file: str):
        """Construct acquisition control class.

        Create instances of sequence provider, tx and rx card.
        Setup the measurement cards and get parameters required for a measurement.

        Parameters
        ----------
        configuration_file
            Path to configuration yaml file which is used to create measurement card and sequence
            provider instances.
        """
        # Get instances from configuration file
        ctx = get_instances(configuration_file)
        self.seq_provider: SequenceProvider = ctx[0]
        self.tx_card: TxCard = ctx[1]
        self.rx_card: RxCard = ctx[2]

        # Setup the cards
        self.is_setup: bool = False
        if self.tx_card.connect() and self.rx_card.connect():
            print("Setup of measurement cards successful.")
            self.is_setup = True

        # Get the rx sampling rate for DDC
        self.f_spcm = self.rx_card.sample_rate * 1e6
        # Set sequence provider max. amplitude per channel according to values from tx_card
        self.seq_provider.max_amp_per_channel = self.tx_card.max_amplitude

        # Read only attributes for data and dwell time of downsampled signal
        self._data: list = []
        self._dwell: float | None = None

    def __del__(self):
        """Class destructor."""
        if self.tx_card:
            self.tx_card.disconnect()
        if self.rx_card:
            self.rx_card.disconnect()
        print("Measurement cards disconnected.")

    @property
    def data(self) -> list[np.ndarray]:
        """Get data acquired by acquisition control, read-only property.

        Returns
        -------
            List of numpy arrays with acquired data.
        """
        return self._data

    @property
    def dwell_time(self) -> float | None:
        """Get dwell time of down-sampled data, read-only property.

        Returns
        -------
            Dwell time of down-sampled signal.
        """
        return self._dwell

    def run(self, sequence: str, parameter: AcquisitionParameter) -> None:
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
        if not self.is_setup:
            raise RuntimeError("Measurement cards are not setup.")

        if not sequence.endswith(".seq"):
            raise FileNotFoundError("Invalid sequence file.")

        self.seq_provider.read(sequence)
        self.seq_provider.rf_to_volt = parameter.b1_scaling
        self.seq_provider.grad_to_volt = parameter.fov_scaling.x
        sqnc: UnrolledSequence = self.seq_provider.unroll_sequence(
            larmor_freq=parameter.larmor_frequency, b1_scaling=parameter.b1_scaling, fov_scaling=parameter.fov_scaling
        )

        # Define timeout for acquisition process: 5 sec + sequence duration
        timeout = 5 + sqnc.duration

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
                # All the data was received, start post processing
                self._data = self.post_processing(self.rx_card.rx_data, parameter)
                break

            if time.time() - time_start > timeout:
                # Could not receive all the data before timeout
                print(f"Acquisition Timeout: Only received {len(self.rx_card.rx_data)}/{sqnc.adc_count} adc events...")
                if len(self.rx_card.rx_data) > 0:
                    self._data = self.post_processing(self.rx_card.rx_data, parameter)
                break

        self.tx_card.stop_operation()
        self.rx_card.stop_operation()

        # Dwell time of down sampled signal: 1 / (f_spcm / kernel_size)
        self._dwell = parameter.downsampling_rate / self.f_spcm

    def post_processing(self, data: list[np.ndarray], parameter: AcquisitionParameter) -> list[np.ndarray]:
        """Perform data post processing.

        Apply the digital downconversion, filtering an downsampling per numpy array in the list of the received data.

        Parameters
        ----------
        data
            Received list of adc data samples
        parameter
            Acquistion parameter to setup the filter

        Returns
        -------
            List of processed data arrays
        """
        processed: list = []
        kernel_size = int(2 * parameter.downsampling_rate)
        f_0 = parameter.larmor_frequency

        for samples in data:
            processed.append(apply_ddc(samples, kernel_size=kernel_size, f_0=f_0, f_spcm=self.f_spcm))

        return processed
