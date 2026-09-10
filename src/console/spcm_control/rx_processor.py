"""Processing worker for RxData objects using a persistent process pool."""

import logging
import multiprocessing
import signal
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

    ``submit()`` is thread-safe and can be called directly from the rx_card
    streaming thread.  ``collect()`` is called after all averages complete
    (by which point every streaming thread has been joined) and waits for
    all outstanding futures.

    Usage
    -----
    >>> processor = RxProcessor(num_workers=2)
    >>> processor.start()
    >>> # pass processor.submit as submit_fn to rx_card.start_operation()
    >>> results = processor.collect(expected_count=N, timeout=T)
    >>> # Repeat collect() for each subsequent run.
    >>> processor.shutdown()
    """

    def __init__(self, num_workers: int = 1) -> None:
        self._num_workers = num_workers
        self._executor: ProcessPoolExecutor | None = None
        self._futures: dict[int, Future] = {}

    def start(self) -> None:
        """Create the process pool and pre-warm all worker processes."""
        self._executor = ProcessPoolExecutor(
            max_workers=self._num_workers, mp_context=_mp_ctx, initializer=_worker_init
        )
        # Submit one no-op per worker to force all processes to spawn now so
        # the first real acquisition doesn't pay the spawn cost.
        warm = [self._executor.submit(_noop) for _ in range(self._num_workers)]
        for f in warm:
            f.result()
        log.debug("RxProcessor pool started with %d worker(s)", self._num_workers)

    def submit(self, index: int, rx_data: RxData, store_unprocessed: bool) -> None:
        """Submit one RxData item for async processing.

        Thread-safe: may be called from any thread, including the rx_card
        streaming thread.
        """
        if self._executor is None:
            raise RuntimeError("RxProcessor is not started. Call start() first.")
        self._futures[index] = self._executor.submit(_process_one, index, rx_data, store_unprocessed)

    def collect(self, expected_count: int, timeout: float = 60.0) -> list[RxData]:
        """Wait for all submitted futures and return results ordered by index.

        Parameters
        ----------
        expected_count
            Number of RxData items expected in this batch.
        timeout
            Maximum seconds to wait for all futures to complete.

        Returns
        -------
            List of processed RxData objects ordered by global index.
        """
        done, not_done = wait(list(self._futures.values()), timeout=timeout)
        if not_done:
            log.warning("%d future(s) did not complete within timeout", len(not_done))

        results: dict[int, RxData] = {}
        for future in done:
            idx, rx_data = future.result()
            results[idx] = rx_data

        if len(results) != expected_count:
            log.warning("Expected %d items but collected %d", expected_count, len(results))

        self._futures.clear()
        return [results[i] for i in range(expected_count) if i in results]

    def shutdown(self) -> None:
        """Shut down the process pool."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
            log.debug("RxProcessor pool shut down")
