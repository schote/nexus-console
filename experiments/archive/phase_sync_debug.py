"""Execution of a spin echo experiment using the acquisition control."""
# %%
# imports
import numpy as np
import matplotlib.pyplot as plt
from console.spcm_control.interface_acquisition_parameter import AcquisitionParameter, Dimensions
from console.spcm_control.acquisition_control import AcquistionControl
from console.utilities.spcm_data_plot import plot_spcm_data
from console.spcm_control.ddc import apply_ddc
import time
from scipy.signal import butter, filtfilt

# %%
# Create acquisition control instance
configuration = "../device_config.yaml"
acq = AcquistionControl(configuration)

# %%
# Sequence filename

# filename = "se_proj_400us-sinc_20ms-te"
filename = "se_proj_400us_sinc_12ms-te"
# filename = "se_spectrum_400us_sinc_20ms-te"
# filename = "se_spectrum_2500us_sinc_12ms-te"
# filename = "dual-se_spec"

seq_path = f"../sequences/export/{filename}.seq"

f_0 = 2037612

n_samples = 500
n_avg = 10
# grad_fovs = np.arange(30) * 0.05
grad_fovs = [0] # no gradients

save_data = False
result_path = "/home/schote01/data/phase_sync/ref_signal/"

_time = np.arange(n_samples) * acq.dwell_time

for alpha in grad_fovs:
    # Loop over different fovs
    
    grad_amp = round(alpha * 200)   # amplitude in mV according to scope
    print(f"FOV scaling factor: {grad_amp} mV")
    
    ref = []
    raw = []
    fit = []

    for k in range(n_avg):

        # Define acquisition parameters
        params = AcquisitionParameter(
            larmor_frequency=f_0,
            b1_scaling=5.0,
            # b1_scaling=7.0,
            fov_scaling=Dimensions(
                x=alpha,
                # x=0.,
                y=0., 
                z=0.
            ),
            fov_offset=Dimensions(x=0., y=0., z=0.),
            downsampling_rate=200
        )

        # Perform acquisition
        acq.run(parameter=params, sequence=seq_path)

        # First argument data from channel 0 and 1,
        # second argument contains the phase corrected echo
        _raw, _ref = acq.data[0][0]
        
        # Truncate signals
        ro_start = int(_raw.size/2 - n_samples/2)
        raw.append(_raw[ro_start:ro_start+n_samples])
        ref.append(_ref[ro_start:ro_start+n_samples])
        
        m_phase, b_phase = np.polyfit(_time, np.angle(ref[-1]), 1)
        _fit = m_phase * _time + b_phase
        fit.append(_fit)
        
        # Wait for next iteraton of average
        time.sleep(0.3)
        
    raw = np.stack(raw)
    ref = np.stack(ref)
    fit = np.stack(fit)

    # raw *= np.exp(-1j * np.angle(ref))

    # Calculate average and spectrum of average
    raw_avg = np.mean(np.stack(raw), axis=0)
    data_fft = np.fft.fftshift(np.fft.fft(raw_avg))
    fft_freq = np.fft.fftshift(np.fft.fftfreq(raw_avg.size, acq.dwell_time))

    # Print peak height and center frequency
    max_spec = np.max(np.abs(data_fft))
    f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]

    print(f"\n>> Frequency offset [Hz]: {f_0_offset}, new frequency f0 [Hz]: {f_0 - f_0_offset}")
    print(f">> Frequency spectrum max.: {max_spec}")

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    ax.plot(fft_freq, np.abs(data_fft), label=f"Average: {n_avg}")
    ax.set_xlim([-20e3, 20e3])
    ax.set_ylim([0, max_spec*1.05])
    ax.set_ylabel("Abs. FFT Spectrum [a.u.]")
    ax.set_xlabel("Frequency [Hz]")
    ax.set_title("1D Projection")
    ax.legend()


    # Save to file
    if save_data:
        np.save(f"{result_path}raw_xgrad-{grad_amp}mV.npy", raw)
        np.save(f"{result_path}ref_xgrad-{grad_amp}mV.npy", ref)
        plt.savefig(f"{result_path}/spectrum_xgrad-{grad_amp}mV.png")
    
        plt.close()

# %%
# Plot phase
fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(raw.shape[0]):
    ax.plot(_time*1e3, np.degrees(np.angle(raw[k, ...])), label=f"k: {k}")
ax.legend()
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")


fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(ref.shape[0]):
    ax.plot(_time*1e3, np.degrees(np.angle(ref[k, ...])), label=f"k: {k}")
ax.legend()
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")

fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(ref.shape[0]):
    ax.plot(_time*1e3, np.degrees(fit[k, ...]), label=f"fit k: {k}")
ax.legend()
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")

# %%

norm = raw * np.exp(-1j * np.angle(ref))

fig, ax = plt.subplots(1, 1, figsize=(10, 5))
for k in range(ref.shape[0]):
    ax.plot(_time*1e3, np.degrees(np.angle(norm[k, ...])), label=f"k: {k}")
ax.legend(loc="center left")
ax.set_ylabel("Phase [°]")
ax.set_xlabel("Time [ms]")

# %%

avg_corr = np.mean(norm, axis=1)



# %%
# # Save phase plot
# plt.savefig("/home/schote01/data/phase_sync/joint_clock/phase_plot.png")

# # Save raw data to text
# for k in range(raw.shape[0]):
#     np.savetxt(f"/home/schote01/data/phase_sync/joint_clocks/raw_{k}.txt", raw[k, ...])

# %%
