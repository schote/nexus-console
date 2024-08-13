"""Interface class for acquisition data."""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import version
from typing import Any

import ismrmrd
import numpy as np

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.utilities.json_encoder import JSONEncoder


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

    session_path: str
    """Directory the acquisition data will be stored in.
    Within the given `storage_path` a new directory with time stamp and sequence name will be created."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Meta data dictionary for additional acquisition info.
    Dictionary is updated (extended) by post-init method with some general information."""

    unprocessed_data: list[np.ndarray] = field(default_factory=list)
    """Unprocessed real-valued MRI frequency (without demodulation, filtering, down-sampling).
    The first entry of the coil dimension also contains the reference signal (16th bit).
    The data array has the following dimensions: [averages, coils, phase encoding, readout]"""

    _additional_data: dict = field(default_factory=dict)
    """Dictionarz containing addition (numpy) data.
    Use the function add_data to update this dictionarz before saving.
    They key of each entry is used as filename."""

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

    def get_data(self, gate_index: int) -> np.ndarray:
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
        return self._raw[gate_index]

    @property
    def raw(self) -> np.ndarray:
        """Get the default raw data array.

        Returns
        -------
            Returns the first entry in raw data list.
        """
        return self.get_data(gate_index=0)

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
        base_path = self.session_path if user_path is None else os.path.join(user_path, "")
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
            json.dump(self.meta, outfile, indent=4, cls=JSONEncoder)

        try:
            # Write sequence .seq file
            self.sequence.write(f"{acq_folder_path}sequence.seq")
        except Exception as exc:
            log.warning("Could not save sequence: %s", exc)

        # Save raw data as numpy array
        if len(self._raw) == 1:
            np.save(f"{acq_folder_path}raw_data.npy", self._raw[0])
        else:
            for k, data in enumerate(self._raw):
                np.save(f"{acq_folder_path}raw_data_{k}.npy", data)

        if len(self._additional_data) > 0:
            for key, value in self._additional_data.items():
                np.save(os.path.join(acq_folder_path, f"{key}.npy"), value)

        if save_unprocessed and self.unprocessed_data:
            # Save raw data as numpy array(s)
            if len(self.unprocessed_data) > 1:
                for k, data in enumerate(self.unprocessed_data):
                    np.save(os.path.join(acq_folder_path, f"unprocessed_data_{k}.npy"), data)
            elif len(self.unprocessed_data) == 1:
                np.save(os.path.join(acq_folder_path, "unprocessed_data.npy"), self.unprocessed_data[0])

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
            json.dumps(info, cls=JSONEncoder)
        except TypeError as exc:
            log.error("Could not append info to meta data.", exc)
        self.meta["info"].update(info)

    def add_data(self, data: dict[str, np.ndarray]) -> None:
        """Add data to additional_data dictionary.

        Parameters
        ----------
        data
            Data which is to be added to acquisition data.
        """
        log = logging.getLogger("AcqData")
        for val in data.values():
            if not hasattr(val, "shape"):
                log.error("Could not add data to acquisition data, pairs of (str, numpy array) required.")
                return
        self._additional_data.update(data)

    def save_ismrmrd(self, header: ismrmrd.xsd.ismrmrdHeader, user_path: str | None = None):
        """Store acquisition data in (ISMR)MRD format."""
        # Get and check sequence labels (required to create acquisition headers)
        if not (labels := self.sequence.evaluate_labels(evolution="adc")):
            raise ValueError("Labels not found. A labeled sequence is required to export ismrmrd.")

        # Get dimensions of raw data
        _, num_coils, num_pe, num_ro = self.raw.shape
        enc_dim = [
            header.encoding[0].encodedSpace.matrixSize.x,
            header.encoding[0].encodedSpace.matrixSize.y,
            header.encoding[0].encodedSpace.matrixSize.z
        ]
        n_dims = sum([int(d > 0) for d in enc_dim])

        # Update larmor frequency with exact frequency
        header.experimentalConditions.H1resonanceFrequency_Hz = int(self.acquisition_parameters.larmor_frequency * 1e6)

        # Set receive channels, required by gadgetron
        system_info = ismrmrd.xsd.acquisitionSystemInformationType()
        system_info.receiverChannels = num_coils
        header.acquisitionSystemInformation = system_info

        # Get folder path and create (ismr)mrd header
        base_path = os.path.join(user_path, "") if user_path else self.session_path
        base_path = os.path.join(base_path, self.meta["folder_name"])
        os.makedirs(base_path, exist_ok=True)
        dataset_path = os.path.join(base_path, "ismrmrd.h5")
        dataset = ismrmrd.Dataset(dataset_path)
        dataset.write_xml_header(header.toXML('utf-8'))

        # Create acquisition
        acq = ismrmrd.Acquisition()
        acq.version = int(version("ismrmrd")[0])
        acq.resize(number_of_samples=num_ro, active_channels=num_coils, trajectory_dimensions=n_dims)
        acq.center_sample = round(num_ro / 2)
        acq.read_dir[0] = 1.0
        acq.phase_dir[1] = 1.0
        acq.slice_dir[2] = 1.0

        for k in range(num_pe):

            acq.scan_counter = k

            # Get k-space encoding from sequence labels and set acquisition indices
            if (key := "LIN") in labels.keys():
                acq.idx.kspace_encode_step_1 = labels[key][k]
            if (key := "PAR") in labels.keys():
                acq.idx.kspace_encode_step_2 = labels[key][k]
            if (key := "SLC") in labels.keys():
                acq.idx.slice = labels[key][k]

            # Set the data and append
            acq.data[:] = self.raw[0, :, k, :]

            dataset.append_acquisition(acq)

        dataset.close()
        log = logging.getLogger("AcqData")
        log.info("ISMRMRD exported: %s", dataset_path)
