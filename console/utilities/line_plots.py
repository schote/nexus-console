import matplotlib.pyplot as plt
import numpy as np

def plot_spcm_data(data: np.ndarray, num_channels: int):
    
    fig, ax = plt.subplots(num_channels, 1, figsize=(16, 9))
    
    # Extract min-max values per channel
    minmax = [(data[k::num_channels].min(), data[k::num_channels].max()) for k in range(num_channels)]
    # Add +-10% of absolute to the calculated limits
    minmax = [(val[0] - abs(val[0])*0.1, val[1] + abs(val[1])*0.1) for val in minmax]
    
    for k in range(num_channels):
        ax[k].plot(data[k::num_channels])
        ax[k].set_ylabel("Channel {}".format(k+1))
        if not minmax[k][0] == minmax[k][1]:
            ax[k].set_ylim(minmax[k])
        
    ax[k].set_xlabel("Number of samples")
        
    return fig
    