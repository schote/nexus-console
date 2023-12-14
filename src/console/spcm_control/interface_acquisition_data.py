"""Interface class for acquisition data."""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter

log = logging.getLogger("AcqData")


@dataclass(slots=True, frozen=True)
class AcquisitionData:
    """Parameters which define an acquisition."""

    raw: np.ndarray | list
    """Demodulated, down-sampled and filtered complex-valued raw MRI data.
    The raw data array has following dimensions:[averages, coils, phase encoding, readout]"""

    acquisition_parameters: AcquisitionParameter
    """Acquisition parameters."""

    sequence: SequenceProvider | Sequence
    """Sequence object used for the acquisition acquisition."""

    device_config: dict
    """Device configurations (transmit card, receive card and sequence provide) of the experiment."""

    dwell_time: float
    """Dwell time of down-sampled raw data in seconds."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Meta data dictionary for additional acquisition info.
    Dictionary is updated (extended) by post-init method with some general information."""

    storage_path: str = os.path.expanduser("~") + "/spcm-console"
    """Directory the acquisition data will be stored in.
    Within the given `storage_path` a new directory with time stamp and sequence name will be created."""

    unprocessed_data: np.ndarray | list | None = None
    """Unprocessed real-valued MRI frequency (without demodulation, filtering, down-sampling).
    The first entry of the coil dimension also contains the reference signal (16th bit).
    The data array has the following dimensions: [averages, coils, phase encoding, readout]"""

    def __post_init__(self) -> None:
        """Post init method to update meta data object."""
        datetime_now = datetime.now()
        if not all([key in list(self.device_config.keys()) for key in ["TxCard", "RxCard", "SequenceProvider"]]):
            raise log.warning("Device configuration contains unknown keys")
        seq_name = self.sequence.definitions["Name"].replace(" ", "_")
        self.meta.update(
            {
                "date_time": datetime_now.strftime("%d/%m/%Y, %H:%M:%S"),
                "folder_name": datetime_now.strftime("%Y-%m-%d-%H%M%S-") + seq_name,
                "raw_dimensions": [_raw.shape for _raw in self.raw] if isinstance(self.raw, list) else self.raw.shape,
                # "unprocessed_dimensions": self.unprocessed_data.shape if self.unprocessed_data is not None else None,
                "acquisition_parameter": self.acquisition_parameters.dict(),
                "sequence": {
                    "name": seq_name,
                    "duration": self.sequence.duration()[0],
                    "configuration": self.device_config["SequenceProvider"],
                },
                "rx_device_configuration": self.device_config["RxCard"],
                "tx_device_configuration": self.device_config["TxCard"],
                "info": {},
            }
        )

    def write(self, save_unprocessed: bool = False) -> None:
        """Save all the acquisition data to a given data path.

        Parameters
        ----------
        save_unprocessed
            Flag which indicates if unprocessed data is to be written or not.
        """
        # Add trailing slash and make dir
        base_path = os.path.join(self.storage_path, "")
        os.makedirs(base_path, exist_ok=True)

        acq_folder = self.meta["folder_name"]
        acq_folder_path = base_path + acq_folder + "/"
        os.makedirs(acq_folder_path, exist_ok=False)

        # Save meta data
        with open(f"{acq_folder_path}meta.json", "w", encoding="utf-8") as outfile:
            json.dump(self.meta, outfile, indent=4)

        try:
            # Write sequence .seq file
            self.sequence.write(f"{acq_folder_path}sequence.seq")
        except Exception as exc:
            log.warning("Could not save sequence: %s", exc)

        # Save raw data as numpy array
        if isinstance(self.raw, list):
            for k, data in enumerate(self.raw):
                np.save(f"{acq_folder_path}raw_data_{k}.npy", data)
        else:
            np.save(f"{acq_folder_path}raw_data.npy", self.raw)

        if save_unprocessed and self.unprocessed_data is not None:
            # Save raw data as numpy array(s)
            if isinstance(self.unprocessed_data, list):
                for k, data in enumerate(self.unprocessed_data):
                    np.save(f"{acq_folder_path}unprocessed_data_{k}.npy", data)
            else:
                np.save(f"{acq_folder_path}unprocessed_data.npy", self.unprocessed_data)

        log.info("Saved acquisition data to: %s", acq_folder_path)

    def add_info(self, info: dict[str, Any]) -> None:
        """Add entries to meta data dictionary.

        Parameters
        ----------
        info
            Information as dictionary to be added.
        """
        self.meta["info"].update(info)
