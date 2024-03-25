# %%
import sequence_gradint_calibration
import logging

from console.spcm_control.acquisition_control import AcquisitionControl
import matplotlib.pyplot as plt

# %%

configuration_file = "../../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration_file, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

# %%
seq = sequence_gradint_calibration.constructor(
    fov=0.24,
    num_samples=120,
    ramp_duration=200e-6,
    ro_bandwidth=20e3,
    delay=10e-3,
    post_gradient_adc_duration=0.5e-3
)
seq.plot()

# %%
acq.set_sequence(seq)
# acq.seq_provider.plot_unrolled()
acq_data = acq.run()

# %%
gradient_data = acq_data.unprocessed_data[0][0, 1, 0, ...]
plt.plot(gradient_data)


# %%

acq_data.save(user_path=r"C:\Users\Tom\Desktop\spcm-data_25-03-24\gradient-calibration", save_unprocessed=True)
# %%
