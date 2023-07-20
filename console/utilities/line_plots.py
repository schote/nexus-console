import matplotlib.pyplot as plt
import numpy as np

def plot_spcm_data(data: np.ndarray, num_channels: int):
    
    fig, ax = plt.subplots(num_channels, 1, figsize=(16, 9))
    minmax = (data[:].min(), data[:].max()*1.10)
    
    for k in range(num_channels):
        ax[k].plot(data[k::num_channels])
        ax[k].set_ylabel("Channel {}".format(k+1))
        ax[k].set_ylim(minmax)
        
    ax[k].set_xlabel("Number of samples")
        
    return fig
    