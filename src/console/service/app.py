"""Nexus service client application."""
import argparse
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pypulseq as pp
import uvicorn
from fastapi import BackgroundTasks, FastAPI

import console
from console.interfaces.acquisition_data import AcquisitionData
from console.service.models import Job
from console.spcm_control.acquisition_control import AcquisitionControl
from console.service import config

# Define logging levels
get_log_level = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

def start_service():
    uvicorn.run("console.service.app:app", host=config.HOST, port=config.PORT, reload=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    parser = argparse.ArgumentParser(description="Start Nexus acquisition service.")
    parser.add_argument("--device_config", type=str,
        help="Path to device configuration yaml file.",
    )
    parser.add_argument("--sessions_folder", type=str, default=os.path.join(Path.home(), "nexus-console"),
        help="Directory to store all the acquisition data acquired during the session.",
    )
    parser.add_argument("--file_log_level", type=str,default="INFO",
        help="Level of logging in log file: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    parser.add_argument("--console_log_level", type=str, default="INFO",
        help="Level of logging in log file: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )
    args = parser.parse_args()

    print(args.file_log_level)
    input("[NEXUS] Before starting the setup, confirm that all the amplifiers are turned off.\nPress Enter to continue...")
    print("[NEXUS] Setting up the acquisition control...")

    # Create global instance
    global acq
    acq = AcquisitionControl(
        configuration_file=args.device_config,
        nexus_data_dir=args.sessions_folder,
        file_log_level=get_log_level[args.file_log_level],
        console_log_level=get_log_level[args.console_log_level],
    )

    input("[NEXUS] Setup completed, hardware components can be turned on.\nPress Enter to continue...")
    print("[NEXUS] Test:: Acquisition control instance: ", acq)

    yield
    # Delete acquisition control instance at the end of the lifespan
    del acq

# Define App and global variables
app = FastAPI(lifespan=lifespan)
acq: AcquisitionControl | None = None
job_queue: dict = {}


@app.get("/healthiness", response_model={}, tags=["health"])
async def health() -> dict:
    """Check if the service is running and healthy."""
    if acq is None:
        return {"status": "error", "message": "Acquisition control not initialized"}
    return {"status": "ok"}


@app.post("/acquisition_parameter", tags=["acquisition"])
async def set_acquisition_parameter(params: dict) -> dict:
    """Update acquisition parameters.

    Parameters
    ----------
    params
        Dictionary with acquisition parameters to be updated.

    Returns
    -------
        Updated dictionary
    """
    print("[NEXUS] Acquisition parameters to update: ", params)
    console.parameter.update(params)
    print("[NEXUS] Set acquisition parameter: ", console.parameter)
    return console.parameter.dict()


@app.get("/acquisition_parameter", tags=["acquisition"])
async def get_acquisition_parameter() -> dict:
    """Return acquisition parameters.

    Returns
    -------
        Dictionary of acquisition parameters.
    """
    return console.parameter.dict()


@app.post("/submit", tags=["acquisition"])
async def submit_sequence(job: Job, background_tasks: BackgroundTasks):
    """Submit a new job. Returns a job_id that you can use to check status."""
    # Generate a unique job ID
    job_id = str(uuid.uuid4())

    # Initialize status as "queued"
    job_queue[job_id] = {
        "state": "queued",
        "sequence": job.sequence,
    }

    # Schedule the "worker" to run in the background
    background_tasks.add_task(acquisition_worker, job_id=job_id, job=job)
    return {"job_id": job_id}


@app.get("/status/{job_id}", tags=["jobs"])
async def get_status(job_id: str):
    """Retrieve the status of a previously submitted job."""
    if job_id in job_queue:
        return job_queue[job_id]
    return {"error": "Job not found", "job_id": job_id}


def acquisition_worker(job_id: str, job: Job) -> None:
    """Perform sequence execution.

    Parameters
    ----------
    job_id
        ID of the sequence acquisition job
    job
        Acquisition job object

    Returns
    -------
        Dictionary with the result path of the acquisition
    """
    global acq
    if acq is None:
        job_queue[job_id]["state"] = "error: acquisition control not initialized"
        return
    seq = pp.Sequence(acq.seq_provider.system).read(job.sequence) if job.sequence is str else job.sequence

    # Set sequence
    acq.set_sequence(seq)
    # Mark as running
    job_queue[job_id]["state"] = "running"

    acq_data: AcquisitionData = acq.run()
    acq_data_path = acq_data.save(save_unprocessed=job.save_unprocessed)

    # Mark job as finished and store a "result"
    job_queue[job_id]["state"] = "finished"
    job_queue[job_id]["result"] = acq_data_path
    print(f"[Worker] Completed job_id={job_id}")
