import requests
from console.service import config
from console.interfaces.acquisition_parameter import AcquisitionParameter
from console.utilities.snr import signal_to_noise_ratio
from console.utilities import sequences
import matplotlib.pyplot as plt
import pypulseq as pp
import os
import time
import numpy as np
import json
from scipy.optimize import curve_fit

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
        print(f"[client]  Response ({resp.status_code}): {resp.json()}")
    except requests.RequestException as e:
        print("[client] Error:", e)


def get_acquisition_parameter() -> AcquisitionParameter | None:
    """Get current acquisition parameters."""
    try:
        response = requests.get(f"{BASE_URL}/acquisition_parameter")
        new_params = AcquisitionParameter()
        new_params.update(response.json())
        return new_params
    except requests.RequestException as e:
        print("[client] Error:", e)
    return None


def set_acquisition_parameter(params) -> AcquisitionParameter | None:
    """
    Update acquisition parameters.

    Parameters
    ----------
    params : dict
        Dictionary of parameters to be updated.
    """
    try:
        response = requests.post(f"{BASE_URL}/acquisition_parameter", json=params)
        new_params = AcquisitionParameter()
        new_params.update(response.json())
        return new_params
    except requests.RequestException as e:
        print("[client] Error:", e)
    return None


def submit_acquisition_job(sequence: pp.Sequence | str, save_unprocessed: bool = False) -> str:
    """Submit a new job."""
    if isinstance(sequence, pp.Sequence):
        seq_file = os.path.join(os.path.dirname(__file__) + "/tmp/tmp.seq")
        print("[client] Saving sequence object to temporary file: ", seq_file)
        os.makedirs(os.path.dirname(seq_file), exist_ok=True)
        sequence.write(seq_file)
    else:
        seq_file = sequence
    try:
        resp = requests.post(
            f"{BASE_URL}/submit",
            json={"sequence": seq_file, "save_unprocessed": save_unprocessed}
        )
        data = resp.json()
        # print(f"Response ({resp.status_code}): {data}")
        return data["job_id"]
    except requests.RequestException as e:
        print("[client] Error:", e)
        return ""


def get_job_status(job_id: str):
    """Retrieve the status of a previously submitted job."""
    try:
        resp = requests.get(f"{BASE_URL}/status/{job_id}")
        resp.raise_for_status()
        data = resp.json()
        # print(f"[client] Response ({resp.status_code}): {data}")
        return data
    except requests.RequestException as e:
        print("[client] Error:", e)
        return {}


def wait_until_finished(job_id: str, interval: float = 1, timeout=10):
    start_time = time.time()
    while True:
        if (delta := time.time() - start_time) > timeout:
            raise TimeoutError(f"[client] Job did not finish, timeout after {delta}s.")
        try:
            status = get_job_status(job_id)
            if "state" in status.keys() and status["state"] == "finished":
                return status
        except requests.exceptions.RequestException as e:
            print(f"[client] Error while polling: {e}")
        time.sleep(interval)


def calibrate_f0(save_unprocessed: bool = False):
    if (params := get_acquisition_parameter()) is not None:
        current_f0 = params.larmor_frequency
        print("[f0 calibration] Current larmor frequency / Hz", current_f0)
    else:
        print(f"[f0 calibration] Could not read acquisition parameters.")
        return

    seq_params = {
        "echo_time": 12e-3,
        "rf_duration": 200e-6,
        "time_bw_product": 0,
        "use_sinc": False,
        "adc_duration": 50e-3,
        "use_fid": True,
    }
    seq = sequences.se_spectrum.constructor(**seq_params)

    job_id = submit_acquisition_job(sequence=seq, save_unprocessed=save_unprocessed)
    job = wait_until_finished(job_id)

    if "result" in job.keys():
        acq_path = job["result"]
        data_path = os.path.join(acq_path, "raw_data.npy")
        if not os.path.exists(data_path):
            raise FileNotFoundError(data_path)
        # Load acquisition and meta data
        acq_data = np.load(data_path)
        with open(os.path.join(acq_path, "meta.json"), "rb") as meta_file:
            meta = json.load(meta_file)

        dwell_time = meta["dwell_time"]

        # FFT
        data = np.mean(acq_data, axis=0)[0].squeeze()
        data_fft = np.fft.fftshift(np.fft.fft(np.fft.fftshift(data)))
        fft_freq = np.fft.fftshift(np.fft.fftfreq(data.size, dwell_time))

        max_spec = np.max(np.abs(data_fft))
        f_0_offset = fft_freq[np.argmax(np.abs(data_fft))]
        snr = signal_to_noise_ratio(data_fft, dwell_time=dwell_time)

        # # Plot spectrum
        # time_axis = np.arange(data.size)*dwell_time*1e3
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
        
        print(f"[f0 calibration] Offset / Hz: {f_0_offset}")
        print(f"[f0 calibration] SNR / dB: {snr}")

        #update global larmor frequency to measured f0
        if abs(f_0_offset) <= 8e3 and snr > 20:
            new_f0 = current_f0 - f_0_offset
            new_params = set_acquisition_parameter({"larmor_frequency": new_f0})
            print(f"[f0 calibration] Updated f0 value / Hz: {new_params.larmor_frequency}")
        else:
            print("[f0 calibration] Could not find Larmor frequency, please check system or update Larmor frequency manually.")


def calibrate_b1(num_steps: int = 50, fa_min: int = 20, fa_max: int = 270, tr: float = 3.):
    seq, flip_angles = sequences.fid_tx_adjust.constructor(
        rf_duration=200e-6,
        repetition_time=tr,
        n_steps=num_steps,
        adc_duration = 50e-3,
        flip_angle_range=(np.deg2rad(fa_min), np.deg2rad(fa_max)),
    )
    
    job_id = submit_acquisition_job(sequence=seq)
    job = wait_until_finished(job_id, timeout=2*seq.duration()[0])
    
    if "result" in job.keys():
        acq_path = job["result"]
        data_path = os.path.join(acq_path, "raw_data.npy")
        if not os.path.exists(data_path):
            raise FileNotFoundError(data_path)
        # Load acquisition and meta data
        acq_data = np.load(data_path)
        
        # FFT
        data = np.mean(acq_data, axis=0)[0, ...]
        data = np.abs(np.fft.fftshift(np.fft.fft(np.fft.fftshift(data), axis=-1)))
        area = np.sum(data, axis=-1)
        
        # Define model for flip angles and fit data
        def fa_model(samples: np.ndarray, amp: float, efficiency: float, damping: float, noise: float) -> np.ndarray:
            """Fit sinusoidal function to measured flip angle values."""
            return amp *(1-damping*samples)* np.abs(np.sin(efficiency * samples)) + noise

        print("[b1-cal] Flip angles: ", flip_angles)
        print("[b1-cal] Integrals: ", area.shape)
        
        init = [area.max(), 1, 0, area.min()]
        fit_params = curve_fit(fa_model, xdata=flip_angles, ydata=area, p0=init, method="lm")[0]
        fa = np.linspace(flip_angles[0], flip_angles[-1], num=2000)
        fit = fa_model(fa, *fit_params)
        
        params = get_acquisition_parameter()
    
        # Calculate and print the maximum flip angle corresponding to the peak
        flip_angle_max_amp = np.degrees(flip_angles[np.argmax(area)])
        flip_angle_max_amp_fit = np.degrees(fa[:1000][np.argmax(fit[:1000])])
        print("[b1-cal] Max. signal at flip angle (measurement): ", flip_angle_max_amp)
        print("[b1-cal] Max. signal at flip angle (fit): ", flip_angle_max_amp_fit)
        factor_meas = flip_angle_max_amp / 90
        factor_fit = flip_angle_max_amp_fit / 90
        print("[b1-cal] B1-scaling factor (meas): ", factor_meas)
        print("[b1-cal] B1-scaling factor (fit): ", factor_fit)
        print("[b1-cal] New B1-scaling (meas): ", factor_meas*params.parameter.b1_scaling)
        print("[b1-cal] New B1-scaling (fit): ", factor_fit*params.parameter.b1_scaling)
        
        new_b1 = input("[b1-cal] Enter b1-value to set: ")
        if isinstance(new_b1, float) and new_b1 != params.b1_scaling:
            set_acquisition_parameter({"b1_scaling": new_b1})

def calibrate_shimming():
    print("Not yet implemented.")
    pass
