# %%
from console.spcm_control.acquisition import AcquisitionControl


# %%

control = AcquisitionControl()

control.get_info(control.card_awg)
# control.get_info(control.card_dig)

# %%
