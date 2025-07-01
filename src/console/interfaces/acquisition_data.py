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
from console.interfaces.rx_data import RxData
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.utilities.json_encoder import JSONEncoder


@dataclass(slots=True, frozen=True)
class AcquisitionData:
    """Parameters which define an acquisition."""

    receive_data: list[list[RxData]]
    """ A list containing a list of RxData objects which contain all of the receive data for the acquisition. The outer
    list contains the list of RxData for each average."""

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
                "version": version("nexus-console"),
                "date_time": datetime_now.strftime("%d/%m/%Y, %H:%M:%S"),
                "folder_name": datetime_now.strftime("%Y-%m-%d-%H%M%S-") + seq_name,
                "dwell_time": self.dwell_time,
                "acquisition_parameter": self.acquisition_parameters.dict(),
                "sequence": {
                    "name": seq_name,
                    "duration": self.sequence.duration()[0],
                },
                "info": {},
            }
        )

    def save(self, user_path: str | None = None, overwrite: bool = False) -> None:
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

        if len(self._additional_data) > 0:
            for key, value in self._additional_data.items():
                np.save(os.path.join(acq_folder_path, f"{key}.npy"), value)

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
        if self.receive_data[0][0].processed_data is None:
            raise RuntimeError("No processed data found")
        num_coils, num_ro = self.receive_data[0][0].processed_data.shape
        num_pe = len(self.receive_data[0])
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
        dataset.write_xml_header(header.toXML("utf-8"))

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
            if (key := "LIN") in labels:
                acq.idx.kspace_encode_step_1 = labels[key][k]
            if (key := "PAR") in labels:
                acq.idx.kspace_encode_step_2 = labels[key][k]
            if (key := "SLC") in labels:
                acq.idx.slice = labels[key][k]

            # Set the data and append
            acq.data[:] = self.receive_data[0][0].processed_data

            dataset.append_acquisition(acq)

        dataset.close()
        log = logging.getLogger("AcqData")
        log.info("ISMRMRD exported: %s", dataset_path)
