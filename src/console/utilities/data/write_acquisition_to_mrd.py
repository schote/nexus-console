"""Write ISMRMRD file for imaging data."""
from importlib.metadata import version
from pathlib import Path

import ismrmrd
import numpy as np
from pypulseq.Sequence.sequence import Sequence

from console.interfaces.dimensions import Dimensions
from console.interfaces.rx_data import RxData
from console.utilities.data import get_logger, mrd_helper

log = get_logger()


def write_acquisition_to_mrd(
    data: list[RxData],
    header: ismrmrd.xsd.ismrmrdHeader,
    sequence: Sequence,
    dataset_path: Path,
    channel_assignment: Dimensions,
) -> Path:
    """Write imaging data to ISMRMRD."""
    with ismrmrd.Dataset(dataset_path) as dataset:
        dataset.write_xml_header(header.toXML("utf-8"))

        # Create acquisition
        acq = ismrmrd.Acquisition()
        acq.version = int(version("ismrmrd")[0])

        # Set raw data orientation directions in LPS coordinates, assuming patient is lying supine, head first.
        # This information is shared for all acquisitions
        # The assumption is that the console output channels to physical gradient orientations are as follows
        # ch output1 -> gradient from front to back (Patient: I to S)
        # ch output2 -> gradient from top to bottom (Patient: P to A)
        # ch output3 -> gradient from left to right (Patient: R to L)
        # For LPS coordinates the direction P to A needs to be inverted, i.e., read_dir = [0,-1,0]

        # Map logical gradient axes to physical directions in LPS coordinates
        direction_map = {
            1: (2, 1.0),   # I to S -> [0, 0, 1]
            2: (1, -1.0),  # P to A -> [0, -1, 0] (inverted for LPS)
            3: (0, 1.0),   # R to L -> [1, 0, 0]
        }

        # Set readout direction
        idx, val = direction_map[int(channel_assignment.x)]
        acq.read_dir[idx] = val

        # Set phase encoding direction
        idx, val = direction_map[int(channel_assignment.y)]
        acq.phase_dir[idx] = val

        # Set slice direction
        idx, val = direction_map[int(channel_assignment.z)]
        acq.slice_dir[idx] = val

        trajectory_position = 0
        none_counter = 0

        # Calculate k-space trajectory from sequence
        trajectory = sequence.calculate_kspace()[0]
        # Trajectory always has shape (3, num_ro), the following line gets all axes which contain values unequal 0
        # The sum of traj_dims, yields the trajectory dimension, while traj_dims is used to mask the trajectory.
        traj_dims = np.all(trajectory != 0, axis=1)

        for k, rx_data in enumerate(data):
            if rx_data.processed_data is None:
                none_counter += 1
                continue

            acq.clear_all_flags()
            acq.scan_counter = k
            # Resize each acquisition to the individual number of sample points and active channels
            num_coils = rx_data.processed_data.shape[0]
            acq.resize(
                number_of_samples=rx_data.num_samples,
                active_channels=num_coils,
                trajectory_dimensions=traj_dims.sum()
            )
            # Assume the center sample is the middle of the data
            acq.center_sample = rx_data.num_samples // 2
            # Readout bandwidth, as time between samples in microseconds
            acq.sample_time_us = rx_data.dwell_time * 1e6
            # Number of samples to be discarded, defined by adc_dead_time
            # Since adc_dead_time is arrange symmetrically around ADC, the
            # number of discarded pre and post sample is identical
            acq.discard_pre = rx_data.num_samples_discard
            acq.discard_post = rx_data.num_samples_discard
            # Timestamp of readout
            if rx_data.time_stamp is not None:
                acq.acquisition_time_stamp = int(rx_data.time_stamp * 1e6)  # timestamp in us
            else:
                log.warning("Missing time stamp for acquisition %i/%i", k, len(data))

            # Set counters and flags
            mrd_helper.set_mrd_counters(acq, rx_data)
            mrd_helper.set_mrd_flags(acq, rx_data)

            # If trajectory is available
            if traj_dims.sum() > 0:
                traj = trajectory[traj_dims, trajectory_position:trajectory_position + rx_data.num_samples].T
                acq.traj[:] = traj
                trajectory_position += rx_data.num_samples

            # Set the data and append
            acq.data[:] = rx_data.processed_data
            dataset.append_acquisition(acq)

    # Log warning if unlabeled acquisitions were found
    if none_counter > 0:
        log.warning(
            "%i/%i acquisitions are unlabeled/none and could not be exported.", none_counter, len(data),
        )

    if not dataset_path.is_file():
        log.error("File write failed. The file does not exist after the write attempt.")
    log.info("ISMRMRD file written to: %s", dataset_path.resolve())
    return dataset_path
