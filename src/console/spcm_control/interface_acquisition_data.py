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
    """Demodulated, down-sampled and filtered complex-valued raw MRI data."""

    acquisition_parameters: AcquisitionParameter
    """Acquisition parameters."""

    sequence: SequenceProvider | Sequence
    """Sequence object used for the acquisition acquisition."""

    dwell_time: float
    """Dwell time of down-sampled raw data in seconds."""

    meta: dict = field(default_factory=dict)
    """Meta data dictionary for additional acquisition info.
    Dictionary is updated (extended) by post-init method with some general information."""

    signal: np.ndarray | None = None
    """Unprocessed real-valued signal data without demodulation, sampled at RX card sample-rate."""

    reference: np.ndarray | None = None
    """Reference signal generated during ADC gate window to compensate phase."""

    def __post_init__(self) -> None:
        """Post init method to update meta data object."""
        self.meta.update(
            {
                "date_time": datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
                "raw_data_shape": self.raw.shape,
                "sig_data_shape": self.signal.shape if self.signal is not None else False,
                "ref_data_shape": self.reference.shape if self.reference is not None else False,
                "acquisition_parameter": self.acquisition_parameters.dict(),
                "sequence": {
                    "name": self.sequence.definitions["Name"][0].replace(" ", "_"),
                    "duration": self.sequence.definitions["TotalDuration"],
                },
            }
        )

    def write(self, data_path: str = os.path.expanduser("~") + "/spcm-console") -> None:
        """Save all the acquisition data to a given data path.

        Parameters
        ----------
        data_path
            Directory the acquisition data is written to.
            This path is unique for each acquisition.
        """
        # Add trailing slash and make dir
        base_path = os.path.join(data_path, "")
        os.makedirs(base_path, exist_ok=True)

        acq_folder = datetime.now().strftime("%d%m%Y-%H%M%S-") + self.meta["sequence"]["name"]
        data_path = base_path + acq_folder + "/"
        os.makedirs(data_path, exist_ok=False)

        # params = self.acquisition_parameters.dict()
        # Save acquisition parameters
        # with open(f"{data_path}acquisition_parameter.json", "w", encoding="utf-8") as outfile:
        #     json.dump(params, outfile, indent=4)

        # Save meta data
        with open(f"{data_path}meta.json", "w", encoding="utf-8") as outfile:
            json.dump(self.meta, outfile, indent=4)

        # Write sequence .seq file
        self.sequence.write(f"{data_path}sequence.seq")

        # Save raw data as numpy array
        np.save(f"{data_path}raw_data.npy", self.raw)

        if self.signal is not None:
            # Save raw data as numpy array
            np.save(f"{data_path}signal_data.npy", self.signal)

        if self.reference is not None:
            # Save raw data as numpy array
            np.save(f"{data_path}reference_signal.npy", self.reference)
