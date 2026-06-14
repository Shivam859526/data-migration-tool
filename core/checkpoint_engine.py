"""Resumable checkpoint storage for migration jobs."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config.constants import CHECKPOINT_FILE


class CheckpointEngine:
    """Persists and restores migration progress per job and table."""

    CHECKPOINT_FILE = CHECKPOINT_FILE

    @classmethod
    def _load_all(cls) -> Dict[str, Any]:
        if not os.path.exists(cls.CHECKPOINT_FILE):
            return {"jobs": {}}
        with open(cls.CHECKPOINT_FILE, "r", encoding="utf-8") as file:
            content = file.read().strip()
            if not content:
                return {"jobs": {}}
            data = json.loads(content)
        if "jobs" not in data:
            return {"jobs": {data.get("job_id", "default"): {"tables": {data.get("table_name", ""): data}}}}
        return data

    @classmethod
    def _save_all(cls, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(cls.CHECKPOINT_FILE) or ".", exist_ok=True)
        with open(cls.CHECKPOINT_FILE, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, default=str)

    @classmethod
    def save_checkpoint(
        cls,
        job_id: str,
        table_name: str,
        offset: int,
        batch_number: int = 0,
        last_key: Optional[List[Any]] = None,
    ) -> None:
        """Save checkpoint for a specific job and table."""
        data = cls._load_all()
        jobs = data.setdefault("jobs", {})
        job = jobs.setdefault(job_id, {"tables": {}})
        entry: Dict[str, Any] = {
            "job_id": job_id,
            "table_name": table_name,
            "batch_number": batch_number,
            "offset": offset,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if last_key is not None:
            entry["last_key"] = list(last_key)
        job["tables"][table_name] = entry
        cls._save_all(data)

    @classmethod
    def load_checkpoint(
        cls, job_id: str, table_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Load checkpoint for a job, optionally filtered by table."""
        data = cls._load_all()
        job = data.get("jobs", {}).get(job_id)
        if not job:
            return None

        if table_name:
            return job.get("tables", {}).get(table_name)

        return job

    @classmethod
    def get_table_offset(cls, job_id: str, table_name: str) -> int:
        """Return saved offset for a table, or 0 if none."""
        checkpoint = cls.load_checkpoint(job_id, table_name)
        if checkpoint:
            return int(checkpoint.get("offset", 0))
        return 0

    @classmethod
    def get_table_last_key(
        cls, job_id: str, table_name: str
    ) -> Optional[Tuple[Any, ...]]:
        """Return saved keyset cursor for resumable keyset pagination."""
        checkpoint = cls.load_checkpoint(job_id, table_name)
        if checkpoint and "last_key" in checkpoint:
            return tuple(checkpoint["last_key"])
        return None

    @classmethod
    def clear_checkpoint(cls, job_id: str, table_name: Optional[str] = None) -> None:
        """Remove checkpoints for a job or specific table."""
        data = cls._load_all()
        job = data.get("jobs", {}).get(job_id)
        if not job:
            return

        if table_name:
            job.get("tables", {}).pop(table_name, None)
        else:
            data["jobs"].pop(job_id, None)

        cls._save_all(data)

    @classmethod
    def list_checkpoints(cls, job_id: str) -> List[Dict[str, Any]]:
        """Return all table checkpoints for a job."""
        job = cls.load_checkpoint(job_id)
        if not job:
            return []
        return list(job.get("tables", {}).values())
