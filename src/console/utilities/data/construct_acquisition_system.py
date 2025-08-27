"""Methods helping to construct or complete ISMRMRD header."""
import ismrmrd
from importlib_metadata import version


def get_nexus_acquisition_system(
    num_coils: int,
    larmor_frequency: float | None,
) -> ismrmrd.xsd.acquisitionSystemInformationType:
    """Define the nexus console specific acquisition system information for ISMRMRD header."""
    system_version = version("console")
    system_info = ismrmrd.xsd.acquisitionSystemInformationType()
    system_info.receiverChannels = num_coils
    system_info.systemVendor = "osi2"
    system_info.systemModel = f"Nexus_{system_version}"
    if larmor_frequency is not None:
        system_info.systemFieldStrength_T = round(larmor_frequency / 42.58e6, 4)
    return system_info
