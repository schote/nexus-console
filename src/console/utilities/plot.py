"""Plotting methods."""
import matplotlib.pyplot as plt
import numpy as np


def plot_slices(img: np.ndarray, vmin: float | None = None, vmax: float | None = None, set_aspect: bool = False):
    """Return sliced plot of 3D image data."""
    num_slices = img.shape[0]
    num_cols = int(np.ceil(np.sqrt(num_slices)))
    num_rows = int(np.ceil(num_slices / num_cols))

    fig, ax = plt.subplots(num_rows, num_cols, figsize=(10, 10))
    ax = ax.ravel()

    total_max = np.amax(np.abs(img)) if not vmax else vmax
    total_min = 0 if not vmin else vmin

    for k, x in enumerate(img[:, ...]):
        if set_aspect:
            dim = x.shape
            ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray", aspect=dim[1]/dim[0])
        else:
            ax[k].imshow(np.abs(x), vmin=total_min, vmax=total_max, cmap="gray")
        ax[k].axis("off")
    _ = [a.remove() for a in ax[k + 1:]]

    fig.tight_layout(pad=0.05)
    fig.set_facecolor("black")

    return fig, ax


def plot_2d(img: np.ndarray, vmin: float | None = None, vmax: float | None = None, set_aspect: bool = True, cmap="gray"):
    """Return 2D plot image plot."""
    dim = img.shape[-2:]
    if set_aspect:
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))
        ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, aspect=dim[1]/dim[0])
    else:
        fig, ax = plt.subplots(1, 1)
        ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.axis("off")
    fig.tight_layout(pad=0.)
    fig.set_facecolor("black")
    return fig, ax


def plot_1d(img: np.ndarray, vmin: float | None = None, vmax: float | None = None, set_aspect: bool = True, cmap="gray"):
    """Return 2D plot image plot."""
    dim = img.shape[-2:]
    if set_aspect:
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))
        ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, aspect=dim[1]/dim[0])
    else:
        fig, ax = plt.subplots(1, 1)
        ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.axis("off")
    fig.tight_layout(pad=0.)
    fig.set_facecolor("black")
    return fig, ax