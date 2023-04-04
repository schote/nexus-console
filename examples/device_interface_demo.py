# %%
# imports
import os
import yaml
from pprint import pprint
import plotly.express as px
import plotly.io as pio

from console.utilities.io import yaml_loader
from console.pulseq_interpreter.sequence import SequenceWrapper

# Plotly configuration
pio.renderers.default = "notebook"

# %%
# Load device configuration
# Config file path
config_file = os.path.normpath("/Users/schote01/code/spectrum-pulseq/device_config.yaml")

# Load config
with open(config_file, 'rb') as file:
    config = yaml.load(file, Loader=yaml_loader)

# Get devices: RxCard or TxCard
devices = config["devices"]

# Print devices
for dev in devices:
    print(dev.__name__)
    pprint(dev.dict())
    
    
# %%
# Get the tx card by filtering the class names and call it's init function
tx_card = list(filter(lambda device: device.__name__ == "TxCard", devices))[0]

tx_card.init_card()

# %%
# Read system config
system = config["system"][0]
print(f"Found system configuration: {type(system)}")


# %%
# Load sequence and modulate RF block 
seq = SequenceWrapper(system)
seq_path = os.path.normpath("/Users/schote01/code/spectrum-pulseq/examples/pulseq/fid.seq")
seq.read(seq_path)

rf_mod, t = seq.get_modulated_rf_block(1)

fig = px.line(x=t, y=rf_mod, title='Sinc RF Pulse', labels=dict(x="Time (us)", y="RF Amplitude"))
fig.show()

# %%
