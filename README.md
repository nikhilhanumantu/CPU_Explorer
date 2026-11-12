# CPU Performance Explorer
### A CPU Performance Bottleneck Analysis and Visualization Tool

A full-stack, cycle-level computer architecture diagnostics suite built with **HTML5, CSS3, Vanilla JavaScript (ES6+)**, and **Python 3 (FastAPI, psutil, SQLite, SQLAlchemy)**.

---

## 🚀 Key Highlights & Architectural Features

- **No React / No Frontend Frameworks**: Pure vanilla HTML5, CSS3, JavaScript adhering strictly to the Google Stitch design specifications.
- **Visual Fidelity**: Fully preserves the light theme, gradients, typography (*Plus Jakarta Sans*, *Inter*, *JetBrains Mono*), rounded corners, cards, and animations.
- **3D Isometric Glowing CPU**: True multi-planar isometric processor package with neon pulse animations, chrome pins, PCB circuit traces with traveling electron pulses, and 3D mouse parallax tilt.
- **Live Hardware Telemetry**: Low-overhead hardware monitoring powered by `psutil` measuring actual CPU loads, per-core utilization matrix, RAM pools, NVMe I/O throughput, and active compute processes with background daemon caching. The PMU-style indicators on the Bottleneck page (LLC miss rate, branch mispredict rate, IPC) are *estimates* derived from these OS counters, not reads of the CPU's hardware performance counters.
- **Cycle-Level 5-Stage RISC Pipeline** (textbook model; the in-order engine does not model control hazards or multi-cycle execute): Simulates Instruction Fetch (IF), Instruction Decode (ID), Execution (EX), Memory Access (MEM), and Write-Back (WB) with Read-After-Write (RAW) hazard detection, load-use delays, forwarding bypass paths (EX/MEM and MEM/WB), interactive cycle-by-cycle stepper, and real-time STALL cell visualization.
- **Performance Analyzer (Single & ISA Modes)**: Rigorous Iron Law calculation engine supporting both Single CPU and Instruction Set Architecture (weighted CPI) modes with complete input validation (zero and negative protection).
- **TMA-Style Top-Down Bottleneck Analysis (heuristic model)**: Splits issue slots into Retiring, Bad Speculation, Frontend Bound, and Backend Bound (Retiring = IPC / issue width, default width 1) and attributes stall penalties to Memory, Pipeline, Branch, and Structural causes. Inputs are user-supplied or estimated rates, not hardware counter reads, and the penalty weights are documented modeling assumptions.
- **Interactive What-If Sensitivity Explorer**: Dynamic architectural sweeps with live parameter sync, SVG curve decay plots, and SQLite scenario save/load capability.
- **Dual-CPU Comparison Engine**: Head-to-head architectural differential evaluation with clustered metric comparison bars, 5-point radar view, and comprehensive COA metrics tables.
- **Reports & Analytics Hub**: Database persistence via SQLite and SQLAlchemy, with instant exports to **JSON**, **CSV**, and clean styled **PDF print** output without dummy data contamination.

---

## 📐 Computer Organization & Architecture (COA) Formulas

### 1. The Iron Law of Processor Performance
$$\text{CPU Execution Time} = \text{Instruction Count (IC)} \times \text{CPI} \times \text{Clock Cycle Time } (\tau)$$
$$\text{Where } \tau = \frac{1}{\text{Clock Frequency } (f)}$$

### 2. Cycles Per Instruction (CPI) & Instructions Per Cycle (IPC)
$$\text{CPI} = \frac{\text{Total Clock Cycles}}{\text{Instruction Count}}$$
$$\text{IPC} = \frac{1}{\text{CPI}} = \frac{\text{Instruction Count}}{\text{Total Clock Cycles}}$$

### 3. Million Instructions Per Second (MIPS)
$$\text{MIPS} = \frac{\text{Instruction Count}}{\text{Execution Time} \times 10^6} = \frac{\text{Frequency (MHz)}}{\text{CPI}}$$

### 4. Instruction Set Weighted CPI
$$\text{CPI}_{\text{weighted}} = \sum_{i=1}^{n} \left( \frac{\text{Count}_i}{\text{Total Instructions}} \times \text{CPI}_i \right)$$

### 5. Dual CPU Speedup Factor
$$S = \frac{\text{Execution Time}_{\text{Base}}}{\text{Execution Time}_{\text{Target}}}$$
$$\text{Speedup Percentage} = (S - 1) \times 100\%$$

### 6. Pipeline Efficiency
$$\text{Pipeline Efficiency} = \left(\frac{\text{Ideal Clock Cycles}}{\text{Total Measured Cycles}}\right) \times 100\%$$
$$\text{Where } \text{Ideal Cycles} = N + 4 \text{ for an } N\text{-instruction in-order 5-stage RISC pipeline}$$

---

## 🧮 Modeling Assumptions

All analysis pages read one set of assumptions from `backend/app/services/arch_model.py`, so the numbers agree across pages. They are modeling assumptions, not measurements:

| Assumption | Value |
|---|---|
| Instruction mix (ALU / Memory / Branch / Other) | 42% / 28% / 12% / 18% |
| Branch flush penalty | 16 cycles |
| Average cache-miss penalty (What-If) | 48 cycles |

What-If CPI: $\text{CPI} = \text{base} + f_{mem} \cdot m \cdot P_{miss} + f_{br} \cdot r \cdot P_{flush} + 0.08 \cdot \text{stalls}$, where $m$ is the cache miss rate and $r$ is the branch mispredict rate.

---

## 📂 Project Architecture

```
CPU-Performance-Explorer/
│
├── frontend/                     # Web Application Pages & Assets
│   ├── Dashboard.html            # Hero 3D CPU & Overview Telemetry
│   ├── PerformanceAnalyzer.html  # Iron Law & Single / ISA Mode
│   ├── PipelineSimulator.html    # 5-Stage RISC Simulator & Hazards
│   ├── BottleneckAnalyzer.html   # TMA Rule-based Diagnostic Audit
│   ├── CPUComparison.html        # Dual CPU Benchmark & Speedup
│   ├── WhatIfAnalysis.html       # Parameter Sensitivity Explorer
│   ├── AdvancedVisualizations.html# Heatmaps & Memory Latency Pyramid
│   ├── Reports.html              # SQLite Reports Hub & Exports
│   ├── css/
│   │   ├── common.css            # Custom scrollbars, glassmorphism, modals
│   │   ├── animations.css        # Neon pulse, 3D float, and keyframes
│   │   └── responsive.css        # Mobile drawer & adaptive tables
│   └── js/
│       ├── common.js             # Universal API fetch & Toast manager
│       ├── navigation.js         # App shell, routing, settings modal
│       ├── dashboard.js          # Hero CPU & Quick Analysis bindings
│       ├── device-monitor.js     # Live SVG wave charts & core matrix
│       ├── performance-analyzer.js# Single & ISA modes, real trend deltas
│       ├── pipeline-simulator.js # Timing diagram, step controller, STALL cells
│       ├── bottleneck-analyzer.js# Semi-circular gauge & stall cards
│       ├── cpu-comparison.js     # Comparison presets, clustered bars, radar
│       ├── what-if-analysis.js   # Real-time sensitivity sliders, scenario save/load
│       ├── visualizations.js     # Memory pyramid & dynamic heatmap
│       └── reports.js            # Generation, search, and CSV/JSON export
│
├── backend/                      # Python FastAPI Architecture
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, routes & static mounts
│   │   ├── api/                  # REST API Endpoints
│   │   │   ├── device.py         # /api/device (specs, live, processes)
│   │   │   ├── analyzer.py       # /api/analyzer (single, ISA mode, latest)
│   │   │   ├── pipeline.py       # /api/pipeline/simulate
│   │   │   ├── bottleneck.py     # /api/bottleneck (analyze, from-latest)
│   │   │   ├── comparison.py     # /api/comparison (analyze, presets)
│   │   │   ├── what_if.py        # /api/what-if (analyze, save, list scenarios)
│   │   │   ├── visualizations.py # /api/visualizations/data
│   │   │   └── reports.py        # /api/reports (CRUD, JSON, CSV)
│   │   ├── services/             # Core COA Calculation Engines
│   │   ├── database/             # SQLite connection & session maker
│   │   ├── models/               # SQLAlchemy ORM models
│   │   └── schemas/              # Pydantic validation schemas
│   ├── requirements.txt          # Python dependencies
│   └── tests/
│       ├── test_api.py           # 11 Unit tests covering REST endpoints
│       ├── test_coa_engine.py    # 15 COA ground truth, TMA, pipeline & edge case unit tests
│       └── test_pages.py         # 4 Page, asset, navigation & redirect integrity tests
│
├── run.py                        # Unified launcher with auto-browser trigger
├── start.bat                     # Windows one-click startup script
├── README.md                     # Documentation
└── .gitignore                    # Git ignore file
```

---

## 🛠️ Quick Start Guide

### Prerequisites
- Python 3.10+ installed on your system.

### One-Click Start (Windows)
Double-click `start.bat` in the root folder, or run in PowerShell:
```powershell
.\start.bat
```

### Manual Start
1. Install Python dependencies:
   ```bash
   py -m pip install -r backend/requirements.txt
   ```
2. Start the application:
   ```bash
   py run.py
   ```
3. Open your browser:
   - **Dashboard**: [http://127.0.0.1:8000/Dashboard.html](http://127.0.0.1:8000/Dashboard.html)
   - **Interactive API Documentation (Swagger)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🧪 Automated Test Suite

To verify the entire backend calculation engine, ground truth COA formulas, and HTML pages:
```bash
py -m unittest discover backend/tests
```
The suite contains **30 tests**:
- `test_api.py`: 11 tests verifying API endpoints, psutil telemetry responses, pipeline simulation, and reports generation.
- `test_coa_engine.py`: 15 tests verifying hand-calculated Iron Law and What-If CPI ground truth, weighted CPI invariants, zero and negative input validation, forwarding ON vs OFF and stall-cell placement, TMA breakdown (sums to 100%, responds to its inputs, continuous across CPI = 1), shared modeling assumptions, and comparison radar scaling.
- `test_pages.py`: 4 tests verifying all 8 HTML pages, all referenced JavaScript scripts, and CSS stylesheets resolve with HTTP 200 without broken links, plus the legacy-URL redirects.
