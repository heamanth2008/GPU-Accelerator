from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProgressEntry:
    iteration: int
    objective: Optional[float] = None
    feasibility: Optional[float] = None


@dataclass
class Job:
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    model: Optional[dict] = None
    result: Optional[dict] = None
    variables: Optional[list] = None
    error: Optional[str] = None
    progress_log: List[ProgressEntry] = field(default_factory=list)

    def add_progress(self, iteration: int, objective=None, feasibility=None):
        self.progress_log.append(ProgressEntry(
            iteration=iteration,
            objective=float(objective) if objective is not None else None,
            feasibility=float(feasibility) if feasibility is not None else None,
        ))


class JobStore:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}

    def create_job(self) -> Job:
        job = Job()
        self._jobs[job.job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def cleanup_old_jobs(self):
        cutoff = time.time() - 3600
        to_delete = [jid for jid, job in self._jobs.items() if job.created_at < cutoff]
        for jid in to_delete:
            del self._jobs[jid]

    def active_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status in ("queued", "running"))


job_store = JobStore()
