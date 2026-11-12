"""
Heuristic Microarchitectural Bottleneck Analyzer Service.
Decomposes execution stalls into Top-Down (TMAM Level-1 style) categories. The inputs
are user-supplied or estimated rates, so the output is a model, not a hardware measurement:
1. Retiring: fraction of pipeline issue slots processing useful instructions
2. Bad Speculation: slots wasted due to branch mispredictions and recovery flushes
3. Frontend Bound: slots starved because fetch/decode cannot deliver uops
4. Backend Bound: slots stalled due to memory hierarchy latency and execution port contention
"""
from typing import Dict, Any, List, Optional

from . import arch_model

class BottleneckAnalyzerService:

    @staticmethod
    def analyze(cpi: float = 2.47,
                llc_miss_rate: float = 28.4,
                branch_mispredict_rate: float = 8.0,
                pipeline_stall_pct: float = 18.0,
                dram_latency_ns: float = 68.0,
                instruction_count: float = 10000.0,
                frequency_ghz: float = 3.0,
                issue_width: Optional[int] = None) -> dict:
        
        # Validation
        if cpi <= 0:
            cpi = 1.0
        if instruction_count <= 0:
            instruction_count = 10000.0
        if frequency_ghz <= 0:
            frequency_ghz = 3.0

        # Total clock cycles = IC * CPI
        total_cycles = instruction_count * cpi

        # 1. DRAM latency in clock cycles: latency_ns * freq_ghz
        dram_latency_cycles = max(1.0, dram_latency_ns * frequency_ghz)

        # 2. Memory subsystem penalty (instruction mix shared via arch_model)
        mem_inst_count = instruction_count * arch_model.MEM_ACCESS_RATIO
        memory_penalty_cycles = int(mem_inst_count * (llc_miss_rate / 100.0) * (dram_latency_cycles * 0.08))

        # 3. Branch misprediction penalty (mix and flush cost shared via arch_model)
        branch_inst_count = instruction_count * arch_model.BRANCH_RATIO
        branch_flush_penalty = arch_model.BRANCH_FLUSH_PENALTY_CYCLES
        branch_penalty_cycles = int(branch_inst_count * (branch_mispredict_rate / 100.0) * branch_flush_penalty)

        # 4. Pipeline dependency and hazard penalty:
        pipeline_penalty_cycles = int(total_cycles * (pipeline_stall_pct / 100.0) * 0.4)

        # 5. Structural / execution port contention:
        # Port saturation on arithmetic and vector units
        structural_penalty_cycles = max(15, int(instruction_count * arch_model.INSTRUCTION_MIX["ALU"] * 0.06 * (cpi / 1.5)))

        total_penalty = memory_penalty_cycles + pipeline_penalty_cycles + branch_penalty_cycles + structural_penalty_cycles
        if total_penalty <= 0:
            total_penalty = 1

        mem_contrib = (memory_penalty_cycles / total_penalty) * 100.0
        pipe_contrib = (pipeline_penalty_cycles / total_penalty) * 100.0
        branch_contrib = (branch_penalty_cycles / total_penalty) * 100.0
        struct_contrib = (structural_penalty_cycles / total_penalty) * 100.0

        # Bottleneck score: relative overhead above ideal single-cycle execution
        # Formally: (CPI - 1.0) / CPI * 100% weighted with memory & branch contention
        cpi_overhead_pct = ((cpi - 1.0) / cpi) * 100.0 if cpi > 1.0 else 0.0
        composite_score = (cpi_overhead_pct * 0.60) + (llc_miss_rate * 0.25) + (branch_mispredict_rate * 0.15)
        score = min(100.0, max(5.0, round(composite_score, 1)))

        if score < 25.0:
            severity = "Low"
            risk_level = "Nominal Execution"
        elif score < 50.0:
            severity = "Medium"
            risk_level = "Moderate Contention"
        elif score < 75.0:
            severity = "High"
            risk_level = "High Risk"
        else:
            severity = "Critical"
            risk_level = "Severe Bottleneck"

        items = [
            {
                "name": "Memory Subsystem Bottleneck",
                "subsystem": "L3 Cache / DRAM",
                "description": f"High cache miss rate ({llc_miss_rate:.1f}% LLC misses) stalling execution units.",
                "penalty_cycles": memory_penalty_cycles,
                "impact_cycles": memory_penalty_cycles,
                "impact_pct": round(mem_contrib, 1),
                "severity": "High" if llc_miss_rate > 20.0 else "Medium",
                "cause": "Inefficient spatial/temporal cache locality and stride-heavy data access patterns.",
                "suggestion": "Implement cache blocking/tiling, struct-of-arrays (SoA) memory layout, and compiler prefetch intrinsics (_mm_prefetch)."
            },
            {
                "name": "Pipeline Stalls & Starvation",
                "subsystem": "Reservation Stations / ROB",
                "description": f"{pipeline_stall_pct:.1f}% of clock cycles starved due to RAW register dependencies.",
                "penalty_cycles": pipeline_penalty_cycles,
                "impact_cycles": pipeline_penalty_cycles,
                "impact_pct": round(pipe_contrib, 1),
                "severity": "High" if pipeline_stall_pct >= 25.0 else ("Medium" if pipeline_stall_pct >= 15.0 else "Low"),
                "cause": "Long dependency chains in inner loop compute blocks and load-use delays.",
                "suggestion": "Unroll loops to interleave independent instructions; utilize register renaming and software pipelining."
            },
            {
                "name": "Branch Misprediction Penalties",
                "subsystem": "Branch Target Buffer (BTB)",
                "description": f"Branch mispredict rate at {branch_mispredict_rate:.1f}% causing frequent {branch_flush_penalty:.0f}-cycle pipeline flushes.",
                "penalty_cycles": branch_penalty_cycles,
                "impact_cycles": branch_penalty_cycles,
                "impact_pct": round(branch_contrib, 1),
                "severity": "High" if branch_mispredict_rate >= 10.0 else ("Medium" if branch_mispredict_rate >= 5.0 else "Low"),
                "cause": "High-entropy branch instructions with unpredictable input data distribution.",
                "suggestion": "Convert branches to conditional moves (CMOV), predicated execution, or lookup table dispatching."
            },
            {
                "name": "Structural ALU Port Contention",
                "subsystem": "Execution Ports 0/1/5",
                "description": "Port saturation on floating-point/vector units during dense calculation.",
                "penalty_cycles": structural_penalty_cycles,
                "impact_cycles": structural_penalty_cycles,
                "impact_pct": round(struct_contrib, 1),
                "severity": "Low" if structural_penalty_cycles < 80 else "Medium",
                "cause": "Imbalanced instruction mix overburdening primary integer and multiplier ports.",
                "suggestion": "Balance arithmetic workloads across independent execution units and exploit AVX-512 FMA vector pipelines."
            }
        ]

        # Determine primary culprit
        sorted_items = sorted(items, key=lambda x: x["impact_pct"], reverse=True)
        top = sorted_items[0]
        primary_culprit = f"Primary culprit: {top['name']} ({top['impact_pct']}% of stall cycles)."

        # Top-Down Microarchitecture Decomposition (TMAM Level-1 style, after Ahmad Yasin):
        # total pipeline issue slots = cycles * issue_width, so
        # Retiring fraction = IPC / issue_width = 1.0 / (CPI * issue_width).
        # Issue width is a property of the machine, so it is never inferred from CPI
        # (inferring it makes Retiring jump discontinuously as CPI crosses 1.0).
        # It defaults to 1 (the scalar textbook pipeline); callers modeling a superscalar
        # core pass issue_width explicitly.
        ipc = 1.0 / cpi if cpi > 0 else 1.0
        effective_width = float(issue_width) if issue_width is not None and issue_width > 0 else 1.0
        ipc_exceeds_width = ipc > effective_width

        retiring_pct = round(max(5.0, min(95.0, (ipc / effective_width) * 100.0)), 1)
        overhead_slots = round(100.0 - retiring_pct, 1)

        # Dynamic Frontend Bound calculation:
        # Reflects instruction fetch latency (I-Cache misses and ITLB misses correlated with LLC miss rate),
        # branch target buffer (BTB) fetch-bubble penalties from branch misprediction recovery,
        # and instruction decode starvation during pipeline dependency stalls.
        frontend_weight = (
            0.06 +
            (branch_mispredict_rate / 100.0) * 0.45 +
            (llc_miss_rate / 100.0) * 0.25 +
            (pipeline_stall_pct / 100.0) * 0.15
        )
        frontend_weight = max(0.05, min(0.40, frontend_weight))
        frontend_raw = overhead_slots * frontend_weight

        bad_spec_raw = overhead_slots * max(0.05, branch_contrib / 100.0)
        backend_raw = overhead_slots * max(0.10, (mem_contrib + struct_contrib + (pipe_contrib * 0.5)) / 100.0)

        # Normalize remaining slots so that:
        # retiring + bad_speculation + frontend_bound + backend_bound == 100.0% exactly!
        rem_sum = bad_spec_raw + frontend_raw + backend_raw
        if rem_sum <= 0:
            rem_sum = 1.0

        bad_spec_pct = round((bad_spec_raw / rem_sum) * overhead_slots, 1)
        frontend_pct = round((frontend_raw / rem_sum) * overhead_slots, 1)
        backend_pct = round(overhead_slots - bad_spec_pct - frontend_pct, 1)

        tma_levels = {
            "retiring": retiring_pct,
            "bad_speculation": bad_spec_pct,
            "frontend_bound": frontend_pct,
            "backend_bound": backend_pct,
            "total_loss": round(overhead_slots, 1)
        }

        distribution = {
            "Memory": round(mem_contrib, 1),
            "Pipeline": round(pipe_contrib, 1),
            "Branch": round(branch_contrib, 1),
            "Structural": round(struct_contrib, 1)
        }

        formula_explanation = "Bottleneck Score = (CPI Overhead × 60%) + (LLC Miss Rate × 25%) + (Branch Mispredict Rate × 15%)"
        if ipc_exceeds_width:
            formula_explanation += (
                f". IPC ({ipc:.2f}) exceeds the assumed issue width ({effective_width:.0f}), "
                "so Retiring is capped; pass issue_width to model a superscalar core."
            )

        return {
            "bottleneck_score": score,
            "severity": severity,
            "risk_level": risk_level,
            "primary_culprit": primary_culprit,
            "summary_message": f"Hardware audit diagnosed {severity} severity microarchitectural contention. {primary_culprit}",
            "items": items,
            "distribution": distribution,
            "tma_levels": tma_levels,
            "issue_width_used": effective_width,
            "formula_explanation": formula_explanation,
            "subsystem_weights": {
                "cpi_overhead_weight": 0.60,
                "llc_miss_weight": 0.25,
                "branch_mispredict_weight": 0.15
            }
        }
