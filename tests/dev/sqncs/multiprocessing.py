# # %%
# import numpy as np
# from scipy.signal import resample
# import matplotlib.pyplot as plt

# # %%
# def calculate_rf(waveform, unrolled_data):
#     n_samples = unrolled_data.size
#     ref_time = np.arange(n_samples) / 20e6
#     envelope = resample(waveform, num=n_samples)
#     unrolled_data[:] = (envelope + 0j) * np.exp(2j * np.pi * (2e6 * ref_time))


# # %%
# # Construct example
# n_samples = 1000
# freq_1 = 3
# freq_2 = 5
# freq_3 = 11
# dt = 400e-6
# t = np.arange(n_samples) * dt

# rf_1 = np.sin(2* np.pi * freq_1 * t)
# rf_2 = np.sin(2* np.pi * freq_2 * t)
# rf_3 = np.sin(2* np.pi * freq_3 * t)

# fig, ax = plt.subplots(1, 1, figsize=(6, 4))
# ax.plot(rf_1)
# ax.plot(rf_2)
# ax.plot(rf_3)

# n_unrolled_samples = int(n_samples * dt * 20e6)
# seq = [np.zeros(n_unrolled_samples, dtype=complex) for _ in range(3)]

# for k, block in enumerate([rf_1, rf_2, rf_3]):
#     calculate_rf(waveform=block, unrolled_data=seq[k])

# fig, ax = plt.subplots(3, 1, figsize=(9, 6))
# for k, data in enumerate(seq):
#     ax[k].plot(np.real(data))

# # %%
