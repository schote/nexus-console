"""Write ISMRMRD file for imaging data."""
from importlib.metadata import version
from pathlib import Path

import ismrmrd
from pypulseq.Sequence.sequence import Sequence

from console.interfaces.rx_data import RxData
from console.utilities.data import construct_acquisition_system, get_logger

log = get_logger()


def write_imaging_mrd(
    data: list[RxData],
    header: ismrmrd.xsd.ismrmrdHeader,
    sequence: Sequence,
    dataset_path: Path,
) -> Path:
    """Write imaging data to ISMRMRD."""
    if not len(data) > 0 or data[0].processed_data is None:
        raise AttributeError("No receive data")

    enc_dim = [
        header.encoding[0].encodedSpace.matrixSize.x,
        header.encoding[0].encodedSpace.matrixSize.y,
        header.encoding[0].encodedSpace.matrixSize.z,
    ]
    n_dims = sum([int(d > 0) for d in enc_dim])

    # Retrieve channel order from sequence definition, if available
    channel_mapping = None
    if (key := "channel_order") in sequence.definitions:
        # Get definition if key 'channel_order' exists
        channel_order = sequence.get_definition(key)
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

    coils_per_rx = [rx_data.processed_data.shape[0] for rx_data in data if rx_data.processed_data is not None]
    # Update larmor frequency and set acquisition system information
    header.acquisitionSystemInformation = construct_acquisition_system.get_nexus_acquisition_system(
        num_coils=max(coils_per_rx),
        larmor_frequency=header.experimentalConditions.H1resonanceFrequency_Hz,
    )

    with ismrmrd.Dataset(dataset_path) as dataset:
        dataset.write_xml_header(header.toXML("utf-8"))

        # Create acquisition
        acq = ismrmrd.Acquisition()
        acq.version = int(version("ismrmrd")[0])
        acq.read_dir[0] = 1.0
        acq.phase_dir[1] = 1.0
        acq.slice_dir[2] = 1.0

        trajectory_position = 0
        count_unsaved = 0

        # Calculate k-space trajectory from sequence
        trajectory = sequence.calculate_kspace()[0]

        for k, rx_data in enumerate(data):
            if rx_data.labels is None or rx_data.processed_data is None:
                count_unsaved += 1
                continue

            acq.clear_all_flags()
            acq.scan_counter = k
            # Resize each acquisition to the individual number of sample points and active channels
            num_coils = rx_data.processed_data.shape[0]
            acq.resize(number_of_samples=rx_data.num_samples, active_channels=num_coils, trajectory_dimensions=n_dims)
            # Assume the center sample is the middle of the data
            acq.center_sample = round(rx_data.num_samples / 2)
            # Readout bandwidth, as time between samples in microseconds
            acq.sample_time_us = rx_data.dwell_time * 1e6
            # Timestamp of readout
            if rx_data.time_stamp is not None:
                acq.acquisition_time_stamp = int(rx_data.time_stamp * 1e6)  # timestamp in us

            # Set counter
            acq.idx.average = rx_data.average_index
            # Set encoding step 1 counters and flags
            if (key := "LIN") in rx_data.labels:
                acq.idx.kspace_encode_step_1 = rx_data.labels[key]
            # Set encoding step 2 counters and flags
            if (key := "PAR") in rx_data.labels:
                acq.idx.kspace_encode_step_2 = rx_data.labels[key]
            # Set slice encoding counters and flags
            if (key := "SLC") in rx_data.labels:
                acq.idx.slice = rx_data.labels[key]
            # Set echo position/contrast counters and flags
            if (key := "ECO") in rx_data.labels:
                acq.idx.contrast = rx_data.labels[key]
            # Set repetition counters and flags
            if (key := "REP") in rx_data.labels:
                acq.idx.repetition = rx_data.labels[key]

            traj = trajectory[:, trajectory_position:trajectory_position + rx_data.num_samples].T
            # Rearrange trajectory according to sequence definition, if available
            if channel_mapping is not None:
                traj = traj[:, channel_mapping]

            # Set the data and append
            acq.data[:] = rx_data.processed_data
            acq.traj[:] = traj
            trajectory_position += rx_data.num_samples

            dataset.append_acquisition(acq)

    # Log warning if unlabeled acquisitions were found
    if count_unsaved > 0:
        log.warning(
            "%i/%i acquisitions are unlabeled/none and could not be exported.", count_unsaved, len(data),
        )

    if not dataset_path.is_file():
        raise FileExistsError("Error writing MRD file.")
    log.info("ISMRMRD file written to: %s", dataset_path.resolve())
    return dataset_path
