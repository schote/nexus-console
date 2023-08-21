import yaml
from pypulseq.opts import Opts
from console.spcm_control.rx_device import RxCard
from console.spcm_control.tx_device import TxCard
from console.pulseq_interpreter.sequence_provider import SequenceProvider


yaml_loader = yaml.SafeLoader

# Add constructors to PyYAML loader
yaml_loader.add_constructor(
    "!TxCard", lambda loader, node: TxCard(**loader.construct_mapping(node, deep=True))
)
yaml_loader.add_constructor(
    "!RxCard", lambda loader, node: RxCard(**loader.construct_mapping(node, deep=True))
)
yaml_loader.add_constructor(
    "!SequenceProvider", lambda loader, node: SequenceProvider(**loader.construct_mapping(node, deep=True))
)
yaml_loader.add_constructor(
    "!Opts", lambda loader, node: Opts(**loader.construct_mapping(node, deep=True))
)
