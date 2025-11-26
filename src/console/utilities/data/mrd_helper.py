"""Methods helping to construct or complete ISMRMRD header."""
from importlib.metadata import version

import ismrmrd

from console.interfaces.rx_data import RxData


def get_nexus_acquisition_system(
    num_coils: int,
    larmor_frequency: float | None,
) -> ismrmrd.xsd.acquisitionSystemInformationType:
    """Define the nexus console specific acquisition system information for ISMRMRD header."""
    system_version = version("nexus-console")
    system_info = ismrmrd.xsd.acquisitionSystemInformationType()
    system_info.receiverChannels = num_coils
    system_info.systemVendor = "osi2"
    system_info.systemModel = f"Nexus_{system_version}"
    if larmor_frequency is not None:
        system_info.systemFieldStrength_T = round(larmor_frequency / 42.58e6, 4)
    return system_info


def set_mrd_counters(mrd_acquisition: ismrmrd.Acquisition, rx_data: RxData) -> None:
    """Extract labels from RxData and set them in MRD acquisition object."""
    # Averaging counter
    mrd_acquisition.idx.average = rx_data.average_index
    if rx_data.labels is not None:
        # Encoding step 1 counter
        if (key := "LIN") in rx_data.labels:
            mrd_acquisition.idx.kspace_encode_step_1 = rx_data.labels[key]
        # Encoding step 2 counter
        if (key := "PAR") in rx_data.labels:
            mrd_acquisition.idx.kspace_encode_step_2 = rx_data.labels[key]
        # Slice encoding counter
        if (key := "SLC") in rx_data.labels:
            mrd_acquisition.idx.slice = rx_data.labels[key]
        # Echo position/contrast counter
        if (key := "ECO") in rx_data.labels:
            mrd_acquisition.idx.contrast = rx_data.labels[key]
        # Cardiac phase counter
        if (key := "PHS") in rx_data.labels:
            mrd_acquisition.idx.phase = rx_data.labels[key]
        # Repetition counter
        if (key := "REP") in rx_data.labels:
            mrd_acquisition.idx.repetition = rx_data.labels[key]
        # Set counter
        if (key := "SET") in rx_data.labels:
            mrd_acquisition.idx.set = rx_data.labels[key]
        # Segment counter
        if (key := "SEG") in rx_data.labels:
            mrd_acquisition.idx.segment = rx_data.labels[key]


def set_mrd_flags(mrd_acquisition: ismrmrd.Acquisition, rx_data: RxData) -> None:
    """Extract pulseq labels from receive data and set them in MRD acquisition object."""
    if rx_data.labels is not None:
        # Noise flag
        if "NOISE" in rx_data.labels:
            mrd_acquisition.set_flag(ismrmrd.ACQ_IS_NOISE_MEASUREMENT)
        # Parallel imaging flags
        if "REF" in rx_data.labels:
            mrd_acquisition.set_flag(ismrmrd.ACQ_IS_PARALLEL_CALIBRATION)
        if "IMA" in rx_data.labels:
            mrd_acquisition.set_flag(ismrmrd.ACQ_IS_PARALLEL_CALIBRATION_AND_IMAGING)
        # Reverse flag
        if "REV" in rx_data.labels:
            mrd_acquisition.set_flag(ismrmrd.ACQ_IS_REVERSE)
        # Navigator flag
        if "NAV" in rx_data.labels:
            mrd_acquisition.set_flag(ismrmrd.ACQ_IS_NAVIGATION_DATA)
