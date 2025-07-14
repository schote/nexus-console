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

    receive_data: list[RxData]
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
        acquisition_id = datetime_now.strftime("%Y-%m-%d-%H%M%S-") + seq_name
        self.meta.update(
            {
                "version": version("nexus-console"),
                "date": datetime_now.strftime("%d/%m/%Y"),
                "time": datetime_now.strftime("%H:%M:%S"),
                "acquisition_id": acquisition_id,
                "folder_name": acquisition_id,
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
        # if not (labels := self.sequence.evaluate_labels(evolution="adc")):
        #     detail = "Sequence labels not found. A labeled sequence is required to export ismrmrd."
        #     raise AttributeError(detail)

        # Get dimensions of raw data
        if self.receive_data[0].processed_data is None:
            detail = "Processed data not found in receive data. Cannot export ISMRMRD."
            raise AttributeError(detail)

        enc_dim = [
            header.encoding[0].encodedSpace.matrixSize.x,
            header.encoding[0].encodedSpace.matrixSize.y,
            header.encoding[0].encodedSpace.matrixSize.z,
        ]
        n_dims = sum([int(d > 0) for d in enc_dim])

        # Update larmor frequency with exact frequency
        header.experimentalConditions.H1resonanceFrequency_Hz = int(self.acquisition_parameters.larmor_frequency * 1e6)

        # Set measurement information
        measurement_info = ismrmrd.xsd.measurementInformationType()
        measurement_info.measurementID = self.meta["acquisition_id"]
        measurement_info.seriesDate = self.meta["date"]
        measurement_info.seriesDate = self.meta["time"]
        header.measurementInformation = measurement_info

        # Set receive channels, required by gadgetron
        system_info = ismrmrd.xsd.acquisitionSystemInformationType()
        # Todo: Get the number of system channels from RX device
        num_coils = self.receive_data[0].processed_data.shape[0]
        system_info.receiverChannels = num_coils
        system_info.systemVendor = "OSII"
        system_info.systemModel = "Nexus"
        system_info.systemFieldStrength_T = round(self.acquisition_parameters.larmor_frequency / 42.58, 4)
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
        acq.read_dir[0] = 1.0
        acq.phase_dir[1] = 1.0
        acq.slice_dir[2] = 1.0

        count_unlabeled = 0

        # Parse label limits:
        labels_max = {}
        for data in self.receive_data:
            for label, count in data.labels.items():
                if label not in labels_max:
                    labels_max[label] = count
                    continue
                labels_max[label] = max(labels_max[label], count)

        for k, data in enumerate(self.receive_data):

            if data.labels is None:
                count_unlabeled += 1
                continue
            acq.clear_all_flags()
            acq.scan_counter = k
            # Resize each acquisition to the individual number of sample points and active channels
            num_coils = data.processed_data.shape[0]
            acq.resize(number_of_samples=data.num_pnts, active_channels=num_coils, trajectory_dimensions=n_dims)
            # Assume the center sample is the middle of the data
            acq.center_sample = round(data.num_pnts / 2)
            # Readout bandwidth, as time between samples in microseconds
            acq.sample_time_us = data.dwell_time * 1e6
            # Timestamp of readout
            acq.acquisition_time_stamp = int(data.time_stamp * 1e6)  # timestamp in us

            # Set averaging counters and flags
            acq.idx.average = data.scan_number
            if data.scan_number == 0:
                acq.setFlag(ismrmrd.ACQ_FIRST_IN_AVERAGE)
            if data.scan_number == data.total_scans - 1:
                acq.setFlag(ismrmrd.ACQ_LAST_IN_AVERAGE)

            # Set encoding step 1 counters and flags
            if (key := "LIN") in data.labels:
                acq.idx.kspace_encode_step_1 = data.labels[key]
                if acq.idx.kspace_encode_step_1 == 0:
                    acq.setFlag(ismrmrd.ACQ_FIRST_IN_ENCODE_STEP1)
                if acq.idx.kspace_encode_step_1 == labels_max[key]:
                    acq.setFlag(ismrmrd.ACQ_LAST_IN_ENCODE_STEP1)

            # Set encoding step 2 counters and flags
            if (key := "PAR") in data.labels:
                acq.idx.kspace_encode_step_2 = data.labels[key]
                if acq.idx.kspace_encode_step_2 == 0:
                    acq.setFlag(ismrmrd.ACQ_FIRST_IN_ENCODE_STEP2)
                if acq.idx.kspace_encode_step_2 == labels_max[key]:
                    acq.setFlag(ismrmrd.ACQ_LAST_IN_ENCODE_STEP2)

            # Set slice encoding counters and flags
            if (key := "SLC") in data.labels:
                acq.idx.slice = data.labels[key]
                if acq.idx.slice == 0:
                    acq.setFlag(ismrmrd.ACQ_FIRST_IN_SLICE)
                if acq.idx.slice == labels_max[key]:
                    acq.setFlag(ismrmrd.ACQ_LAST_IN_SLICE)

            # Set echo position/contrast counters and flags
            if (key := "ECO") in data.labels:
                acq.idx.contrast = data.labels[key]
                if acq.idx.contrast == 0:
                    acq.setFlag(ismrmrd.ACQ_FIRST_IN_CONTRAST)
                if acq.idx.contrast == labels_max[key]:
                    acq.setFlag(ismrmrd.ACQ_LAST_IN_CONTRAST)

            # Set echo position/contrast counters and flags
            if (key := "REP") in data.labels:
                acq.idx.repetition = data.labels[key]
                if acq.idx.repetition == 0:
                    acq.setFlag(ismrmrd.ACQ_FIRST_IN_REPETITION)
                if acq.idx.repetition == labels_max[key]:
                    acq.setFlag(ismrmrd.ACQ_LAST_IN_REPETITION)

            # Set the data and append
            acq.data[:] = data.processed_data
            # TODO: Set trajectory calculated from pypulseq sequence

            dataset.append_acquisition(acq)

        # Log warning if unlabeled acquisitions were found
        if count_unlabeled > 0:
            self.log.warning(
                "%i/%i acquisitions were not labeled and thus not exported.",
                count_unlabeled,
                len(self.receive_data),
            )

        dataset.close()
        log = logging.getLogger("AcqData")
        log.info("ISMRMRD exported: %s", dataset_path)
