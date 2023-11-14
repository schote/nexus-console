# %%
import numpy as np
import matplotlib.pyplot as plt

# %%
N = 64

kx = (np.arange(64) - int(N/2))/N
ky = (np.arange(64) - int(N/2))/N

traj_x, traj_y = np.meshgrid(
    kx, ky, indexing="xy"
)

distance = np.sqrt(traj_x**2 + traj_y**2)

fig, ax = plt.subplots(1, 2, figsize=(10, 5))
ax[0].scatter(traj_x, traj_y, marker="x", s=5)
ax[0].set_ylabel("k_y")
ax[0].set_xlabel("k_x")
ax[1].imshow(distance)

# %%
