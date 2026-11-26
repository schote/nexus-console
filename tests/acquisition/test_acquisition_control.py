"""Tests of the shutdown and error handling of the acquisition control, with mocked cards."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from console.interfaces.dimensions import Dimensions
from console.spcm_control import acquisition_control
from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.rx_processor import RxProcessor


@pytest.fixture
def acq() -> AcquisitionControl:
    """Acquisition control with mocked cards, processor and sequence, bypassing the constructor."""
    acq = AcquisitionControl.__new__(AcquisitionControl)
    acq._run_lock = threading.Lock()
    acq._closed = False
    acq.log = MagicMock()
    acq.is_setup = True
    acq._processor = MagicMock()
    acq.config = SimpleNamespace(tx=SimpleNamespace(gradients_terminated_50ohm=False))
    acq.tx_card = MagicMock(worker=None)
    acq.rx_card = MagicMock(worker=MagicMock(), is_receiving=threading.Event())
    acq.rx_card.is_receiving.set()
    acq.sequence = MagicMock(duration=1.0, adc_count=1, rx_data=[])
    acq.sequence.parameter.num_averages = 2
    return acq


def test_close_stops_disconnects_and_is_idempotent(acq):
    """Close stops running operations, disconnects both cards and shuts down the processor only once."""
    acq.tx_card.worker = MagicMock()
    acq.close()
    acq.close()
    for card in (acq.tx_card, acq.rx_card):
        card.stop_operation.assert_called_once()
        card.disconnect.assert_called_once()
    acq._processor.shutdown.assert_called_once()


def test_close_partially_constructed():
    """Close must not fail if the constructor failed before the cards were created."""
    acq = AcquisitionControl.__new__(AcquisitionControl)
    acq._run_lock = threading.Lock()
    acq._closed = False
    acq.close()


def test_run_error_stops_cards_and_resets_offsets(acq):
    """An error during the acquisition stops the receive thread, resets the offsets and propagates."""
    acq.tx_card.start_operation.side_effect = RuntimeError("tx failed")
    with pytest.raises(RuntimeError, match="tx failed"):
        acq.run()
    acq.rx_card.stop_operation.assert_called_once()
    assert acq.rx_card.rx_data is None
    assert acq.tx_card.set_gradient_offsets.call_args.kwargs["offsets"] == Dimensions(x=0, y=0, z=0)


def test_run_receive_thread_terminated(acq):
    """A receive thread that terminates before receiving raises instead of waiting forever."""
    acq.rx_card.is_receiving = threading.Event()
    acq.rx_card.worker.is_alive.return_value = False
    with pytest.raises(RuntimeError, match="Receive thread terminated"):
        acq.run()
    acq.rx_card.stop_operation.assert_called_once()
    acq.tx_card.start_operation.assert_not_called()


def test_run_clears_processor_results(acq):
    """Results of a previous, aborted run are discarded at the start of a run."""
    acq.tx_card.start_operation.side_effect = RuntimeError("tx failed")
    with pytest.raises(RuntimeError):
        acq.run()
    acq._processor.clear.assert_called_once()


@pytest.fixture
def acq_without_adc(acq, monkeypatch: pytest.MonkeyPatch) -> AcquisitionControl:
    """Acquisition control with a short sequence without ADC events, which completes without receive data."""
    monkeypatch.setattr(acquisition_control, "AcquisitionData", MagicMock())
    acq.seq_provider = MagicMock()
    acq.config.model_dump = dict
    acq.rx_card.total_gates = 0
    acq._processor.collect.return_value = []
    acq.sequence.adc_count = 0
    acq.sequence.duration = 0.2
    acq.sequence.parameter.averaging_delay = 0
    return acq


def test_run_without_adc_events_waits_for_duration(acq_without_adc):
    """Without ADC events, an average ends with the sequence duration instead of the timeout."""
    start = time.time()
    acq_without_adc.run()

    assert time.time() - start < 2  # timeout would be 2 x 5.2 s
    acq_without_adc.log.warning.assert_called_once_with("No ADC events present")


def test_progress_covers_all_averages(acq_without_adc):
    """Progress increases monotonically over all averages and reaches 100 % when the run is complete."""
    progress: list[int] = []
    acq_without_adc.run(progress_callback=progress.append)

    assert progress == sorted(progress)
    assert progress[-2] < 100  # 100 % is only reported once the run is complete
    assert progress[-1] == acq_without_adc.get_progress() == 100


def test_close_aborts_running_acquisition(acq):
    """Close aborts a running acquisition, which stops the cards and resets the offsets before the disconnect."""
    acq.rx_card.total_gates = 0  # the expected gate never arrives
    acq.sequence.parameter.averaging_delay = 0
    started = threading.Event()
    acq.tx_card.start_operation.side_effect = lambda *_: started.set()
    events: list[object] = []
    acq.rx_card.stop_operation.side_effect = lambda: events.append("stop")
    acq.tx_card.set_gradient_offsets.side_effect = lambda **kwargs: events.append(kwargs["offsets"])
    acq.rx_card.disconnect.side_effect = lambda: events.append("disconnect")
    errors: list[Exception] = []

    def _run() -> None:
        try:
            acq.run()
        except RuntimeError as exc:
            errors.append(exc)

    thread = threading.Thread(target=_run)
    thread.start()
    assert started.wait(timeout=5)
    acq.close()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert "aborted" in str(errors[0])
    disconnect = events.index("disconnect")
    assert events.index("stop") < disconnect
    assert events.index(Dimensions(x=0, y=0, z=0)) < disconnect


def test_run_after_close_is_refused(acq):
    """A closed acquisition control does not operate the cards anymore."""
    acq.close()
    with pytest.raises(RuntimeError, match="aborted"):
        acq.run()
    acq.tx_card.set_gradient_offsets.assert_not_called()


def test_processor_clear_discards_futures():
    """Clear cancels and removes all futures that were not collected."""
    processor = RxProcessor(num_workers=1)
    future = MagicMock()
    processor._futures = {0: future}
    processor.clear()
    future.cancel.assert_called_once()
    assert processor._futures == {}
