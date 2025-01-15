# from fastapi import FastAPI
from contextlib import asynccontextmanager
from pathlib import Path
import os
import uvicorn
from fastapi import FastAPI
import argparse
import logging
from pathlib import Path
from fastapi import BackgroundTasks
from pydantic import BaseModel
import time
import uuid
import logging
from pathlib import Path
# from console.spcm_control.acquisition_control import AcquisitionControl

# TODO: Replace by acquisition control import above.
get_log_level = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class AcquisitionControl():
    def __init__(
        self,
        var1: str = "hello",
        var2: str = "world",
    ):
        self.a = var1
        self.b = var2
        print("Acquisition control setup completed.")


# class AcquisitionControl():
    # def __init__(
    #     self,
    #     configuration_file: str,
    #     nexus_data_dir: Path = Path(Path.home(), "nexus-console"),
    #     file_log_level: int = logging.INFO,
    #     console_log_level: int = logging.INFO,
    # ):
    #     self.config = configuration_file
    #     self.data = nexus_data_dir
    #     self.file_log = file_log_level
    #     self.console_log = console_log_level
    #     print(f"Acquisition control init dummy:\nConfig: {configuration_file}\nData: {nexus_data_dir}\nFile log: {file_log_level}\nConsole log: {console_log_level}")


class Job(BaseModel):
    """Model representing a job submission."""
    seq_file: str
    params: dict = {}
    
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    parser = argparse.ArgumentParser(description="Start Nexus acquisition service.")
    parser.add_argument(
        "--device_config",
        type=str,
        help="Path to device configuration yaml file.",
    )
    parser.add_argument(
        "--sessions_folder",
        type=str,
        default=os.path.join(Path.home(), "nexus-console"),
        help="Directory to store all the acquisition data acquired during the session.",
    )
    parser.add_argument(
        "--file_log_level",
        type=str,
        default="INFO",
        help="Level of logging in log file: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    parser.add_argument(
        "--console_log_level",
        type=str,
        default="INFO",
        help="Level of logging in log file: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    args = parser.parse_args()
    
    print(args.file_log_level)

    input("[NEXUS] Before starting the setup, confirm that all the amplifiers are turned off.\nPress any key to continue...")
    print("[NEXUS] Setting up the acquisition control...")

    # Create global instance
    global acq
    acq = AcquisitionControl()

    # acq = AcquisitionControl(
    #     configuration_file=args.device_config,
    #     nexus_data_dir=args.sessions_folder,
    #     file_log_level=get_log_level[args.file_log_level],
    #     console_log_level=get_log_level[args.console_log_level],
    # )

    # acq.instance = acq.AcquisitionControl(
    #     configuration_file=args.device_config,
    #     nexus_data_dir=args.sessions_folder,
    #     file_log_level=acq.get_log_level[args.file_log_level],
    #     console_log_level=acq.get_log_level[args.console_log_level],
    # )


    input("[NEXUS] Setup completed, hardware components can be turned on.\nPress any key to continue...")

    print("TEST:: Acquisition is none? ", acq)
    # print("TEST:: ", acq.instance.data)
    # print("TEST:: Acquisition is none? ", acq.instance)
    
    yield
    
    # Define acquisition control deletion



app = FastAPI(lifespan=lifespan)



acq: AcquisitionControl | None = None
job_queue: dict = {}
# TODO: Add status and acquisition progress to acquisition control class.
counter = 0


@app.post("/submit", tags=["jobs"])
def submit_acquisition_job(job: Job, background_tasks: BackgroundTasks):
    """Submit a new job. Returns a job_id that you can use to check status."""
    # Generate a unique job ID
    job_id = str(uuid.uuid4())

    # Initialize status as "queued"
    job_queue[job_id] = {
        "state": "queued",
        "seq_file": job.seq_file,
        "params": job.params,
    }
    global counter
    counter += 1

    # Schedule the "worker" to run in the background
    background_tasks.add_task(acquisition_worker, job_id, job.seq_file, job.params)

    return {"job_id": job_id}



@app.get("/status/{job_id}", tags=["jobs"])
def get_status(job_id: str):
    """Retrieve the status of a previously submitted job."""
    if job_id in job_queue:
        return job_queue[job_id]
    print(job_queue)
    
    global counter
    print("counter: ", counter)
    return {"error": "Job not found", "job_id": job_id}




@app.post("/f0", tags=["calibration"])
async def calibrate_f0(save_unprocessed: bool = False):
    # if acq is None:
    #     return
    print("[FREQ CALIBRATION] Running f0-frequency calibration...")
    # current_f0 = console.parameter.larmor_frequency

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
    
@app.post("/b1", tags=["calibration"])
async def calibrate_b1():
    # if acq is None:
    #     print("Acquisition control not defined.")
    #     return
    # print("[B1 CALIBRATION] Nexus data path: ", acq.data)
    # data = np.random.random(500)
    # fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    # ax.plot(np.arange(data.size), data)
    # ax.set_xlabel("Samples")
    # ax.set_ylabel("Signal")
    # fig.show()
    global acq
    print("B1 calibration endpoint: ", acq)
    

@app.post("/setup_acquisiton_control")
async def setup_acquisition_control():
    global acq
    acq = AcquisitionControl()
    print("Acquisition control setup completed.")


@app.post("/shimming", tags=["calibration"])
async def calibrate_shimming():
    # if acq is None:
    #     return
    print("Calibrate larmor frequency")





def start_service():
    # if acq is not None:
    uvicorn.run("console.service.app:app", reload=True)
        # uvicorn.run(app, reload=True)
        # run_app()





def acquisition_worker(job_id: str, seq_file: str, params: dict):
    # Mark as running
    job_queue[job_id]["state"] = "running"

    # Simulate some work (e.g., reading seq_file, processing params, etc.)
    # TODO: Perform acquisition here
    time.sleep(5)

    # Mark job as finished and store a "result"
    job_queue[job_id]["state"] = "finished"
    job_queue[job_id]["result"] = f"Processed {seq_file} with {params}"
    print(f"[Worker] Completed job_id={job_id}")
    
    