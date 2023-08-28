"""Acquisition Control Class."""

import threading

import numpy as np

from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard


class AcquistionControl:
    """Acquisition control class.

    The main functionality of the acquisition control is to orchestrate transmit and receive cards using
    ``TxCard`` and ``RxCard`` instances.
    """

    def __init__(self, tx_engine: TxCard, rx_engine: RxCard):
        self.tx_engine = tx_engine
        self.rx_engine = rx_engine

        # Event is thread-safe boolean variable, which can be used to interrupt a thread
        # We need this to interrupt an acquisition
        self.interrupt_acq = threading.Event()

    def acquire(self, sequence: np.ndarray) -> str:
        """Handles the acquisition of an unrolled pulseq sequence.

        This function is yet a prototypic skeleton.

        Parameters
        ----------
        sequence
            Numpy array with unrolled replay data (pulseq sequence)

        Returns
        -------
            Path of the receive data file as string
        """
        # Define filename for the acquired data and return it after acquisition was successful
        data_file = ""

        # Connect to cards
        self.tx_engine.connect()
        self.rx_engine.connect()

        # Create and start threads...
        tx_thread = threading.Thread(target=self.tx_engine.start_operation, args=(sequence,))
        rx_thread = threading.Thread(target=self.rx_engine.start_operation)

        rx_thread.start()
        tx_thread.start()

        # TODO: Report progress, wait until operation is finished
        # => Idea: Calculate estimated acquisition time and join threads after this timeout
        # Maybe this is even part of the TX card operate() routine
        # Stop RX card dependent on the TX card

        # Wait for threads
        tx_thread.join()
        rx_thread.join()

        # Disconnect cards and return acquired data
        self.tx_engine.disconnect()
        self.rx_engine.disconnect()

        return data_file
