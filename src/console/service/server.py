# server.py
import os
from pathlib import Path
import argparse
import uuid
import asyncio
import threading
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from console.service.models import ScanRequest, Job
import pypulseq as pp

import console
from console.service import config
from console.spcm_control.acquisition_control import AcquisitionControl
from console.interfaces.acquisition_data import AcquisitionData


def lifespan(app: FastAPI):
    parser = argparse.ArgumentParser(description="Start Nexus acquisition service.")
    parser.add_argument("-d", "--device_config", type=str, required=True,
        help="Path to device configuration yaml file.",
    )
    parser.add_argument("-p", "--sessions_folder", type=str, default=os.path.join(Path.home(), "nexus-console"),
        help="Directory to store all the acquisition data acquired during the session.",
    )
    args = parser.parse_args()
    input("\n[neXus] Before starting the setup, confirm that all the amplifiers are turned off.\nPress Enter to continue...")
    print("\n[neXus] Setting up the acquisition control...\n")

    # Create global instance
    # global acq
    app.state.acq = AcquisitionControl(
    # acq = AcquisitionControl(
        configuration_file=args.device_config,
        nexus_data_dir=args.sessions_folder,
    )
    input("\n[neXus] Setup completed, hardware components can be turned on.\nPress Enter to continue...")
    # print("\n[neXus] Test:: Acquisition control instance: ", acq)
    print("\n[neXus] Test:: Acquisition control instance: ", app.state.acq)


    yield
    # Delete acquisition control instance at the end of the lifespan
    # del acq
    del app.state.acq


# app = FastAPI(lifespan=lifespan)
app = FastAPI()

# Shared state
job_queue: dict[str, Job] = {}
lock = threading.Lock()
acq_lock = asyncio.Lock()
# acq: AcquisitionControl | None = None


@app.post("/test", tags=["acquisition"])
async def test_scan():
    lock.acquire()
    acq = AcquisitionControl(configuration_file="/home/schote01/code/spectrum-console-experiments/device_config_ptb.yaml")
    acq.set_sequence("/home/schote01/code/spectrum-console-experiments/service/2d_tse.seq")
    print("[neXus] Set sequence. Starting acquisition...")
    acq_data: AcquisitionData = acq.run()
    print("[neXus] Job completed, saving data...")
    acq_data_path = acq_data.save(save_unprocessed=acq.save_unprocessed)
    print("[neXus] Job done.")
    print("[neXus] ", acq_data_path)
    del acq
    lock.release()
    
    

@app.post("/request_scan", tags=["acquisition"])
# async def start_acquisition(request: ScanRequest):
async def start_acquisition(request: ScanRequest):
    # Create new job id
    job_id = str(uuid.uuid4())
    
    # # Read and set sequence
    # if seq := pp.Sequence(acq.seq_provider.system):
    #     seq.read(request.sequence)
    #     # print(seq)
    # if not seq:
    #     return
   
    event = asyncio.Event()
    # with lock:
    #     job_queue[job_id] = Job(request=request, event=event)

    # def run_acquisition():
    #     with lock:
    #         global acq
    #         acq.set_sequence(request.sequence)
    #         job_queue[job_id].status = "running"
    #         acq_data: AcquisitionData = acq.run()
    #         print("[neXus] Job completed, saving data...")
    #         acq_data_path = acq_data.save(save_unprocessed=acq.save_unprocessed)
    #         # job_queue[job_id]["status"] = "completed" if not control._stop_requested else "stopped"
    #         job_queue[job_id].status = "completed"
    #         job_queue[job_id].result = acq_data_path
    #         print("[neXus] Job done.")
    #     event.set()
    async with acq_lock:
        job_queue[job_id] = Job(request=request, event=event)
        acq = app.state.acq
        # global acq
        acq.set_sequence(request.sequence)
        job_queue[job_id].status = "running"
        acq_data: AcquisitionData = acq.run()
        print("[neXus] Job completed, saving data...")
        acq_data_path = acq_data.save(save_unprocessed=acq.save_unprocessed)
        # job_queue[job_id]["status"] = "completed" if not control._stop_requested else "stopped"
        job_queue[job_id].status = "completed"
        job_queue[job_id].result = acq_data_path
        print("[neXus] Job done.")

    # event.set()

    # thread = threading.Thread(target=run_acquisition)
    # thread.start()
    return JSONResponse({"job_id": job_id})

@app.get("/jobs", tags=["acquisition"])
async def get_jobs():
    with lock:
        return {jid: job.status for jid, job in job_queue.items()}

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    with lock:
        if job_id not in job_queue:
            await websocket.send_json({"error": "Invalid job ID"})
            await websocket.close()
            return
        event = job_queue[job_id].event
    
    while True:
        await event.wait()
        with lock:
            status = job_queue[job_id].status
            event.clear()
        
        await websocket.send_json({"status": status})
        if status in ["completed", "stopped"]:
            break
    
    await websocket.close()

# @app.post("/stop/{job_id}")
# async def stop_acquisition(job_id: str):
#     with jobs_lock:
#         if job_id not in jobs:
#             return {"error": "Invalid job ID"}
#         control.stop_acquisition()
#     return {"status": "stop requested"}

@app.get("/acquisition_parameter", tags=["acquisition"])
def get_acquisition_parameter() -> dict:
    """Return acquisition parameters.

    Returns
    -------
        Dictionary of acquisition parameters.
    """
    print("[neXus] Acquisition parameters: ", console.parameter.dict())
    return console.parameter.dict()

@app.post("/acquisition_parameter", tags=["acquisition"])
def set_acquisition_parameter(params: dict) -> None:
    """Update acquisition parameters.

    Parameters
    ----------
    params
        Dictionary with acquisition parameters to be updated.

    Returns
    -------
        Updated dictionary
    """
    print("[neXus] Acquisition parameters to update: ", params)
    console.parameter.update(params)
    print("[neXus] Updated acquisition parameter: ", console.parameter.dict())
    return console.parameter.dict()

def start_service():
    # Disable reload, because every reload triggers a re-instantiation of the acquisition control
    uvicorn.run("console.service.server:app", host=config.HOST, port=config.PORT, reload=False)

if __name__ == "__main__":
    start_service()
