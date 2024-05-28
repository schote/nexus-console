"""Utility functions for loading configuration and adding constructors."""
import os

import yaml
from pypulseq.opts import Opts

from console.pulseq_interpreter.sequence_provider import SequenceProvider
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.spcm_control.sync_device import SyncCard

def tx_card_constructor(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode) -> TxCard:
    """Construct a transmit card object.

    Parameters
    ----------
    loader
        yaml loader
    node
        constructor mapping

    Returns
    -------
        TxCard object
    """
    # Ignore type checking here since mypy requires keywords to be strings
    return TxCard(**loader.construct_mapping(node, deep=True))  # type: ignore

def sync_card_constructor(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode) -> SyncCard:
    """Construct a synchronization card object.

    Parameters
    ----------
    loader
        yaml loader
    node
        constructor mapping

    Returns
    -------
        TxCard object
    """
    # Ignore type checking here since mypy requires keywords to be strings
    return SyncCard(**loader.construct_mapping(node, deep=True))  # type: ignore

def rx_card_constructor(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode) -> RxCard:
    """Construct a receive card object.

    Parameters
    ----------
    loader
        yaml loader
    node
        constructor mapping

    Returns
    -------
        RxCard object
    """
    # Ignore type checking here since mypy requires keywords to be strings
    return RxCard(**loader.construct_mapping(node, deep=True))  # type: ignore


def sequence_provider_constructor(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode) -> SequenceProvider:
    """Construct a sequence provider.

    Parameters
    ----------
    loader
        yaml loader
    node
        constructor mapping

    Returns
    -------
        SequenceProvider object
    """
    # Ignore type checking here since mypy requires keywords to be strings
    return SequenceProvider(**loader.construct_mapping(node, deep=True))  # type: ignore


def opts_constructor(loader: yaml.SafeLoader, node: yaml.nodes.MappingNode) -> Opts:
    """Construct an options object.

    Parameters
    ----------
    loader
        yaml loader
    node
        constructor mapping

    Returns
    -------
        Options object
    """
    return Opts(**loader.construct_mapping(node, deep=True))


# >> Helper function to read configuration file
def get_instances(path_to_config: str) -> tuple[SequenceProvider,SequenceProvider, TxCard, TxCard , RxCard, SyncCard]:
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
    if not file_path.endswith(".yaml"):
        raise FileNotFoundError("Invalid configuration file, yaml file required.")
    with open(file_path, "rb") as file:
        config = yaml.load(file, Loader=Loader)  # noqa: S506

    # Set output limits of sequence provider to the maximum amplitudes from transmit card
    config["SequenceProviders"][0].output_limits = config["TxCards"][0].max_amplitude
    config["SequenceProviders"][1].output_limits = config["TxCards"][1].max_amplitude
    return (config["SequenceProviders"][0],config["SequenceProviders"][1], config["TxCards"][0],config["TxCards"][1], config["RxCard"],config["SyncCard"])


# >> Create yaml loader object
Loader = yaml.SafeLoader

# >> Add constructors to PyYAML loader
Loader.add_constructor("!RxCard", rx_card_constructor)
Loader.add_constructor("!TxCard", tx_card_constructor)
Loader.add_constructor("!SyncCard", sync_card_constructor)
Loader.add_constructor("!SequenceProvider", sequence_provider_constructor)
Loader.add_constructor("!Opts", opts_constructor)
