import yaml

from console.spcm_control.tx_device import TxCard
from console.spcm_control.rx_device import RxCard

# from pypulseq.opts import Opts

# Add constructors to PyYAML loader
yaml_loader = yaml.SafeLoader
yaml_loader.add_constructor("!TxCard", lambda loader, node: TxCard(**loader.construct_mapping(node, deep=True)))
yaml_loader.add_constructor("!RxCard", lambda loader, node: RxCard(**loader.construct_mapping(node, deep=True)))
# yaml_loader.add_constructor("!System", lambda loader, node: Opts(**loader.construct_mapping(node)))