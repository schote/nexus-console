import requests
from console.service import config
from console.service.models import Job
from console.interfaces.acquisition_parameter import AcquisitionParameter

BASE_URL = config.get_url()

def help_menu():
    """Print help menu."""
    print(
        """
Available commands:
  health                        - Check if the server is running and healthy
  acquisition_parameters        - Get current acquisition parameters
  set_parameters param1=val ... - Set acquisition parameters. e.g., set param1=10 param2="hello"
  submit SEQUENCE_PATH          - Submit a new job (sequence). e.g., submit "my_test_sequence.seq"
  status JOB_ID                 - Retrieve the status of a previously submitted job
  exit / quit                   - Exit the application
  help                          - Show this help menu
"""
    )

def health():
    """Check service healthiness."""
    try:
        resp = requests.get(f"{BASE_URL}/healthiness")
        print(f"Response ({resp.status_code}): {resp.json()}")
    except requests.RequestException as e:
        print("Error:", e)

def get_acquisition_parameter():
    """Get current acquisition parameters."""
    try:
        resp = requests.get(f"{BASE_URL}/acquisition_parameter")
        print(f"Response ({resp.status_code}): {resp.json()}")
    except requests.RequestException as e:
        print("Error:", e)

def set_acquisition_parameter(params):
    """
    Update acquisition parameters.

    Parameters
    ----------
    params : dict
        Dictionary of parameters to be updated.
    """
    try:
        new_params = requests.post(f"{BASE_URL}/acquisition_parameter", json=params)
        return AcquisitionParameter(**new_params.json())
    except requests.RequestException as e:
        print("Error:", e)

def submit_sequence(sequence_data):
    """Submit a new job."""
    try:
        resp = requests.post(f"{BASE_URL}/submit", json=Job(sequence=sequence_data))
        print(f"Response ({resp.status_code}): {resp.json()}")
    except requests.RequestException as e:
        print("Error:", e)

def get_job_status(job_id: str):
    """Retrieve the status of a previously submitted job."""
    try:
        resp = requests.get(f"{BASE_URL}/status/{job_id}")
        print(f"Response ({resp.status_code}): {resp.json()}")
    except requests.RequestException as e:
        print("Error:", e)

def calibrate_f0(save_unprocessed: bool = False):
    pass

    # current_f0 = get_acquisition_parameter()["larmor_frequency"]

    # params: dict[str, bool | float] = {
    #     "echo_time": 12e-3,
    #     "rf_duration": 200e-6,
    #     "time_bw_product": 0,
    #     "use_sinc": False,
    #     "adc_duration": 50e-3,
    #     "use_fid": True,
    # }
    # seq = sequences.se_spectrum.constructor(**params)
    # current_f0 = console.parameter.larmor_frequency

    # acq.set_sequence(seq)
    # acq_data: AcquisitionData = acq.run()

    # # FFT
    # data = np.mean(acq_data.raw, axis=0)[0].squeeze()
    # data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
    # fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, acq_data.dwell_time))

    # max_spec = np.max(np.abs(data_fft))
    # f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]
    # snr = signal_to_noise_ratio(data_fft, dwell_time=acq_data.dwell_time)

    # # Plot spectrum
    # time_axis = np.arange(data.size)*acq_data.dwell_time*1e3
    # fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    # ax[0].plot(time_axis, np.abs(data), label="Abs")
    # ax[0].plot(time_axis, np.real(data), label="Re")
    # ax[0].plot(time_axis, np.imag(data), label="Im")
    # ax[0].legend(loc="upper right")
    # ax[1].plot(fft_freq, np.abs(data_fft))
    # ax[1].set_ylim([0, max_spec * 1.05])
    # ax[0].set_xlabel("Time / ms")
    # ax[0].set_ylabel("RX signal / mV")
    # ax[1].set_ylabel("Abs. FFT Spectrum / a.u.")
    # ax[1].set_xlabel("Frequency / Hz")
    # plt.show()

    # print(f"[FREQ CALIBRATION] Current f0 / Hz: {f_0_offset}")
    # print(f"[FREQ CALIBRATION] Offset / Hz: {f_0_offset}")
    # print(f"[FREQ CALIBRATION] SNR / dB: {snr}")

    # #update global larmor frequency to measured f0
    # if abs(f_0_offset) <= 8e3:
    #     print(f"[FREQ CALIBRATION] Updated f0 value / Hz: {current_f0 - f_0_offset}")
    #     console.parameter.larmor_frequency = current_f0 - f_0_offset

    # # Add information to acquisition data
    # acq_data.add_info({
    #     "current f0 / Hz": current_f0,
    #     "f0 offset / Hz": f_0_offset,
    #     "new f0 / Hz": current_f0 - f_0_offset,
    #     "magnitude spectrum max": max_spec,
    #     "snr / dB": snr,
    # })

    # acq_data.save(save_unprocessed=save_unprocessed)

def calibrate_b1():
    pass

def calibrate_shimming():
    pass
