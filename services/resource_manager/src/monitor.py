"""System resource monitoring — CPU, RAM, disk, GPU detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psutil
import structlog

logger = structlog.get_logger()


@dataclass
class SystemResources:
    cpu_percent: float
    cpu_count: int
    memory_total_mb: int
    memory_available_mb: int
    memory_percent: float
    disk_total_gb: float
    disk_free_gb: float
    disk_percent: float
    gpu_available: bool = False
    gpu_info: list[dict[str, Any]] | None = None


class ResourceMonitor:
    """Monitors system resources for robot scheduling decisions."""

    def snapshot(self) -> SystemResources:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return SystemResources(
            cpu_percent=cpu,
            cpu_count=psutil.cpu_count() or 1,
            memory_total_mb=int(mem.total / (1024 * 1024)),
            memory_available_mb=int(mem.available / (1024 * 1024)),
            memory_percent=mem.percent,
            disk_total_gb=round(disk.total / (1024**3), 1),
            disk_free_gb=round(disk.free / (1024**3), 1),
            disk_percent=disk.percent,
            gpu_available=self._detect_gpu(),
            gpu_info=self._gpu_info(),
        )

    def can_run_robot(self, min_memory_mb: int = 512, max_cpu_percent: float = 90.0) -> bool:
        snap = self.snapshot()
        return snap.memory_available_mb >= min_memory_mb and snap.cpu_percent < max_cpu_percent

    def _detect_gpu(self) -> bool:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def _gpu_info(self) -> list[dict[str, Any]] | None:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
            gpus = []
            for line in result.stdout.strip().split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    gpus.append({
                        "name": parts[0],
                        "memory_total_mb": int(parts[1]),
                        "memory_free_mb": int(parts[2]),
                        "utilization_percent": int(parts[3]),
                    })
            return gpus or None
        except Exception:
            return None
