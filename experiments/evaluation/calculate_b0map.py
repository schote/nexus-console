import numpy as np
import os
import json

# %%
# 1st acquisition == TE1, 2nd acquisition == TE2
acquisitions = [
    "C:\Users\Tom\Desktop\spcm-data\b0-map\2024-02-15-155826-tse_3d",
    # "C:\Users\Tom\Desktop\spcm-data\b0-map\2024-02-15-153630-tse_3d"
]

meta = []
data = []

for acq in acquisitions:
    _data = np.load(os.path.join(acq, "raw_data.npy"))
    data.append(_data)
    with open(os.path.join(acq, "meta.json")) as fh:
        _meta = json.dumps(fh)
        meta.append(_meta)