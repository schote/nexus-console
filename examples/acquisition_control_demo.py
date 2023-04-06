# %%
import yaml
import numpy as np

from console.utilities.io import yaml_loader
from console.spcm_control.acquisition_control import AcquistionControl
from console.pulseq_interpreter.sequence import SequenceProvider

# %%

config_file = os.path.normpath("/Users/schote01/code/spectrum-pulseq/device_config.yaml")

# Load config
with open(config_file, 'rb') as file:
    config = yaml.load(file, Loader=yaml_loader)

# Get devices: RxCard or TxCard
devices = config["devices"]
tx_card = list(filter(lambda device: device.__name__ == "TxCard", devices))[0]
rx_card = list(filter(lambda device: device.__name__ == "RxCard", devices))[0]

# Get sequence provider
# system = config["system"][0]
# seq = SequenceProvider(system)

# # Read sequence
# seq_path = os.path.normpath("/Users/schote01/code/spectrum-pulseq/examples/pulseq/fid.seq")
# seq.read(seq_path)

acq_control = AcquistionControl(tx_card, rx_card)

# %%

seq = np.arange(16)
print(f"Data passed to acquire func.: {seq}")
_ = acq_control.acquire(seq)

# %%
