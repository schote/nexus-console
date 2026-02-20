"""Implementation of processing worker."""

import logging
import multiprocessing
import traceback


class ProcessingWorker(multiprocessing.Process):
    """Worker process for processing RxData objects."""

    def __init__(self, processing_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue):
        """Initialize the processing worker."""
        super().__init__(name="ProcessingWorker")
        self.processing_queue = processing_queue
        self.result_queue = result_queue
        self.log = logging.getLogger(self.name)

    def run(self):
        """Main loop of the processing worker."""
        self.log.info("ProcessingWorker started")
        while True:
            try:
                rx_data = self.processing_queue.get()
                if rx_data is None:  # Shutdown sentinel
                    self.log.info("ProcessingWorker received shutdown signal")
                    break

                # Process the data
                # This will back-fill the SharedMemory via the RxData properties
                rx_data.process_data()

                # Push the Metadata-only object to the result queue
                self.result_queue.put(rx_data)

            except Exception as e:
                self.log.error(f"Error in ProcessingWorker: {e}")
                self.log.error(traceback.format_exc())

        self.log.info("ProcessingWorker shut down")
