"""FastAPI server for the GPU LP Solver — replaces SimpleHTTPRequestHandler."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import router, gpu_is_available
from api.job_store import job_store

app = FastAPI(
    title="GPU LP Solver",
    description="High-performance Linear Program solver with CPU (HiGHS) and GPU (CuPy PDHG) backends.",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Versioned API routes
app.include_router(router, prefix="/api/v1")

# Legacy unversioned routes (backward compat with old frontend)
@app.get("/api/capabilities")
async def legacy_capabilities():
    return {"gpuAvailable": gpu_is_available(),
            "deployment": "render" if os.environ.get("RENDER") else "local"}

@app.get("/api/sample")
async def legacy_sample():
    sample_path = ROOT / "data" / "sample_small.mps"
    if not sample_path.exists():
        return JSONResponse(status_code=404, content={"error": "Sample file not found"})
    return {"filename": "sample_small.mps", "mpsText": sample_path.read_text(encoding="utf-8")}

@app.post("/api/solve")
async def legacy_solve(request: Request):
    """Legacy synchronous solve endpoint for backward compatibility."""
    import asyncio, tempfile
    from pathlib import Path as _Path
    from api.schemas import SolveRequest, BackendType
    from api.routes import _run_solve_job
    from api.job_store import job_store

    try:
        body = await request.body()
        payload = json.loads(body.decode("utf-8"))
        backend_str = payload.get("backend", "highs")
        req = SolveRequest(
            mpsText=payload.get("mpsText", ""),
            backend=BackendType(backend_str),
            maxIterations=int(payload.get("maxIterations", 50_000)),
        )
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    if req.backend == BackendType.gpu and not gpu_is_available():
        return JSONResponse(status_code=400, content={
            "error": "GPU solving is unavailable on this server. Select CPU HiGHS."
        })

    job = job_store.create_job()
    await _run_solve_job(job, req)

    if job.status == "failed":
        return JSONResponse(status_code=500, content={"error": job.error})

    return JSONResponse(content={
        "model": job.model,
        "result": job.result,
        "variables": job.variables or [],
    })


# Static frontend — must be mounted LAST so API routes take priority
app.mount("/", StaticFiles(directory=str(ROOT / "web"), html=True), name="static")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
