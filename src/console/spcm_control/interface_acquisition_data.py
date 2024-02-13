"""Interface class for acquisition data."""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import version
from typing import Any

import numpy as np

from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter


@dataclass(slots=True, frozen=True)
class AcquisitionData:
    """Parameters which define an acquisition."""

    _raw: list[np.ndarray]
    """Demodulated, down-sampled and filtered complex-valued raw MRI data.
    The raw data array has following dimensions:[averages, coils, phase encoding, readout]"""

    acquisition_parameters: AcquisitionParameter
    """Acquisition parameters."""

    sequence: SequenceProvider | Sequence
    """Sequence object used for the acquisition acquisition."""

    dwell_time: float
    """Dwell time of down-sampled raw data in seconds."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Meta data dictionary for additional acquisition info.
    Dictionary is updated (extended) by post-init method with some general information."""

    unprocessed_data: np.ndarray | list | None = None
    """Unprocessed real-valued MRI frequency (without demodulation, filtering, down-sampling).
    The first entry of the coil dimension also contains the reference signal (16th bit).
    The data array has the following dimensions: [averages, coils, phase encoding, readout]"""

    storage_path: str = os.path.expanduser("~") + "/spcm-console"
    """Directory the acquisition data will be stored in.
    Within the given `storage_path` a new directory with time stamp and sequence name will be created."""

    def __post_init__(self) -> None:
        """Post init method to update meta data object."""
        datetime_now = datetime.now()
        seq_name = self.sequence.definitions["Name"].replace(" ", "_")
        self.meta.update(
            {
                "version": version("console"),
                "date_time": datetime_now.strftime("%d/%m/%Y, %H:%M:%S"),
                "folder_name": datetime_now.strftime("%Y-%m-%d-%H%M%S-") + seq_name,
                "dimensions": [r.shape for r in self._raw],
                "dwell_time": self.dwell_time,
                "acquisition_parameter": self.acquisition_parameters.dict(),
                "sequence": {
                    "name": seq_name,
                    "duration": self.sequence.duration()[0],
                },
                "info": {},
            }
        )

    def get_data(self, gate_size_index: int) -> np.ndarray:
        """Get a single raw data array from raw data list.

        During the acquisition, ADC gate events with different durations might occure.
        The data from the different ADC gate sizes is stored in separate arrays which
        are gathered in a list.

        Parameters
        ----------
        gate_size_index, optional
            Index of the raw data array to be returned.
            Raw data from different ADC gate length are stored in separate arrays.

        Returns
        -------
            Raw data array.
        """
        return self._raw[gate_size_index]

    @property
    def raw(self) -> np.ndarray:
        """Get the default raw data array.

        Returns
        -------
            Returns the first entry in raw data list.
        """
        return self.get_data(gate_size_index=0)

    def save(self, user_path: str | None = None, save_unprocessed: bool = False, overwrite: bool = False) -> None:
        """Save all the acquisition data to a given data path.

        Parameters
        ----------
        user_path
            Optional user path, default is None.
            If provided, it is taken to store the acquisition data.
            Other wise a datetime-based folder is created.
        save_unprocessed
            Flag which indicates if unprocessed data is to be written or not, default is False.
        overwrite
            Flag which indicates whether the acquisition data should be overwritten
            in case it already exists from a previous call to this function, default is False.
        """
        log = logging.getLogger("AcqData")
        # Add trailing slash and make dir
        base_path = self.storage_path if user_path is None else os.path.join(user_path, "")
        os.makedirs(base_path, exist_ok=True)

        acq_folder = self.meta["folder_name"]
        acq_folder_path = base_path + acq_folder + "/"

        try:
            os.makedirs(acq_folder_path, exist_ok=overwrite)
        except Exception as exc:
            log.exception(
                msg="This acquisition data object has already been saved. Use the overwrite flag to force overwriting.",
                exc_info=exc
            )
            return

        # Save meta data
        with open(f"{acq_folder_path}meta.json", "w", encoding="utf-8") as outfile:
            json.dump(self.meta, outfile, indent=4)

        try:
            # Write sequence .seq file
            self.sequence.write(f"{acq_folder_path}sequence.seq")
        except Exception as exc:
            log.warning("Could not save sequence: %s", exc)

        # Save raw data as numpy array
        if len(self._raw) == 1:
            np.save(f"{acq_folder_path}raw_data.npy", self.raw[0])
        else:
            for k, data in enumerate(self.raw):
                np.save(f"{acq_folder_path}raw_data_{k}.npy", data)

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
        log = logging.getLogger("AcqData")
        try:
            json.dumps(info)
        except TypeError as exc:
            log.error("Could not append info to meta data.", exc)
        self.meta["info"].update(info)
