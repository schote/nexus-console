# %%
import sequence_gradint_calibration
import logging

from console.spcm_control.acquisition_control import AcquisitionControl

# %%
seq = sequence_gradint_calibration.constructor(
    fov=0.24,
    num_samples=120,
    ramp_duration=200e-6,
    ro_bandwidth=20e3,
    delay=1e-3
)

seq.plot()

# %%

configuration_file = "../device_config.yaml"
acq = AcquisitionControl(configuration_file=configuration_file, console_log_level=logging.INFO, file_log_level=logging.DEBUG)

acq.set_sequence(seq)
# acq.seq_provider.plot_unrolled()

acq_data = acq.run()

# %%
