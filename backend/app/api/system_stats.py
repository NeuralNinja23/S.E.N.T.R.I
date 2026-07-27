"""Real system telemetry endpoint using psutil + nvidia-smi."""

import time
import threading
import psutil
import subprocess
import platform
from fastapi import APIRouter

router = APIRouter()

_boot_time = psutil.boot_time()
_last_net = psutil.net_io_counters()
_last_net_time = time.time()
_net_lock = threading.Lock()  # Bug #28: prevent race condition under concurrent polls


def _get_gpu_stats() -> dict:
    """Get GPU utilization, VRAM usage, and temperature via nvidia-smi (Windows/Linux)."""
    try:
        result = subprocess.run(
            "nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits",
            capture_output=True,
            text=True,
            shell=True,
            timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            gpu_util = float(parts[0].strip())
            gpu_temp = float(parts[1].strip())
            vram_used = float(parts[2].strip())
            vram_total = float(parts[3].strip())
            vram_pct = round((vram_used / vram_total) * 100.0, 1) if vram_total > 0 else 0.0
            return {
                "gpu_percent": gpu_util,
                "gpu_temp": gpu_temp,
                "vram_used_mb": vram_used,
                "vram_total_mb": vram_total,
                "vram_percent": vram_pct,
            }
    except Exception:
        pass
    return {"gpu_percent": 0, "gpu_temp": 0, "vram_used_mb": 0, "vram_total_mb": 0, "vram_percent": 0}



def _get_net_speed() -> dict:
    """Calculate network speed in bytes/sec since last call."""
    global _last_net, _last_net_time
    with _net_lock:  # Bug #28: serialize concurrent callers to prevent state pollution
        now = time.time()
        current = psutil.net_io_counters()
        dt = now - _last_net_time
        if dt < 0.1:
            dt = 1  # Avoid division by zero on first call

        send_speed = (current.bytes_sent - _last_net.bytes_sent) / dt
        recv_speed = (current.bytes_recv - _last_net.bytes_recv) / dt

        _last_net = current
        _last_net_time = now

    return {
        "net_send_bps": round(send_speed),
        "net_recv_bps": round(recv_speed),
    }


@router.get("/api/system-stats")
async def system_stats():
    cpu_percent = psutil.cpu_percent(interval=0)
    mem = psutil.virtual_memory()
    net = _get_net_speed()
    gpu = _get_gpu_stats()
    uptime_seconds = int(time.time() - _boot_time)

    # Try to get CPU temperature (Linux only via psutil; Windows uses nvidia-smi for GPU temp)
    cpu_temp = 0
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Pick the first available sensor
            for name, entries in temps.items():
                if entries:
                    cpu_temp = entries[0].current
                    break
    except Exception:
        pass

    # Disk telemetry (C: on Windows, root on others)
    disk_total = 0
    disk_used = 0
    disk_percent = 0
    try:
        disk_path = "C:\\" if platform.system() == "Windows" else "/"
        disk = psutil.disk_usage(disk_path)
        disk_total = round(disk.total / (1024**3))
        disk_used = round(disk.used / (1024**3))
        disk_percent = round(disk.percent, 1)
    except Exception:
        pass

    import asyncio
    from app.utils.telemetry import telemetry_collector

    return {
        "cpu": round(cpu_percent, 1),
        "mem": round(mem.percent, 1),
        "net_send_bps": net["net_send_bps"],
        "net_recv_bps": net["net_recv_bps"],
        "gpu": round(gpu["gpu_percent"], 1),
        "gpu_temp": round(gpu["gpu_temp"], 1),
        "cpu_temp": round(cpu_temp, 1),
        "processes": len(psutil.pids()),
        "uptime_seconds": uptime_seconds,
        "os": platform.system(),
        "disk_total": disk_total,
        "disk_used": disk_used,
        "disk_percent": disk_percent,
        "active_asyncio_tasks": len(asyncio.all_tasks()),
        "telemetry": telemetry_collector.get_telemetry_dict(),
    }
