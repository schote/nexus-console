import yaml

from console.spcm_control.device import TxCard, RxCard
from pypulseq.opts import Opts

# Add constructors to PyYAML loader
yaml_loader = yaml.SafeLoader
yaml_loader.add_constructor("!TxCard", lambda loader, node: TxCard(**loader.construct_mapping(node)))
yaml_loader.add_constructor("!RxCard", lambda loader, node: RxCard(**loader.construct_mapping(node)))
yaml_loader.add_constructor("!System", lambda loader, node: Opts(**loader.construct_mapping(node)))