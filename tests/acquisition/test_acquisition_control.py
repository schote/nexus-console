"""Tests of the shutdown and error handling of the acquisition control, with mocked cards."""
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from console.interfaces.dimensions import Dimensions
from console.spcm_control.acquisition_control import AcquisitionControl
from console.spcm_control.rx_processor import RxProcessor


@pytest.fixture
def acq() -> AcquisitionControl:
    """Acquisition control with mocked cards, processor and sequence, bypassing the constructor."""
    acq = AcquisitionControl.__new__(AcquisitionControl)
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


def test_processor_clear_discards_futures():
    """Clear cancels and removes all futures that were not collected."""
    processor = RxProcessor(num_workers=1)
    future = MagicMock()
    processor._futures = {0: future}
    processor.clear()
    future.cancel.assert_called_once()
    assert processor._futures == {}
