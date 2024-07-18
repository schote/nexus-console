"""Spin-echo spectrum."""
# imports
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

import console.spcm_control.globals as glob
import console.utilities.sequences as sequences
from console.interfaces.interface_acquisition_data import AcquisitionData
from console.spcm_control.acquisition_control import AcquisitionControl

# Create acquisition control instance
acq = AcquisitionControl(configuration_file="example_device_config.yaml")

# Construct and plot sequence
seq, te_values = sequences.t2_relaxation.constructor(
    echo_time_range=(10e-3, 100e-3), num_steps=50, repetition_time=600e-3
)

# Larmor frequency:
f_0 = 2038550
glob.update_parameters(larmor_frequency=f_0, b1_scaling=2.43)


# Perform acquisition
acq.set_sequence(sequence=seq)
acq_data: AcquisitionData = acq.run()
data = np.mean(acq_data.raw, axis=0).squeeze()

peaks = np.max(data, axis=-1)


# T2 model to fit the acquired data
def t2_model(te_values, a, b, c):
    """Model for T2 relaxation."""
    return a + b * np.exp(-te_values / c)


# Fit parameters to measured data
params = curve_fit(t2_model, xdata=te_values, ydata=np.abs(peaks))[0]
t2 = params[-1]

te_values_fit = np.linspace(te_values[0], te_values[-1], 1000)
# te_values_fit = np.linspace(0, 0.3, 1000)

# Calculate decay with fitted parameters
t2_fit = t2_model(te_values_fit, *params)

# Plot measurement and fit
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.scatter(te_values * 1e3, np.abs(peaks), marker="x", c="b", label="Measurement")
ax.set_xlabel("TE [ms]")
ax.set_ylabel("Abs. signal ampliude [mV]")
ax.plot(te_values_fit * 1e3, t2_fit, linestyle="--", c="r", label=f"Fit, T2 = {round(t2 * 1e3, 4)} ms")
ax.legend()

# Save
# Add information to acquisition data
acq_data.add_info({
    "preamp": "china_preamp",
    "te_values": list(te_values),
    "T2_ms": t2
})
acq_data.save()

del acq
