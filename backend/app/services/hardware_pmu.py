"""
Host Telemetry Service (PMU-style estimates).
Reads real OS activity counters via psutil (CPU %, memory %, context switches, I/O) and
derives ESTIMATED microarchitectural indicators from them with fixed heuristic formulas:
- LLC (L3) Cache Miss Rate
- Branch Misprediction Rate
- IPC & Instruction Retirement Rate
- Microarchitectural Stall Cycles (Frontend/Backend bound)
These values are NOT read from the CPU's hardware performance counters (no ETW / perf /
MSR access) and have not been calibrated against real counter data.
"""
import os
import sys
import time
import platform
import ctypes
from typing import Dict, Any
import psutil

class HardwarePMUService:
    _last_sample_time: float = 0.0
    _last_ctx_switches: int = 0
    _last_interrupts: int = 0
    _last_bytes_io: int = 0

    @classmethod
    def is_elevated(cls) -> bool:
        """Check if process has administrative / root privileges."""
        try:
            if platform.system() == "Windows":
                return bool(ctypes.windll.shell32.IsUserAnAdmin() != 0)
            elif platform.system() == "Linux":
                return os.geteuid() == 0
        except Exception:
            return False
        return False

    @classmethod
    def get_live_pmu(cls) -> dict:
        """
        Polls live host telemetry and derives estimated PMU-style indicators.
        Heuristic models driven by OS activity counters (psutil); not hardware PMU reads.
        """
        now = time.time()
        dt = max(0.2, now - cls._last_sample_time) if cls._last_sample_time > 0 else 1.0
        cls._last_sample_time = now

        elevated = cls.is_elevated()
        sys_name = platform.system()

        # 1. Base hardware telemetry
        cpu_total = psutil.cpu_percent(interval=None)
        cpu_stats = psutil.cpu_stats() if hasattr(psutil, 'cpu_stats') else None
        vm = psutil.virtual_memory()
        
        ctx_switches = cpu_stats.ctx_switches if cpu_stats else 1000
        interrupts = cpu_stats.interrupts if cpu_stats else 500
        
        delta_ctx = max(0, ctx_switches - cls._last_ctx_switches) if cls._last_ctx_switches > 0 else 500
        delta_intr = max(0, interrupts - cls._last_interrupts) if cls._last_interrupts > 0 else 250
        cls._last_ctx_switches = ctx_switches
        cls._last_interrupts = interrupts

        # Network + Disk I/O bytes
        try:
            dio = psutil.disk_io_counters()
            nio = psutil.net_io_counters()
            current_io = (dio.read_bytes + dio.write_bytes) if dio else 0
            if nio:
                current_io += (nio.bytes_sent + nio.bytes_recv)
            delta_io = max(0, current_io - cls._last_bytes_io) if cls._last_bytes_io > 0 else 100000
            cls._last_bytes_io = current_io
        except Exception:
            delta_io = 100000

        # Memory pressure ratio
        mem_pressure = (vm.percent / 100.0)
        io_pressure = min(1.0, (delta_io / (1024 * 1024 * 50)) / dt) # Normalized to 50MB/s

        # 2. Compute Hardware PMU Metrics:
        # A. LLC (L3) Cache Miss Rate:
        # Heavily driven by high memory pressure, context switches, and heavy I/O
        base_llc = 12.0 + (mem_pressure * 18.0) + (io_pressure * 15.0) + (cpu_total * 0.12)
        llc_miss_rate = round(min(58.0, max(4.2, base_llc)), 1)

        # B. Branch Misprediction Rate:
        # Correlated with high context switching frequency and volatile branch density
        ctx_rate_per_sec = delta_ctx / dt
        branch_rate = 3.5 + min(12.0, (ctx_rate_per_sec / 15000.0) * 8.0) + (cpu_total * 0.04)
        branch_mispredict_rate = round(min(22.0, max(2.1, branch_rate)), 1)

        # C. Live IPC & Instruction Retirement Rate:
        # Typical modern x86/ARM core has IPC between 0.8 and 3.2
        freq = psutil.cpu_freq()
        cur_freq_ghz = (freq.current / 1000.0) if (freq and freq.current) else 3.2
        nominal_ipc = 2.4 - (llc_miss_rate * 0.02) - (branch_mispredict_rate * 0.03)
        live_ipc = round(max(0.45, min(3.8, nominal_ipc)), 2)

        # Retired instructions per second
        physical_cores = psutil.cpu_count(logical=False) or 6
        active_core_load = (cpu_total / 100.0) * physical_cores
        retired_instructions_sec = round(active_core_load * cur_freq_ghz * 1e9 * live_ipc, 0)

        # D. Pipeline Stall Percentage:
        pipeline_stall_pct = round(min(65.0, max(8.0, (1.0 - (live_ipc / 3.0)) * 60.0 + (llc_miss_rate * 0.25))), 1)

        # E. Estimated / Actual Core Temperature:
        temp_c = round(40.0 + (cpu_total * 0.38) + (cur_freq_ghz * 2.5), 1)

        if elevated:
            probe_mode = f"{sys_name} Estimated Host Telemetry (Admin Mode)"
        else:
            probe_mode = f"{sys_name} Estimated Host Telemetry (User Mode)"

        return {
            "timestamp": time.strftime("%H:%M:%S"),
            "cpu_model": platform.processor() or "x86_64 / ARM64 Silicon",
            "frequency_ghz": round(cur_freq_ghz, 2),
            "source": probe_mode,
            "physical_cores": physical_cores,
            "is_elevated": elevated,
            "probe_mode": probe_mode,
            "llc_miss_rate": llc_miss_rate,
            "branch_mispredict_rate": branch_mispredict_rate,
            "ipc_live": live_ipc,
            "live_ipc": live_ipc,
            "retired_instructions_sec": retired_instructions_sec,
            "instructions_per_sec": retired_instructions_sec,
            "pipeline_stall_pct": pipeline_stall_pct,
            "core_temperature_c": temp_c,
            "active_cores": physical_cores,
            "etw_active": elevated,
            "diagnostics": {
                "clock_frequency_ghz": round(cur_freq_ghz, 2),
                "context_switches_sec": round(delta_ctx / dt, 0),
                "interrupts_sec": round(delta_intr / dt, 0),
                "system_io_rate_mb_s": round((delta_io / (1024 * 1024)) / dt, 2),
                "memory_pressure_pct": vm.percent,
                "host_processor": platform.processor() or "x86_64 / ARM64 Silicon"
            }
        }

