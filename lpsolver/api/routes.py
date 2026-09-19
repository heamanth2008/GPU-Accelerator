from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from api.schemas import SolveRequest, CapabilitiesResponse
from api.job_store import job_store, Job
from src.mps_parser import parse_mps
from src.solver import solve

ROOT = Path(__file__).resolve().parent.parent
MAX_MODEL_BYTES = 10 * 1024 * 1024

router = APIRouter()

_GPU_INFO_CACHE = None

def get_hardware_info() -> dict:
    global _GPU_INFO_CACHE
    if _GPU_INFO_CACHE is not None and _GPU_INFO_CACHE.get("gpuAvailable"):
        return _GPU_INFO_CACHE

    info = {
        "gpuHardwareDetected": False,
        "gpuDevice": None,
        "gpuAvailable": False,
        "smartAppControlBlocked": False,
        "vramTotalMB": 0,
    }

    # 1. Check physical GPU via nvidia-smi
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            info["gpuHardwareDetected"] = True
            info["gpuDevice"] = parts[0]
            if len(parts) > 1:
                try:
                    info["vramTotalMB"] = int(parts[1])
                except ValueError:
                    pass
    except Exception:
        pass

    # 2. Check CuPy availability & Smart App Control
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() > 0:
            info["gpuAvailable"] = True
            if not info["gpuDevice"]:
                dev_name = cp.cuda.runtime.getDeviceProperties(0)["name"]
                info["gpuDevice"] = dev_name.decode() if isinstance(dev_name, bytes) else str(dev_name)
    except Exception as exc:
        err_msg = str(exc)
        if "Application Control policy has blocked this file" in err_msg or "0283ac0f" in err_msg:
            info["smartAppControlBlocked"] = True

    _GPU_INFO_CACHE = info
    return info


def gpu_is_available() -> bool:
    return get_hardware_info()["gpuAvailable"]


@router.get("/capabilities")
async def capabilities():
    hw = get_hardware_info()
    return {
        "gpuAvailable": hw["gpuAvailable"],
        "gpuHardwareDetected": hw["gpuHardwareDetected"],
        "gpuDevice": hw["gpuDevice"],
        "smartAppControlBlocked": hw["smartAppControlBlocked"],
        "vramTotalMB": hw["vramTotalMB"],
        "deployment": "render" if os.environ.get("RENDER") else "local",
    }


@router.get("/presets")
async def get_presets():
    return [
        {"id": "sample", "name": "Small Sparse LP (3 vars)", "file": "sample_small.mps"},
        {"id": "afiro", "name": "Netlib AFIRO Benchmark (32 vars, 27 rows)", "file": "afiro.mps"},
    ]


@router.get("/sample")
async def get_sample(preset: str = "sample"):
    fname = "afiro.mps" if preset == "afiro" else "sample_small.mps"
    sample_path = ROOT / "data" / fname
    if not sample_path.exists():
        sample_path = ROOT / "data" / "sample_small.mps"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Preset file not found")
    return {"filename": sample_path.name, "mpsText": sample_path.read_text(encoding="utf-8")}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job)


@router.get("/jobs/{job_id}/export")
async def export_job(job_id: str, format: str = "csv"):
    job = job_store.get_job(job_id)
    if not job or job.status != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not yet completed")
    variables = job.variables or []
    if format == "json":
        content = json.dumps({
            "model": job.model,
            "result": job.result,
            "variables": variables,
        }, indent=2)
        media = "application/json"
        ext = "json"
    else:
        lines = ["name,value,reduced_cost,type"] + [
            f"{v.get('name','')},{v.get('value',0.0)},{v.get('reduced_cost',0.0)},{v.get('type','Continuous')}"
            for v in variables
        ]
        content = "\n".join(lines)
        media = "text/csv"
        ext = "csv"
    fname = f"solution_{job_id[:8]}.{ext}"
    return StreamingResponse(
        io.StringIO(content),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )


@router.post("/solve")
async def solve_model(request: SolveRequest):
    """Create a solve job, execute in background, return job_id."""
    job = job_store.create_job()
    asyncio.create_task(_run_solve_job(job, request))
    return {"job_id": job.job_id, "status": "queued"}


@router.websocket("/ws/solver/{job_id}")
async def websocket_solver(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = job_store.get_job(job_id)
    if not job:
        await websocket.send_json({"type": "error", "message": "Job not found"})
        await websocket.close()
        return

    sent_progress = 0
    try:
        while True:
            # Stream any new progress iterations
            new_entries = job.progress_log[sent_progress:]
            for entry in new_entries:
                await websocket.send_json({
                    "type": "progress",
                    "iteration": entry.iteration,
                    "objective": entry.objective,
                    "feasibility": entry.feasibility,
                })
                sent_progress += 1

            # Heartbeat status
            await websocket.send_json({
                "type": "status",
                "status": job.status,
                "queueDepth": job_store.active_count(),
            })

            if job.status in ("completed", "failed"):
                await websocket.send_json({"type": "result", "payload": _job_response(job)})
                break

            await asyncio.sleep(0.15)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _run_solve_job(job: Job, request: SolveRequest):
    job.status = "running"
    try:
        result = await asyncio.to_thread(_solve_blocking, job, request)
        job.model = result["model"]
        job.result = result["result"]
        job.variables = result["variables"]
        job.status = "completed"
    except Exception as exc:
        job.error = str(exc)
        job.status = "failed"


def _solve_blocking(job: Job, request: SolveRequest) -> dict:
    mps_text = request.mps_text

    with tempfile.NamedTemporaryFile(mode="w", suffix=".mps", encoding="utf-8", delete=False) as f:
        f.write(mps_text)
        temp_path = Path(f.name)
    try:
        model = parse_mps(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    def progress_callback(iteration, objective, feasibility):
        job.add_progress(iteration, objective, feasibility)

    if request.backend == "gpu":
        from src.gpu_solver import solve_gpu_pdhg
        result = solve_gpu_pdhg(
            model,
            max_iterations=request.max_iterations,
            tolerance=request.tolerance,
            check_every=request.check_every,
            progress_callback=progress_callback,
        )
    else:
        result = solve(model, progress_callback=progress_callback)

    reduced_costs = result.get("reduced_costs", [])
    slacks = result.get("slack", [])

    variables = []
    if result.get("x") is not None:
        for i, (name, val) in enumerate(zip(model.col_names, result["x"])):
            rc = reduced_costs[i] if i < len(reduced_costs) else 0.0
            variables.append({
                "name": name,
                "value": float(val),
                "reduced_cost": float(rc),
                "type": "Continuous",
            })

    return {
        "model": {
            "name": model.name,
            "rows": model.num_rows,
            "columns": model.num_cols,
            "nonzeros": model.nnz,
        },
        "result": {k: v for k, v in result.items() if k not in ("x", "reduced_costs", "slack")},
        "variables": variables,
    }


def _job_response(job: Job) -> dict:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "model": job.model,
        "result": job.result,
        "variables": job.variables,
        "error": job.error,
        "progress": len(job.progress_log),
    }
