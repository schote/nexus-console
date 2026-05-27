"""Processing worker for RxData objects using multiprocessing."""

import logging
from multiprocessing import Process, Queue

from console.interfaces.rx_data import RxData

log = logging.getLogger("RxProc")


class RxProcessor:
    """Runs RxData.process_data() in a separate process fed by a queue.

    The RxCard pushes lightweight RxData items (with raw_data in shared memory)
    onto ``input_queue``. The worker process reattaches to the shared memory,
    processes the data, and puts the result on an internal result queue.

    Usage
    -----
    >>> processor = RxProcessor(store_unprocessed=False)
    >>> processor.start()
    >>> # ... RxCard pushes items to processor.input_queue ...
    >>> results = processor.stop_and_collect(expected_count=N, timeout=T)
    """

    def __init__(self, store_unprocessed: bool = False) -> None:
        self.input_queue: Queue = Queue()
        self._result_queue: Queue = Queue()
        self._store_unprocessed = store_unprocessed
        self._process: Process | None = None

    def start(self) -> None:
        """Start the worker process."""
        self._process = Process(
            target=self._worker_loop,
            args=(self.input_queue, self._result_queue, self._store_unprocessed),
            daemon=True,
        )
        self._process.start()
        log.debug("Processing worker started (PID %s)", self._process.pid)

    def stop_and_collect(self, expected_count: int, timeout: float = 60.0) -> list[RxData]:
        """Send sentinel, join worker, return results ordered by global index.

        Parameters
        ----------
        expected_count
            Total number of RxData items expected (num_averages*adc_count).
        timeout
            Maximum seconds to wait for the worker process to finish.

        Returns
        -------
            Ordered list of processed RxData objects.

        Raises
        ------
        RuntimeError
            If the worker times out.
        """
        # Signal worker to stop
        self.input_queue.put(None)

        if self._process is not None:
            self._process.join(timeout=timeout)
            if self._process.is_alive():
                log.error("Processing worker did not finish within %.1fs, terminating.", timeout)
                self._process.terminate()
                self._process.join(timeout=5)
                raise RuntimeError("RxProcessor worker timed out")

        # Collect all results
        results: dict[int, RxData] = {}
        while not self._result_queue.empty():
            idx, rx_data = self._result_queue.get_nowait()
            results[idx] = rx_data

        if len(results) != expected_count:
            log.warning(
                "Expected %d processed items but collected %d",
                expected_count,
                len(results),
            )

        # Return ordered by global index, skip missing
        return [results[i] for i in range(expected_count) if i in results]

    @staticmethod
    def _worker_loop(
        input_queue: Queue,
        result_queue: Queue,
        store_unprocessed: bool,
    ) -> None:
        """Worker loop running in a separate process."""
        processed_count = 0
        logger = logging.getLogger("RxProc")

        while True:
            item = input_queue.get()
            if item is None:
                logger.debug("Sentinel received, worker processed %d items", processed_count)
                break

            index, rx_data = item
            # __setstate__ has already called _attach_shm()

            try:
                # Validate that shared memory was attached successfully
                if rx_data._shm_name is not None and rx_data._shm is None:
                    raise RuntimeError(
                        f"Shared memory not attached for index {index}: "
                        f"name={rx_data._shm_name}, raw_data={'set' if rx_data.raw_data is not None else 'None'}"
                    )

                rx_data.process_data(store_unprocessed=store_unprocessed)
                processed_count += 1
                logger.debug("Processed item %d (total: %d)", index, processed_count)
            except Exception:
                logger.warning("Failed to process RxData index %d, continuing", index, exc_info=True)

            # Release shared memory; optionally copy raw_data to a regular array first.
            rx_data.materialize(keep=store_unprocessed)
            result_queue.put((index, rx_data))
