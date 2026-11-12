import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.device_monitor import DeviceMonitorService
from ..services.hardware_pmu import HardwarePMUService
from ..schemas.schemas import DeviceSpecsResponse, DeviceLiveResponse, HardwarePMUResponse

router = APIRouter(prefix="/api/device", tags=["Device Monitor"])

# In-memory history buffer (last 60 seconds)
history_buffer = []

@router.get("/specifications", response_model=DeviceSpecsResponse)
def get_specifications():
    return DeviceMonitorService.get_specifications()

@router.get("/live", response_model=DeviceLiveResponse)
def get_live():
    metrics = DeviceMonitorService.get_live_metrics()
    history_buffer.append(metrics)
    if len(history_buffer) > 60:
        history_buffer.pop(0)
    return metrics

@router.get("/history")
def get_history():
    return {"history": history_buffer}

@router.get("/processes")
def get_processes(limit: int = 20):
    return {"processes": DeviceMonitorService.get_top_processes(limit=limit)}

@router.get("/pmu", response_model=HardwarePMUResponse)
def get_hardware_pmu():
    """
    Returns PMU-style metrics (L3 miss rate, branch mispredictions, IPC, instruction
    retirement) ESTIMATED from live OS activity counters via psutil. These are heuristic
    estimates, not reads of the CPU's hardware performance counters.
    """
    return HardwarePMUService.get_live_pmu()

@router.websocket("/ws")
async def websocket_device_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            metrics = DeviceMonitorService.get_live_metrics()
            history_buffer.append(metrics)
            if len(history_buffer) > 60:
                history_buffer.pop(0)
            await websocket.send_json(metrics)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()

