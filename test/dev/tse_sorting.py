# %%
import numpy as np
import matplotlib.pyplot as plt

# %%
N = 16

kx = (np.arange(N) - int(N/2))/N
ky = (np.arange(N) - int(N/2))/N

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

ordering = np.flip(np.argsort(distance.flatten()))

traj_x_sorted = traj_x.flatten()[ordering]
traj_y_sorted = traj_y.flatten()[ordering]

max_pts = 10

plt.plot(traj_x_sorted[:max_pts], traj_y_sorted[:max_pts])
# %%
