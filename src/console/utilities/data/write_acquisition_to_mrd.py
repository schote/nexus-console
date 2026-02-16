"""Write ISMRMRD file for imaging data."""
from importlib.metadata import version
from pathlib import Path

import ismrmrd
import numpy as np
from pypulseq.Sequence.sequence import Sequence

from console.interfaces.rx_data import RxData
from console.utilities.data import get_logger, mrd_helper

log = get_logger()


def write_acquisition_to_mrd(
    data: list[RxData],
    header: ismrmrd.xsd.ismrmrdHeader,
    sequence: Sequence,
    dataset_path: Path,
) -> Path:
    """Write imaging data to ISMRMRD."""
    with ismrmrd.Dataset(dataset_path) as dataset:
        dataset.write_xml_header(header.toXML("utf-8"))

        # Create acquisition
        acq = ismrmrd.Acquisition()
        acq.version = int(version("ismrmrd")[0])
        acq.read_dir[0] = 1.0
        acq.phase_dir[1] = 1.0
        acq.slice_dir[2] = 1.0

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
            
            # Handle ADC presampling if applicable
            if rx_data.labels is not None:
                if not rx_data.labels.get("NOISE"):   # dont remove for noise scans
                    image_samples = header.encoding[0].encodedSpace.matrixSize.x
                    x_ratio = rx_data.num_samples / image_samples
                    if x_ratio > 1.0:
                        log.warning(
                            "Readout oversampling detected (x_ratio=%.2f) for acquisition %i/%i. ",
                            x_ratio, k, len(data)-1,
                        )
                        # Round down to integer oversampling factors and mark exceeding samples to be discarded (adc-presampling)
                        acq.discard_pre = rx_data.num_samples - (image_samples * int(x_ratio))
                else:
                    acq.discard_pre = 0
            else:
                acq.discard_pre = 0
    
            # Assume the center sample is the middle of the data, accounting for pre-discarded samples
            acq.center_sample = (rx_data.num_samples + acq.discard_pre) // 2
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
