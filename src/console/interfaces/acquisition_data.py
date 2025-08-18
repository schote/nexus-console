"""Interface class for acquisition data."""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import h5py
import ismrmrd
import numpy as np

from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.interfaces.rx_data import RxData
from console.pulseq_interpreter.sequence_provider import Sequence, SequenceProvider
from console.utilities.json_encoder import JSONEncoder

log = logging.getLogger("AcqData")


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

    session_path: str
    """Directory the acquisition data will be stored in.
    Within the given `storage_path` a new directory with time stamp and sequence name will be created."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Meta data dictionary for additional acquisition info.
    Dictionary is updated (extended) by post-init method with some general information."""

    _additional_numpy_data: dict = field(default_factory=dict)
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
                "date": datetime_now.strftime("%Y-%m-%d"),
                "time": datetime_now.strftime("%H:%M:%S"),
                "acquisition_id": acquisition_id,
                "folder_name": acquisition_id,
                "acquisition_parameter": self.acquisition_parameters.dict(),
                "sequence": {
                    "name": seq_name,
                    "duration": self.sequence.duration()[0],
                    "definitions": {
                        # Write all sequence definitions, turn numpy arrays into lists
                        k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in self.sequence.definitions.items()
                    },
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
        overwrite
            Flag which indicates whether the acquisition data should be overwritten
            in case it already exists from a previous call to this function, default is False.
        """
        # Add trailing slash and make dir
        base_path = Path(user_path) if user_path is not None else Path(self.session_path)
        base_path.mkdir(parents=True, exist_ok=True)
        acq_folder_path = base_path / self.meta["folder_name"]
        acq_folder_path.mkdir(parents=True, exist_ok=True)

        try:
            self._save_acquisiton_data(acq_folder_path / "acquisition_data.h5")
        except TypeError as exc:
            log.warning("Type error when saving acquisition data to h5 format.", exc_info=exc)
        except Exception as exc:
            log.warning("Unexpected error when saving acquisition data to h5 format.", exc_info=exc)

        # Save meta data
        if not (meta_file := acq_folder_path / "meta.json").exists() or overwrite:
            with open(meta_file, "w", encoding="utf-8") as outfile:
                json.dump(self.meta, outfile, indent=4, cls=JSONEncoder)

        if not (sequence_file := acq_folder_path / "sequence.seq").exists() or overwrite:
            try:
                # Write sequence .seq file
                self.sequence.write(sequence_file)
            except Exception as exc:
                log.warning("Could not save sequence: %s", exc)

        if len(self._additional_numpy_data) > 0:
            for key, value in self._additional_numpy_data.items():
                np.save(acq_folder_path / f"{key}.npy", value)

        log.info("Saved acquisition data to: %s", acq_folder_path)

    def add_info(self, info: dict[str, Any]) -> None:
        """Add entries to meta data dictionary.

        Parameters
        ----------
        info
            Information as dictionary to be added.
        """
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
        for key, val in data.items():
            if isinstance(key, str) and isinstance(val, np.ndarray) and hasattr(val, "shape"):
                self._additional_numpy_data.update(data)
            else:
                detail = f"Could not add `{key}` to acquisition data...\n\
                    Key-value pairs of str: np.ndarray are required."
                log.error(detail)
                continue

    def save_ismrmrd(self, header: ismrmrd.xsd.ismrmrdHeader | str | Path, user_path: str | None = None):
        """Store acquisition data in (ISMR)MRD format."""
        # Get dimensions of raw data
        if self.receive_data[0].processed_data is None:
            detail = "Processed data not found in receive data. Cannot export ISMRMRD."
            raise AttributeError(detail)

        if not isinstance(header, ismrmrd.xsd.ismrmrdHeader):
            header_path = Path(header) if isinstance(header, str) else header
            # Open the dataset
            dataset = ismrmrd.Dataset(header_path, 'dataset')
            # Read the XML header as a string
            xml_header = dataset.read_xml_header()
            # Parse it into a structured object (optional, see below)
            header = ismrmrd.xsd.CreateFromDocument(xml_header)

        enc_dim = [
            header.encoding[0].encodedSpace.matrixSize.x,
            header.encoding[0].encodedSpace.matrixSize.y,
            header.encoding[0].encodedSpace.matrixSize.z,
        ]
        n_dims = sum([int(d > 0) for d in enc_dim])

        sequence_trajectory = self.sequence.calculate_kspace()[0]

        # Retrieve channel order from sequence definition, if available
        channel_mapping = None
        if (key := "channel_order") in self.sequence.definitions:
            # Get definition if key 'channel_order' exists
            channel_order = self.sequence.get_definition(key)
            channels = ("x", "y", "z")
            # Ensure that channel order is list/tuple, has length 3 and contains only valid channels
            check = (
                isinstance(channel_order, (list, tuple)) and
                len(channel_order) == len(channels) and
                all(ch in channels for ch in channel_order)
            )
            if check:
                # Assign mapping if check passed
                channel_mapping = [channel_order.index(ch) for ch in channels]
        else:
            log.warning("Could not find `channel_order` in sequence definitions, assigning sequence trajectory as is.")

        # Update larmor frequency with exact frequency
        header.experimentalConditions.H1resonanceFrequency_Hz = int(self.acquisition_parameters.larmor_frequency * 1e6)

        # Set measurement information
        measurement_info = ismrmrd.xsd.measurementInformationType()
        measurement_info.measurementID = self.meta["acquisition_id"]
        measurement_info.seriesDate = self.meta["date"]
        measurement_info.seriesTime = self.meta["time"]
        header.measurementInformation = measurement_info

        # Set receive channels, required by gadgetron
        system_info = ismrmrd.xsd.acquisitionSystemInformationType()
        num_coils = self.receive_data[0].processed_data.shape[0]
        system_info.receiverChannels = num_coils
        system_info.systemVendor = "osi2"
        system_info.systemModel = "Nexus"
        system_info.systemFieldStrength_T = round(self.acquisition_parameters.larmor_frequency / 42.58, 4)
        header.acquisitionSystemInformation = system_info

        # Get folder path and create (ismr)mrd header
        base_path = Path(user_path) if user_path else Path(self.session_path)
        base_path = base_path / self.meta["folder_name"]
        base_path.mkdir(parents=True, exist_ok=True)
        dataset_path = base_path / "data.mrd"
        dataset = ismrmrd.Dataset(dataset_path)
        dataset.write_xml_header(header.toXML('utf-8'))

        # Create acquisition
        acq = ismrmrd.Acquisition()
        acq.version = int(version("ismrmrd")[0])
        acq.read_dir[0] = 1.0
        acq.phase_dir[1] = 1.0
        acq.slice_dir[2] = 1.0

        trajectory_position = 0
        count_unsaved = 0

        for k, data in enumerate(self.receive_data):

            if data.labels is None or data.processed_data is None:
                count_unsaved += 1
                continue

            acq.clear_all_flags()
            acq.scan_counter = k
            # Resize each acquisition to the individual number of sample points and active channels
            num_coils = data.processed_data.shape[0]
            acq.resize(number_of_samples=data.num_samples, active_channels=num_coils, trajectory_dimensions=n_dims)
            # Assume the center sample is the middle of the data
            acq.center_sample = round(data.num_samples / 2)
            # Readout bandwidth, as time between samples in microseconds
            acq.sample_time_us = data.dwell_time * 1e6
            # Timestamp of readout
            if data.time_stamp is not None:
                acq.acquisition_time_stamp = int(data.time_stamp * 1e6)  # timestamp in us

            # Set counter
            acq.idx.average = data.average_index
            # Set encoding step 1 counters and flags
            if (key := "LIN") in data.labels:
                acq.idx.kspace_encode_step_1 = data.labels[key]
            # Set encoding step 2 counters and flags
            if (key := "PAR") in data.labels:
                acq.idx.kspace_encode_step_2 = data.labels[key]
            # Set slice encoding counters and flags
            if (key := "SLC") in data.labels:
                acq.idx.slice = data.labels[key]
            # Set echo position/contrast counters and flags
            if (key := "ECO") in data.labels:
                acq.idx.contrast = data.labels[key]
            # Set repetition counters and flags
            if (key := "REP") in data.labels:
                acq.idx.repetition = data.labels[key]

            traj = sequence_trajectory[:, trajectory_position:trajectory_position + data.num_samples].T
            # Rearrange trajectory according to sequence definition, if available
            if channel_mapping is not None:
                traj = traj[:, channel_mapping]

            # Set the data and append
            acq.data[:] = data.processed_data
            acq.traj[:] = traj
            trajectory_position += data.num_samples

            dataset.append_acquisition(acq)

        # Log warning if unlabeled acquisitions were found
        if count_unsaved > 0:
            log.warning(
                "%i/%i acquisitions are unlabeled/none and could not be exported.",
                count_unsaved,
                len(self.receive_data),
            )

        dataset.close()
        log.info("ISMRMRD exported: %s", dataset_path)

    def _save_acquisiton_data(self, file_path: str) -> None:
        """Save AcquisitionData and all RxData entries to an HDF5 file."""

        def _write_dict(group: h5py.Group, _dict: dict) -> None:
            """Write dictionary to h5py group."""
            for key, value in _dict.items():
                if isinstance(value, dict):
                    _write_dict(group.create_group(key), value)
                elif isinstance(value, np.generic):
                    group.attrs[key] = value.item()
                elif isinstance(value, (int, float, bool)):
                    group.attrs[key] = value
                elif value is None:
                    group.attrs[key] = "None"
                else:
                    group.attrs[key] = str(value)

        with h5py.File(file_path, "w") as fh:
            # --- Metadata
            meta_group = fh.create_group("meta")
            _write_dict(meta_group, self.meta)

            # --- RxData per average
            receive_data_group = fh.create_group("receive_data")
            receive_data_group.attrs["length"] = len(self.receive_data)
            for idx, rx_data in enumerate(self.receive_data):
                rx_group = receive_data_group.create_group(str(idx))
                _write_dict(rx_group, rx_data.dict())
                if rx_data.processed_data is not None:
                    rx_group.create_dataset("processed_data", data=rx_data.processed_data)
                if rx_data.raw_data is not None:
                    rx_group.create_dataset("raw_data", data=rx_data.raw_data)
