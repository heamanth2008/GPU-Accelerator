from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class BackendType(str, Enum):
    highs = "highs"
    gpu = "gpu"


class SolveRequest(BaseModel):
    mps_text: str = Field(..., alias="mpsText", min_length=1)
    backend: BackendType = BackendType.highs
    max_iterations: int = Field(50_000, ge=100, le=1_000_000, alias="maxIterations")
    tolerance: float = Field(1e-5, gt=0, le=1.0)
    check_every: int = Field(100, ge=10, le=1000, alias="checkEvery")

    model_config = {"populate_by_name": True}


class VariableResult(BaseModel):
    name: str
    value: float


class ModelInfo(BaseModel):
    name: str
    rows: int
    columns: int
    nonzeros: int


class SolveResult(BaseModel):
    status: str
    objective: Optional[float] = None
    elapsed_sec: float
    solver: str
    iterations: Optional[int] = None
    max_constraint_violation: Optional[float] = None
    device: Optional[str] = None


class JobStatusEnum(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class CapabilitiesResponse(BaseModel):
    gpu_available: bool
    deployment: str
