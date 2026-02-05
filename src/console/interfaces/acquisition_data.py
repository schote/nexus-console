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
from console.utilities.data import get_nexus_acquisition_system, write_acquisition_to_mrd
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
    """Dictionary containing addition (numpy) data.
    Use the function add_data to update this dictionary before saving.
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
                "acquisition_parameter": self.acquisition_parameters.to_dict(),
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
            self._write_acquisition_data(acq_folder_path / "rx_data.h5")
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

    def save_ismrmrd(
        self,
        header: ismrmrd.xsd.ismrmrdHeader | str | Path | None = None,
        user_path: str | None = None,
    ) -> Path | None:
        """Store acquisition data in ISMRMRD format."""
        # Ensure that receive data is available
        if not self.receive_data or self.receive_data[0].processed_data is None:
            detail = "Processed data not found in receive data. Cannot export ISMRMRD."
            raise AttributeError(detail)

        # Get MRD data path
        base_path = Path(user_path) if user_path else Path(self.session_path)
        base_path = base_path / self.meta["folder_name"]
        base_path.mkdir(parents=True, exist_ok=True)
        dataset_path = base_path / "data.mrd"

        # Create measurement info from meta
        info = ismrmrd.xsd.measurementInformationType(
            measurementID=self.meta["acquisition_id"],
            seriesDate=self.meta["date"],
            seriesTime=self.meta["time"],
        )
        # Get number of coils per receive event and create acquisition system info
        coils_per_rx = [
            rx_data.processed_data.shape[0] for rx_data in self.receive_data if rx_data.processed_data is not None
        ]
        system_info = get_nexus_acquisition_system(
            num_coils=max(coils_per_rx),
            larmor_frequency=int(self.acquisition_parameters.larmor_frequency),
        )
        # Define experimental conditions with true larmor frequency
        conditions = ismrmrd.xsd.experimentalConditionsType(
            H1resonanceFrequency_Hz=int(self.acquisition_parameters.larmor_frequency),
        )

        # Create header if not given
        if header is None:
            log.info("ISMRMRD header not given, creating header without encoding/reconstruction info.")
            header = ismrmrd.xsd.ismrmrdHeader()

        # Load header from xml file
        if isinstance(header, (str, Path)):
            header_path = Path(header)
            log.info("Loading ISMRMRD header from file: %s", header_path.name)
            # Open the dataset
            dataset = ismrmrd.Dataset(header_path)
            # Read the XML file and create header
            xml_header = dataset.read_xml_header()
            header = ismrmrd.xsd.CreateFromDocument(xml_header)

        # Extend header if given
        if isinstance(header, ismrmrd.xsd.ismrmrdHeader):
            # Update existing ismrmrd header with measurement info, conditions and system info
            header.measurementInformation = info
            header.experimentalConditions = conditions
            header.acquisitionSystemInformation = system_info

            return write_acquisition_to_mrd(
                data=self.receive_data,
                header=header,
                sequence=self.sequence,
                dataset_path=dataset_path,
                channel_assignment=self.acquisition_parameters.channel_assignment,
            )

        log.warning("Invalid MRD header, could not write MRD file.")
        return None

    def _write_acquisition_data(self, file_path: str) -> None:
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
