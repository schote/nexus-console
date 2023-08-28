import os

import yaml
from pypulseq.opts import Opts

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard

# >> Create yaml loader object
yaml_loader = yaml.SafeLoader

# >> Add constructors to PyYAML loader
yaml_loader.add_constructor("!RxCard", lambda loader, node: RxCard(**loader.construct_mapping(node, deep=True)))
yaml_loader.add_constructor("!TxCard", lambda loader, node: TxCard(**loader.construct_mapping(node, deep=True)))
yaml_loader.add_constructor(
    "!SequenceProvider", lambda loader, node: SequenceProvider(**loader.construct_mapping(node, deep=True))
)
yaml_loader.add_constructor("!Opts", lambda loader, node: Opts(**loader.construct_mapping(node, deep=True)))


# >> Helper functions to read configuration file


def read_config(path_to_config: str) -> dict:
    """Read configuration yaml file with custom yaml loader.

    Custom yaml loader contains constructors for transmit and receive cards and for sequence provider and pypulseq parameters.

    Parameters
    ----------
    path_to_config
        Path to configuration yaml file

    Returns
    -------
        Dictionary with all entries from configuration yaml file
    """
    file_path = os.path.normpath(path_to_config)
    with open(file_path, "rb") as file:
        config = yaml.load(file, Loader=yaml_loader)
    return config


# >> Helper functions to get instances


def get_sequence_provider(path_to_config: str = "../device_config.yaml") -> SequenceProvider:
    """Get a sequence provider class instance.

    Parameters
    ----------
    path_to_config, optional
        Path to configuration yaml file, by default "../device_config.yaml"

    Returns
    -------
        Sequence provider class instance with configuration from yaml file.
    """
    return read_config(path_to_config)["SequenceProvider"]


def get_tx_card(path_to_config: str = "../device_config.yaml") -> TxCard:
    """Get a transmit card class instance.

    Parameters
    ----------
    path_to_config, optional
        Path to configuration yaml file, by default "../device_config.yaml"

    Returns
    -------
        Transmit card class instance with configuration from yaml file.
    """
    return read_config(path_to_config)["TxCard"]


def get_rx_card(path_to_config: str = "../device_config.yaml") -> RxCard:
    """Get a receive card class instance.

    Parameters
    ----------
    path_to_config, optional
        Path to configuration yaml file, by default "../device_config.yaml"

    Returns
    -------
        Receive card class instance with configuration from yaml file.
    """
    return read_config(path_to_config)["RxCard"]
