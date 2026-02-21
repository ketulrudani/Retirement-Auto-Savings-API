"""Performance endpoint: time, memory, threads."""

import threading
import time

import psutil
from fastapi import APIRouter, Request

from app.schemas import PerformanceResponse

router = APIRouter()


@router.get("/performance", response_model=PerformanceResponse)
def performance(request: Request) -> PerformanceResponse:
    """Report response time (from request state), memory (process), and thread count."""
    start = getattr(request.state, "start_time", None)
    if start is not None:
        duration_ms = (time.perf_counter() - start) * 1000
        total_sec = duration_ms / 1000
        h = int(total_sec // 3600)
        m = int((total_sec % 3600) // 60)
        s = total_sec % 60
        time_str = f"{h:02d}:{m:02d}:{s:06.3f}"
    else:
        time_str = "00:00:00.000"

    process = psutil.Process()
    mem_mb = process.memory_info().rss / (1024 * 1024)
    memory_str = f"{mem_mb:.2f} MB"
    threads = threading.active_count()

    return PerformanceResponse(time=time_str, memory=memory_str, threads=threads)
