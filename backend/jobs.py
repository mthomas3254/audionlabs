"""Background jobs for work that takes longer than a web request may last.

Cloudflare, which fronts audionlabs.ai, closes any request that has not answered
within 100 seconds and shows the visitor a 524. Demucs and Whisper on Railway's
CPU take minutes for a full song. So an upload returns a job id immediately,
the work runs on a worker thread, and the page polls /jobs/{id}. Every poll
answers in milliseconds.

Jobs live in memory. Railway runs one instance, and results are ephemeral
anyway, so a restart simply drops in-flight jobs. Finished jobs expire after
MAX_AGE_SECONDS so the table cannot grow without bound.

    JOB_WORKERS   how many jobs may run at once (default 1: Demucs saturates a
                  CPU, so parallel jobs only slow each other down)
"""
import os
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

MAX_AGE_SECONDS = 2 * 60 * 60

Work = Callable[[Callable[[str], None]], Dict[str, Any]]


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"          # queued | running | done | error
    stage: str = "Waiting in line"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def public(self) -> Dict[str, Any]:
        return {"job_id": self.id, "kind": self.kind, "status": self.status,
                "stage": self.stage, "result": self.result, "error": self.error}


class JobStore:
    def __init__(self, workers: Optional[int] = None):
        if workers is None:
            try:
                workers = int(os.getenv("JOB_WORKERS", "1"))
            except ValueError:
                workers = 1
        self._executor = ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="job")
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, work: Work) -> Job:
        self._expire()
        job = Job(id=uuid.uuid4().hex, kind=kind)
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job, work)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def queue_position(self, job: Job) -> int:
        """How many queued jobs were submitted before this one."""
        with self._lock:
            return sum(1 for j in self._jobs.values()
                       if j.status == "queued" and j.created < job.created)

    # ---- internals ----

    def _run(self, job: Job, work: Work) -> None:
        def set_stage(text: str) -> None:
            job.stage = text
            job.updated = time.time()

        job.status = "running"
        set_stage("Starting")
        try:
            job.result = work(set_stage)
            job.status = "done"
            set_stage("Done")
        except Exception as exc:  # noqa: BLE001 - the visitor gets a short message, the log gets the rest
            # str(exc) is the message the work chose for the visitor. The full detail,
            # including any command line or path, goes only to the server log.
            job.error = str(exc).strip().splitlines()[0] if str(exc).strip() else "Processing failed."
            job.status = "error"
            set_stage("Failed")
            print(f"[job {job.kind} {job.id}] failed: {exc.__class__.__name__}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    def _expire(self) -> None:
        cutoff = time.time() - MAX_AGE_SECONDS
        with self._lock:
            stale = [k for k, j in self._jobs.items()
                     if j.status in ("done", "error") and j.updated < cutoff]
            for k in stale:
                del self._jobs[k]
