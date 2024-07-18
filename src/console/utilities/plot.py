"""Plotting methods."""
import matplotlib.pyplot as plt
import numpy as np


def plot_slices(img: np.ndarray, vmin: float | None = None, vmax: float | None = None):
    """Return sliced plot of 3D image data."""
    num_slices = img.shape[0]
    num_cols = int(np.ceil(np.sqrt(num_slices)))
    num_rows = int(np.ceil(num_slices/num_cols))

    fig, ax = plt.subplots(num_rows, num_cols, figsize=(10, 10))
    ax = ax.ravel()

    total_max = np.amax(np.abs(img)) if not vmax else vmax
    total_min = 0 if not vmin else vmin

    for k, x in enumerate(img[:, ...]):
        ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray")
        ax[k].axis("off")
    _ = [a.remove() for a in ax[k+1:]]

    fig.tight_layout(pad=0.05)
    fig.set_facecolor("black")

    return fig, ax
