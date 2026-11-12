"""
Single source of truth for the architectural assumptions used across the tool.

Every analysis page (Performance Analyzer, Bottleneck Analyzer, What-If) models the
same canonical workload, so they all read these values instead of keeping private copies.
These are modeling assumptions, not measurements.
"""

# Canonical instruction mix (fractions of the dynamic instruction stream; sums to 1.0).
INSTRUCTION_MIX = {"ALU": 0.42, "Memory": 0.28, "Branch": 0.12, "Other": 0.18}

MEM_ACCESS_RATIO = INSTRUCTION_MIX["Memory"]
BRANCH_RATIO = INSTRUCTION_MIX["Branch"]

# Cycles lost refilling the pipeline after one mispredicted branch.
BRANCH_FLUSH_PENALTY_CYCLES = 16.0

# Assumed average stall, in cycles, per cache miss in the What-If model.
CACHE_MISS_PENALTY_CYCLES = 48.0
