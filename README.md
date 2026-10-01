# GPU-Accelerator
A local LP solver that reads MPS models and solves them via CPU (SciPy/HiGHS, exact) or GPU (CuPy PDHG, sparse iterative). Includes scaling, benchmarking, and a simple CLI.
# ⚡ GPU-Accelerated Linear Programming (LP) Solver

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CUDA](https://img.shields.io/badge/CUDA-13.x%20%7C%2012.x-76B900.svg?logo=nvidia&logoColor=white)](https://developer.nvidia.com/cuda-zone)
[![CuPy](https://img.shields.io/badge/GPU%20Engine-CuPy%20PDHG-green.svg)](https://cupy.dev/)
[![HiGHS](https://img.shields.io/badge/CPU%20Engine-HiGHS%20SciPy-orange.svg)](https://highs.dev/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

An industrial-grade, full-stack continuous Linear Program (LP) optimization platform. Designed to seamlessly switch between **exact CPU solutions** (via SciPy's HiGHS solver) and **first-order massive-scale GPU acceleration** (via custom CuPy Primal-Dual Hybrid Gradient — PDHG routines). 

Includes a modern, reactive Web Dashboard featuring live WebSocket telemetry, real-time Chart.js convergence plots, client-side `.gz` decompression, and instant CSV/JSON solution export pipelines.

---

## 🌟 Key Highlights

- **Dual-Engine Architecture**:
  - **CPU HiGHS (Exact)**: High-performance Revised Simplex and Interior-Point algorithms. Yields exact optimal solutions, slack values, and reduced costs.
  - **GPU CuPy PDHG (Iterative Acceleration)**: Custom first-order Primal-Dual Hybrid Gradient method utilizing CUDA sparse CSR matrix-vector products (`SpMV`). Tailored for massive, high-dimensional sparse models where simplex factorization overhead becomes prohibitive.
- **Real-Time Live Convergence Telemetry**:
  - WebSocket bidirectional channel (`/api/v1/ws/solver/{job_id}`) streaming iteration counters, objective trajectories, constraint violations, and memory consumption directly to the client.
  - Dynamic **Chart.js** plot with zoom, pan, and automatic dark/light theme adjustments.
- **Client-Side Model Ingestion**:
  - Drag-and-drop file uploader supporting standard Free-Format MPS (`.mps`), LP files (`.lp`), and native in-browser **gzip decompression** (`.mps.gz`) without external libraries.
  - One-click benchmark presets (e.g., Small Sparse LP, Netlib AFIRO benchmark).
- **Interactive Solution Inspector**:
  - Paginated, searchable, and sortable data table for all Decision Variables, Slacks, and Reduced Costs.
  - Filter pills to isolate non-zero variables instantly.
  - Export solutions in `.csv` or `.json` format with a single click.
- **Hardware Auto-Detection & Resilient Fallback**:
  - Automatically identifies local NVIDIA GPUs (e.g., RTX 2050/3060/4090/A100) and VRAM capacity.
  - Graceful fallback ensures that even on CPU-only environments (such as Render free tiers), the application remains 100% operational without crashing.
- **Zero-Storage Privacy Model**:
  - All input files and model representations are processed in-memory and discarded upon execution completion.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Client ["Frontend (Modern Web UI)"]
        UI["Dashboard & File Uploader (.mps, .lp, .gz)"]
        WSClient["WebSocket Client"]
        Chart["Chart.js Live Convergence Plot"]
        Table["Paginated Variable & Slack Table"]
    end

    subgraph API ["FastAPI Async Server Layer"]
        Router["REST Endpoints (/api/v1/solve, /capabilities)"]
        WSRoute["WebSocket Router (/api/v1/ws/solver/{job_id})"]
        Parser["In-Memory Free MPS Parser"]
        JobStore["In-Memory Thread-Safe Job Store"]
    end

    subgraph Compute ["Optimization Engines"]
        direction LR
        CPU["CPU Engine\nSciPy HiGHS\n(Simplex / Interior-Point)"]
        GPU["GPU Engine\nCuPy PDHG\n(CUDA Sparse SpMV)"]
    end

    UI -->|Upload Model & Params| Router
    Router --> Parser
    Parser --> JobStore
    JobStore --> Compute
    Compute -->|Iteration Progress| WSRoute
    WSRoute -->|Live Data Stream| WSClient
    WSClient --> Chart
    Compute -->|Final Solution & Duals| Router
    Router --> Table
