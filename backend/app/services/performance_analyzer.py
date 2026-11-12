"""
Computer Organization and Architecture (COA) Performance Analyzer Service.
Provides mathematically exact calculations for Single CPU and Instruction Set Analysis
based on the Iron Law of Processor Performance:
T_exec = (IC * CPI) / f = IC * CPI * tau
IPC = 1 / CPI
MIPS = f_MHz / CPI = IC / (T_exec * 10^6)
"""
from typing import Dict, Any

from . import arch_model

def format_time(seconds: float) -> str:
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f} ns"
    elif seconds < 1e-3:
        return f"{seconds * 1e6:.2f} µs"
    elif seconds < 1.0:
        return f"{seconds * 1e3:.2f} ms"
    else:
        return f"{seconds:.2f} s"


class PerformanceAnalyzerService:

    BASELINE_CPI = 2.81
    BASELINE_IPC = 1.0 / 2.81  # ~0.356
    BASELINE_FREQ_GHZ = 3.0

    @classmethod
    def calculate_single(cls,
                         instruction_count: float,
                         cycles: float,
                         frequency: float,
                         unit: str = "1e9") -> Dict[str, Any]:
        # Validate inputs
        if instruction_count <= 0:
            raise ValueError("Instruction count (IC) must be strictly positive (> 0)")
        if cycles <= 0:
            raise ValueError("Clock cycles must be strictly positive (> 0)")
        if frequency <= 0:
            raise ValueError("Clock frequency must be strictly positive (> 0)")

        try:
            freq_multiplier = float(unit)
        except (ValueError, TypeError):
            freq_multiplier = 1e9

        freq_hz = frequency * freq_multiplier
        freq_ghz = freq_hz / 1e9
        freq_mhz = freq_hz / 1e6

        # Iron Law Core Formulas
        # CPI = Total Clock Cycles / Total Instructions
        cpi = cycles / instruction_count

        # IPC = Total Instructions / Total Clock Cycles = 1 / CPI
        ipc = instruction_count / cycles

        # Clock Period tau = 1 / f
        cycle_time_sec = 1.0 / freq_hz
        cycle_time_ns = cycle_time_sec * 1e9

        # Execution Time T = (IC * CPI) / f = Cycles / f
        execution_time_sec = (instruction_count * cpi) / freq_hz
        execution_time_ms = execution_time_sec * 1000.0

        # MIPS = IC / (Execution Time in sec * 10^6) = f_MHz / CPI
        mips = freq_mhz / cpi

        # Mathematical comparisons against standard architectural reference baseline
        # (Reference Core: 3.0 GHz, CPI = 2.81, IPC = 0.356)
        baseline_time_sec = (instruction_count * cls.BASELINE_CPI) / (cls.BASELINE_FREQ_GHZ * 1e9)
        baseline_time_ms = baseline_time_sec * 1000.0
        baseline_mips = (cls.BASELINE_FREQ_GHZ * 1000.0) / cls.BASELINE_CPI

        trend_cpi = round(((cpi - cls.BASELINE_CPI) / cls.BASELINE_CPI) * 100.0, 1)
        trend_ipc = round(((ipc - cls.BASELINE_IPC) / cls.BASELINE_IPC) * 100.0, 1)
        trend_exectime = round(((execution_time_ms - baseline_time_ms) / baseline_time_ms) * 100.0, 1)
        trend_mips = round(((mips - baseline_mips) / baseline_mips) * 100.0, 1)

        # 5-Stage RISC Stage Modeling (IF, ID, EX, MEM, WB)
        # Based on canonical RISC-V / MIPS workload profile:
        # ALU instructions dominate execution stage (EX), load/stores dominate MEM,
        # all instructions cycle through fetch (IF), decode (ID), and retire (WB).
        stage_if = round(cycles * 0.12)
        stage_id = round(cycles * 0.10)
        stage_ex = round(cycles * 0.38)
        stage_mem = round(cycles * 0.28)
        stage_wb = round(cycles * 0.12)

        stage_breakdown = {
            "IF": {"pct": 12.0, "cycles": stage_if, "desc": "Instruction Fetch"},
            "ID": {"pct": 10.0, "cycles": stage_id, "desc": "Instruction Decode"},
            "EX": {"pct": 38.0, "cycles": stage_ex, "desc": "Execute / ALU"},
            "MEM": {"pct": 28.0, "cycles": stage_mem, "desc": "Memory Access"},
            "WB": {"pct": 12.0, "cycles": stage_wb, "desc": "Write Back"},
            "modeling_assumption": "Modeled using canonical 5-stage RISC instruction distribution"
        }

        # Workload composition breakdown
        mix = arch_model.INSTRUCTION_MIX
        instruction_distribution = {
            "ALU": {"count": round(instruction_count * mix["ALU"]), "pct": round(mix["ALU"] * 100.0, 1), "color": "#006b2c"},
            "Memory": {"count": round(instruction_count * mix["Memory"]), "pct": round(mix["Memory"] * 100.0, 1), "color": "#0051d5"},
            "Branch": {"count": round(instruction_count * mix["Branch"]), "pct": round(mix["Branch"] * 100.0, 1), "color": "#6b38d4"},
            "Others": {"count": round(instruction_count * mix["Other"]), "pct": round(mix["Other"] * 100.0, 1), "color": "#bdcaba"},
        }

        return {
            "instruction_count": instruction_count,
            "cycles": cycles,
            "frequency_ghz": round(freq_ghz, 2),
            "cycle_time_ns": round(cycle_time_ns, 3),
            "cpi": round(cpi, 2),
            "ipc": round(ipc, 2),
            "execution_time_ms": round(execution_time_ms, 4),
            "execution_time_formatted": format_time(execution_time_sec),
            "mips": round(mips, 1),
            "trend_cpi": trend_cpi,
            "trend_ipc": trend_ipc,
            "trend_exectime": trend_exectime,
            "trend_mips": trend_mips,
            "stage_breakdown": stage_breakdown,
            "instruction_distribution": instruction_distribution
        }

    @classmethod
    def calculate_instruction_set(cls,
                                  alu_count: float, alu_cpi: float,
                                  mem_count: float, mem_cpi: float,
                                  branch_count: float, branch_cpi: float,
                                  other_count: float, other_cpi: float,
                                  frequency: float, unit: str = "1e9") -> Dict[str, Any]:
        # Validate counts are non-negative
        if alu_count < 0 or mem_count < 0 or branch_count < 0 or other_count < 0:
            raise ValueError("Instruction counts cannot be negative")

        total_instructions = alu_count + mem_count + branch_count + other_count
        if total_instructions <= 0:
            raise ValueError("Total instruction count across all categories must be strictly positive (> 0)")

        # Validate CPIs for active categories
        if (alu_count > 0 and alu_cpi <= 0) or \
           (mem_count > 0 and mem_cpi <= 0) or \
           (branch_count > 0 and branch_cpi <= 0) or \
           (other_count > 0 and other_cpi <= 0):
            raise ValueError("CPI for instruction categories with non-zero count must be strictly positive (> 0)")

        if frequency <= 0:
            raise ValueError("Clock frequency must be strictly positive (> 0)")

        try:
            freq_multiplier = float(unit)
        except (ValueError, TypeError):
            freq_multiplier = 1e9

        freq_hz = frequency * freq_multiplier
        freq_ghz = freq_hz / 1e9
        freq_mhz = freq_hz / 1e6

        # Category Cycles = Count_i * CPI_i
        cycles_alu = alu_count * alu_cpi
        cycles_mem = mem_count * mem_cpi
        cycles_branch = branch_count * branch_cpi
        cycles_other = other_count * other_cpi
        total_cycles = cycles_alu + cycles_mem + cycles_branch + cycles_other

        # Weighted CPI = Total Clock Cycles / Total Instructions
        weighted_cpi = total_cycles / total_instructions
        ipc = 1.0 / weighted_cpi if weighted_cpi > 0 else 0.0

        # Clock Period tau
        cycle_time_sec = 1.0 / freq_hz
        cycle_time_ns = cycle_time_sec * 1e9

        # Execution Time T = (Total Instructions * Weighted CPI) / Frequency = Total Cycles / Frequency
        execution_time_sec = total_cycles / freq_hz
        execution_time_ms = execution_time_sec * 1000.0

        # MIPS = f_MHz / Weighted CPI = Total Instructions / (Execution Time * 10^6)
        mips = freq_mhz / weighted_cpi if weighted_cpi > 0 else 0.0

        category_pcts = {
            "ALU": round((alu_count / total_instructions) * 100.0, 1),
            "Memory": round((mem_count / total_instructions) * 100.0, 1),
            "Branch": round((branch_count / total_instructions) * 100.0, 1),
            "Other": round((other_count / total_instructions) * 100.0, 1)
        }

        # 5-Stage RISC Cycle Breakdown derived from real instruction workloads:
        # In classic 5-stage:
        # - IF & ID & WB: 1 cycle per instruction retired = total_instructions cycles each
        # - EX: execution cycles for ALU and Branch instructions = cycles_alu + cycles_branch
        # - MEM: memory access cycles for Load/Store instructions = cycles_mem
        # Normalize stages proportionally to match total elapsed clock cycles:
        raw_stage_cycles = {
            "IF": total_instructions,
            "ID": total_instructions,
            "EX": cycles_alu + cycles_branch + (cycles_other * 0.5),
            "MEM": cycles_mem + (cycles_other * 0.5),
            "WB": total_instructions
        }
        raw_sum = sum(raw_stage_cycles.values())
        if raw_sum <= 0:
            raw_sum = 1.0

        stage_breakdown = {
            "IF": {
                "pct": round((raw_stage_cycles["IF"] / raw_sum) * 100.0, 1),
                "cycles": round((raw_stage_cycles["IF"] / raw_sum) * total_cycles),
                "desc": "Instruction Fetch"
            },
            "ID": {
                "pct": round((raw_stage_cycles["ID"] / raw_sum) * 100.0, 1),
                "cycles": round((raw_stage_cycles["ID"] / raw_sum) * total_cycles),
                "desc": "Instruction Decode"
            },
            "EX": {
                "pct": round((raw_stage_cycles["EX"] / raw_sum) * 100.0, 1),
                "cycles": round((raw_stage_cycles["EX"] / raw_sum) * total_cycles),
                "desc": "Execute / ALU & Branch"
            },
            "MEM": {
                "pct": round((raw_stage_cycles["MEM"] / raw_sum) * 100.0, 1),
                "cycles": round((raw_stage_cycles["MEM"] / raw_sum) * total_cycles),
                "desc": "Memory Access (Load/Store)"
            },
            "WB": {
                "pct": round((raw_stage_cycles["WB"] / raw_sum) * 100.0, 1),
                "cycles": round((raw_stage_cycles["WB"] / raw_sum) * total_cycles),
                "desc": "Write Back"
            },
            "modeling_assumption": "Derived from explicit instruction class counts and individual category CPIs"
        }

        instruction_distribution = {
            "ALU": {"count": alu_count, "pct": category_pcts["ALU"], "color": "#006b2c"},
            "Memory": {"count": mem_count, "pct": category_pcts["Memory"], "color": "#0051d5"},
            "Branch": {"count": branch_count, "pct": category_pcts["Branch"], "color": "#6b38d4"},
            "Others": {"count": other_count, "pct": category_pcts["Other"], "color": "#bdcaba"},
        }

        # Trend relative to baseline
        baseline_time_sec = (total_instructions * cls.BASELINE_CPI) / (cls.BASELINE_FREQ_GHZ * 1e9)
        baseline_time_ms = baseline_time_sec * 1000.0
        baseline_mips = (cls.BASELINE_FREQ_GHZ * 1000.0) / cls.BASELINE_CPI

        trend_cpi = round(((weighted_cpi - cls.BASELINE_CPI) / cls.BASELINE_CPI) * 100.0, 1)
        trend_ipc = round(((ipc - cls.BASELINE_IPC) / cls.BASELINE_IPC) * 100.0, 1)
        trend_exectime = round(((execution_time_ms - baseline_time_ms) / baseline_time_ms) * 100.0, 1)
        trend_mips = round(((mips - baseline_mips) / baseline_mips) * 100.0, 1)

        return {
            "total_instructions": total_instructions,
            "total_cycles": total_cycles,
            "weighted_cpi": round(weighted_cpi, 2),
            "cpi": round(weighted_cpi, 2),
            "ipc": round(ipc, 2),
            "frequency_ghz": round(freq_ghz, 2),
            "cycle_time_ns": round(cycle_time_ns, 3),
            "execution_time_ms": round(execution_time_ms, 4),
            "execution_time_formatted": format_time(execution_time_sec),
            "mips": round(mips, 1),
            "trend_cpi": trend_cpi,
            "trend_ipc": trend_ipc,
            "trend_exectime": trend_exectime,
            "trend_mips": trend_mips,
            "category_percentages": category_pcts,
            "stage_breakdown": stage_breakdown,
            "instruction_distribution": instruction_distribution
        }
