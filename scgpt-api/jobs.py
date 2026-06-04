"""Thread-safe in-memory job store.

The store does **not** persist across restarts – it exists so clients can
query progress and final outcomes via ``GET /job/{job_id}``. For multi-replica
deployments the implementation should be swapped for Redis / Cosmos DB; the
interface is intentionally narrow to make that swap straightforward.
"""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from schemas import ErrorResponse, JobInfo, JobStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobStore:
    """LRU-capped, lock-protected map of ``job_id -> JobInfo``."""

    def __init__(self, max_history: int) -> None:
        if max_history < 1:
            raise ValueError("max_history must be >= 1")
        self._max_history = max_history
        self._lock = threading.RLock()
        self._jobs: "OrderedDict[str, JobInfo]" = OrderedDict()

    # Lifecycle helpers

    def create(
        self,
        *,
        endpoint: str,
        request: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> JobInfo:
        job = JobInfo(
            job_id=job_id or uuid.uuid4().hex,
            status=JobStatus.pending,
            endpoint=endpoint,
            created_at=utcnow(),
            request=request,
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self.evict_locked()
        return job

    def mark_running(self, job_id: str) -> JobInfo:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.running
            job.started_at = utcnow()
            return job

    def mark_completed(self, job_id: str, result: Dict[str, Any]) -> JobInfo:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.completed
            job.finished_at = utcnow()
            job.result = result
            if job.started_at:
                job.duration_seconds = (
                    job.finished_at - job.started_at
                ).total_seconds()
            return job

    def mark_failed(self, job_id: str, error: ErrorResponse) -> JobInfo:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.failed
            job.finished_at = utcnow()
            job.error = error
            if job.started_at:
                job.duration_seconds = (
                    job.finished_at - job.started_at
                ).total_seconds()
            return job

    # Read access

    def get(self, job_id: str) -> Optional[JobInfo]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                self._jobs.move_to_end(job_id)
            return job

    def __contains__(self, job_id: object) -> bool:
        with self._lock:
            return job_id in self._jobs

    def __len__(self) -> int:
        with self._lock:
            return len(self._jobs)

    # Internal

    def evict_locked(self) -> None:
        while len(self._jobs) > self._max_history:
            self._jobs.popitem(last=False)
