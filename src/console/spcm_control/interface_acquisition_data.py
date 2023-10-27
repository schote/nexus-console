"""Interface class for acquisition parameters."""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter


@dataclass(slots=True, frozen=True)
class AcquisitionData:
    """Parameters which define an acquisition."""

    raw: np.ndarray
    """Demodulated, down-sampled and filtered complex-valued raw MRI data.
    The raw data array has following dimensions:[averages, coils, phase encoding, readout]"""

    acquisition_parameters: AcquisitionParameter
    """Acquisition parameters."""

    sequence: SequenceProvider | Sequence
    """Sequence object used for the acquisition acquisition."""

    dwell_time: float
    """Dwell time of down-sampled raw data in seconds."""

    meta: dict = field(default_factory=dict)
    """Meta data dictionary for additional acquisition info.
    Dictionary is updated (extended) by post-init method with some general information."""

    storage_path: str = os.path.expanduser("~") + "/spcm-console"
    """Directory the acquisition data will be stored in.
    Within the given `storage_path` a new directory with time stamp and sequence name will be created."""

    # unprocessed_data: np.ndarray | None = None
    unprocessed_data: list | None = None
    """Unprocessed real-valued MRI frequency (without demodulation, filtering, down-sampling).
    The first entry of the coil dimension also contains the reference signal (16th bit).
    The data array has the following dimensions: [averages, coils, phase encoding, readout]"""

    is_stored: bool = False
    """Status flag which indicates if data has already been stored or not. 
    Must not be initialized, flag is cleared again in ``__post_init__`` method.
    """

    def __post_init__(self) -> None:
        """Post init method to update meta data object."""
        datetime_now = datetime.now()
        seq_name = self.sequence.definitions["Name"].replace(" ", "_")
        self.meta.update(
            {
                "date_time": datetime_now.strftime("%d/%m/%Y, %H:%M:%S"),
                "folder_name": datetime_now.strftime("%Y-%m-%d-%H%M%S-") + seq_name,
                "raw_dimensions": self.raw.shape,
                # "unprocessed_dimensions": self.unprocessed_data.shape if self.unprocessed_data is not None else None,
                "acquisition_parameter": self.acquisition_parameters.dict(),
                "sequence": {
                    "name": seq_name,
                    "duration": self.sequence.definitions["TotalDuration"],
                },
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

        # Write sequence .seq file
        self.sequence.write(f"{acq_folder_path}sequence.seq")

        # Save raw data as numpy array
        np.save(f"{acq_folder_path}raw_data.npy", self.raw)

        if save_unprocessed and self.unprocessed_data is not None:
            # Save raw data as numpy array
            # np.save(f"{acq_folder_path}unprocessed_data.npy", self.unprocessed_data)
            _tmp = np.asanyarray(self.unprocessed_data, dtype=object)
            np.save(f"{acq_folder_path}unprocessed_data.npy", _tmp, allow_pickle=True)

    def add_info(self, info: dict) -> None:
        """Add entries to meta data dictionary.

        Parameters
        ----------
        info
            Information as dictionary to be added.
        """
        self.meta["info"].update(info)
