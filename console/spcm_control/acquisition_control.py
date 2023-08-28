import threading

import numpy as np

from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard


class AcquistionControl:
    def __init__(self, tx_engine: TxCard, rx_engine: RxCard):
        self.tx_engine = tx_engine
        self.rx_engine = rx_engine

        # Event is thread-safe boolean variable, which can be used to interrupt a thread
        # We need this to interrupt an acquisition
        self.interrupt_acq = threading.Event()

    def acquire(self, sequence: np.array = np.arange(10)) -> list:
        # Initialize empty data array
        data = []

        # Connect to cards
        self.tx_engine.connect()
        self.rx_engine.connect()

        # Create and start threads...
        tx_thread = threading.Thread(
            target=self.tx_engine.operate, args=(sequence,)
        )  # args=(sequence.rollout_sequence(), )
        rx_thread = threading.Thread(target=self.rx_engine.operate, args=(data, ))
        
        rx_thread.start()
        tx_thread.start()
        

        # Report progress
        # while tx_thread.is_alive():
        #     print(f"Ctrl: Running sequence... {self.tx_engine.progress*100}%")
        #     time.sleep(0.1)

        # Wait for threads
        tx_thread.join()
        rx_thread.join()

        # Disconnect cards and return acquired data
        self.tx_engine.disconnect()
        self.rx_engine.disconnect()

        return data
