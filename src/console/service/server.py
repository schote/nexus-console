# server.py
import uuid
import threading
import asyncio
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

class AcquisitionParameters(BaseModel):
    sequence: dict  # Define your actual parameters here

class AcquisitionControl:
    def __init__(self):
        self._running = False
        self._stop_requested = False

    def set_sequence(self, parameters: dict):
        # Implement actual sequence setup
        pass

    def start_acquisition(self):
        self._running = True
        self._stop_requested = False
        # Simulate acquisition process
        import time
        for i in range(1, 101):
            if self._stop_requested:
                break
            time.sleep(0.1)  # Simulate work
        self._running = False

    def stop_acquisition(self):
        self._stop_requested = True

    @property
    def status(self):
        return "running" if self._running else "stopped"

# Shared state
jobs = {}
jobs_lock = threading.Lock()
job_events = {}
control = AcquisitionControl()

@app.post("/start")
async def start_acquisition(params: AcquisitionParameters):
    job_id = str(uuid.uuid4())
    control.set_sequence(params.sequence)
    
    event = asyncio.Event()
    with jobs_lock:
        jobs[job_id] = {"status": "starting", "event": event}
        job_events[job_id] = event

    def run_acquisition():
        with jobs_lock:
            jobs[job_id]["status"] = "running"
            control.start_acquisition()
            jobs[job_id]["status"] = "completed" if not control._stop_requested else "stopped"
        event.set()

    thread = threading.Thread(target=run_acquisition)
    thread.start()
    
    return JSONResponse({"job_id": job_id})

@app.get("/jobs")
async def get_jobs():
    with jobs_lock:
        return {jid: job["status"] for jid, job in jobs.items()}

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    with jobs_lock:
        if job_id not in jobs:
            await websocket.send_json({"error": "Invalid job ID"})
            await websocket.close()
            return
        event = job_events[job_id]
    
    while True:
        await event.wait()
        with jobs_lock:
            status = jobs[job_id]["status"]
            event.clear()
        
        await websocket.send_json({"status": status})
        if status in ["completed", "stopped"]:
            break
    
    await websocket.close()

@app.post("/stop/{job_id}")
async def stop_acquisition(job_id: str):
    with jobs_lock:
        if job_id not in jobs:
            return {"error": "Invalid job ID"}
        control.stop_acquisition()
    return {"status": "stop requested"}
