"""Migration job lifecycle management."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.constants import MIGRATION_STATUS_STARTED


class JobManager:
    """Creates and tracks migration jobs."""

    _jobs: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def create_job(cls, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        job = {
            "job_id": job_id,
            "start_time": datetime.now(),
            "status": MIGRATION_STATUS_STARTED,
            "tables": tables or [],
            "completed_tables": [],
            "failed_tables": [],
        }
        cls._jobs[job_id] = job
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        return cls._jobs.get(job_id)

    @classmethod
    def update_status(cls, job_id: str, status: str) -> None:
        if job_id in cls._jobs:
            cls._jobs[job_id]["status"] = status

    @classmethod
    def mark_table_complete(cls, job_id: str, table_name: str) -> None:
        if job_id in cls._jobs:
            cls._jobs[job_id]["completed_tables"].append(table_name)

    @classmethod
    def mark_table_failed(cls, job_id: str, table_name: str, error: str) -> None:
        if job_id in cls._jobs:
            cls._jobs[job_id]["failed_tables"].append({
                "table": table_name,
                "error": error,
            })
