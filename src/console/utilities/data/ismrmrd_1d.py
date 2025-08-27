"""Method to write 1D ISMRMRD data."""
from importlib.metadata import version
from pathlib import Path

import ismrmrd

from console.interfaces.rx_data import RxData
from console.utilities.data import construct_acquisition_system, get_logger

log = get_logger()


def write_1d_mrd(
    data: list[RxData],
    header: ismrmrd.xsd.ismrmrdHeader,
    dataset_path: Path,
) -> Path:
    """Write 1D ISMRMRD data."""
    if not len(data) > 0 or data[0].processed_data is None:
        raise AttributeError("No receive data")

    coils_per_rx = [rx_data.processed_data.shape[0] for rx_data in data if rx_data.processed_data is not None]
    # Acquisition system info
    header.acquisitionSystemInformation = construct_acquisition_system.get_nexus_acquisition_system(
        num_coils=max(coils_per_rx),
        larmor_frequency=header.experimentalConditions.H1resonanceFrequency_Hz,
    )

    # Save into dataset
    with ismrmrd.Dataset(dataset_path) as dataset:
        dataset.write_xml_header(header.toXML("utf-8"))

        # Track number of rx_data objects with processed_data = None
        count_unsaved = 0

        # Create and reuse acquisition with version
        acq = ismrmrd.Acquisition()
        acq.version = int(version("ismrmrd")[0])

        # Add data
        for k, rx_data in enumerate(data):
            if rx_data.processed_data is None:
                count_unsaved += 1
                continue

            # Set indices
            acq.idx.scan_counter = k
            acq.idx.average = rx_data.average_index

            # Resize acquisition
            num_coils = rx_data.processed_data.shape[0]
            acq.resize(number_of_samples=rx_data.num_samples, active_channels=num_coils)

            if rx_data.time_stamp is not None:
                acq.acquisition_time_stamp = int(rx_data.time_stamp * 1e6)

            acq.sample_time_us = rx_data.dwell_time * 1e6  # µs

            acq.data[:] = rx_data.processed_data
            dataset.append_acquisition(acq)

    if count_unsaved > 0:
        log.warning(
            "%i/%i acquisitions are unlabeled/none and could not be exported.", count_unsaved, len(data))

    if not dataset_path.is_file():
        raise FileExistsError("Error writing MRD file.")
    log.info("ISMRMRD file written to: %s", dataset_path.resolve())
    return dataset_path
