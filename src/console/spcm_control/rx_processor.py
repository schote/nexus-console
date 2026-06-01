"""Processing worker for RxData objects using a persistent process pool."""

import logging
import multiprocessing
import queue
import signal
import threading
from concurrent.futures import Future, ProcessPoolExecutor, wait

from console.interfaces.rx_data import RxData

log = logging.getLogger("RxProc")

# 'spawn' is the only safe start method on Windows and avoids fork-related
# deadlocks in multi-threaded processes on Linux.
_mp_ctx = multiprocessing.get_context("spawn")


def _worker_init() -> None:
    """Ignore SIGINT in worker processes so Ctrl-C is handled by the main process only."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _noop() -> None:
    """No-op submitted to pre-warm pool worker processes."""


def _process_one(index: int, rx_data: RxData, store_unprocessed: bool) -> tuple[int, RxData]:
    """Process a single RxData item inside a worker process."""
    rx_data.process_data(store_unprocessed=store_unprocessed)
    rx_data.materialize(keep=store_unprocessed)
    return index, rx_data


class RxProcessor:
    """Processes RxData items using a persistent pool of worker processes.

    A feeder thread drains ``input_queue`` and submits each item to a
    ``ProcessPoolExecutor``, allowing multiple ADC events to be processed
    concurrently.  The pool workers are kept alive across acquisition runs,
    eliminating per-run process-spawn overhead.

    Usage
    -----
    >>> processor = RxProcessor(num_workers=2)
    >>> processor.start()
    >>> # --- acquisition run ---
    >>> processor.begin_batch(store_unprocessed=False)
    >>> # rx_card pushes (index, rx_data) to processor.input_queue ...
    >>> results = processor.collect_batch(expected_count=N, timeout=T)
    >>> # Repeat begin_batch / collect_batch for each subsequent run.
    >>> processor.shutdown()
    """

    def __init__(self, num_workers: int = 1) -> None:
        self.input_queue: queue.Queue = queue.Queue()
        self._num_workers = num_workers
        self._executor: ProcessPoolExecutor | None = None
        self._futures: dict[int, Future] = {}
        self._feeder: threading.Thread | None = None
        self._batch_done = threading.Event()
        self._store_unprocessed: bool = False

    def start(self) -> None:
        """Create the process pool and pre-warm all worker processes."""
        self._executor = ProcessPoolExecutor(max_workers=self._num_workers, mp_context=_mp_ctx, initializer=_worker_init)
        # Submit one no-op per worker to force all processes to spawn now so
        # the first real acquisition doesn't pay the spawn cost.
        warm = [self._executor.submit(_noop) for _ in range(self._num_workers)]
        for f in warm:
            f.result()
        log.debug("RxProcessor pool started with %d worker(s)", self._num_workers)
        self._start_feeder()

    def begin_batch(self, store_unprocessed: bool = False) -> None:
        """Prepare for a new acquisition batch.

        Must be called before the rx_card starts pushing items to
        ``input_queue``.
        """
        self._store_unprocessed = store_unprocessed

    def collect_batch(self, expected_count: int, timeout: float = 60.0) -> list[RxData]:
        """Signal end of batch, collect results, and reset for the next run.

        Parameters
        ----------
        expected_count
            Number of RxData items expected in this batch.
        timeout
            Maximum seconds to wait for all futures to complete.

        Returns
        -------
            List of processed RxData objects ordered by global index.

        Raises
        ------
        RuntimeError
            If the feeder thread does not finish within *timeout* seconds.
        """
        self.input_queue.put(None)  # sentinel — tells feeder the batch is over

        if not self._batch_done.wait(timeout=timeout):
            log.error("Feeder thread did not finish within %.1fs", timeout)
            raise RuntimeError("RxProcessor feeder timed out")

        done, not_done = wait(list(self._futures.values()), timeout=timeout)
        if not_done:
            log.warning("%d future(s) did not complete within timeout", len(not_done))

        results: dict[int, RxData] = {}
        for future in done:
            idx, rx_data = future.result()
            results[idx] = rx_data

        if len(results) != expected_count:
            log.warning("Expected %d items but collected %d", expected_count, len(results))

        self._start_feeder()  # reset for next batch
        return [results[i] for i in range(expected_count) if i in results]

    def shutdown(self) -> None:
        """Shut down the process pool."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
            log.debug("RxProcessor pool shut down")

    def _start_feeder(self) -> None:
        """(Re)start the feeder thread for a new batch."""
        self._futures.clear()
        self._batch_done.clear()
        self._feeder = threading.Thread(target=self._feeder_loop, daemon=True)
        self._feeder.start()

    def _feeder_loop(self) -> None:
        """Drain input_queue and submit items to the executor until sentinel."""
        while True:
            try:
                item = self.input_queue.get(timeout=0.05)
            except queue.Empty:
                continue
            if item is None:
                self._batch_done.set()
                return
            index, rx_data = item
            future = self._executor.submit(_process_one, index, rx_data, self._store_unprocessed)
            self._futures[index] = future
