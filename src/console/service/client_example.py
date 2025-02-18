# client.py
import websockets
import asyncio
import requests

async def monitor_job(job_id):
    async with websockets.connect(f"ws://localhost:8000/ws/{job_id}") as websocket:
        while True:
            response = await websocket.recv()
            print(f"Job {job_id} status: {response}")
            if "completed" in response or "stopped" in response:
                break

def start_acquisition():
    response = requests.post(
        "http://localhost:8000/start",
        json={"sequence": {"param1": "value1"}}  # Add actual parameters
    )
    job_id = response.json()["job_id"]
    print(f"Started acquisition with ID: {job_id}")
    asyncio.run(monitor_job(job_id))

if __name__ == "__main__":
    start_acquisition()