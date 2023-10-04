"""Utility functions for loading configuration and adding constructors."""
import os

import yaml
from pypulseq.opts import Opts

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard

# >> Create yaml loader object
Loader = yaml.SafeLoader

# >> Add constructors to PyYAML loader
Loader.add_constructor("!RxCard", lambda loader, node: RxCard(**loader.construct_mapping(node, deep=True)))
Loader.add_constructor("!TxCard", lambda loader, node: TxCard(**loader.construct_mapping(node, deep=True)))
Loader.add_constructor(
    "!SequenceProvider", lambda loader, node: SequenceProvider(**loader.construct_mapping(node, deep=True))
)
Loader.add_constructor("!Opts", lambda loader, node: Opts(**loader.construct_mapping(node, deep=True)))


# >> Helper functions to read configuration file


def get_instances(path_to_config: str) -> tuple[SequenceProvider, TxCard, RxCard]:
    """Construct object instances from yaml configuration file.

    Uses custom yaml loader which contains constructors for sequence provider, transmit and receive cards.
    Object instances are created according to the parameterization from yaml configuration file.
    This function returns object instances for all the different constructors.

    Parameters
    ----------
    path_to_config
        Path to configuration yaml file

    Returns
    -------
        Tuple of instances: SequenceProvider, TxCard and RxCard
    """
    file_path = os.path.normpath(path_to_config)
    with open(file_path, "rb") as file:
        config = yaml.load(file, Loader=Loader)

    return (config["SequenceProvider"], config["TxCard"], config["RxCard"])
