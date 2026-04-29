import json
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = BASE_DIR / "jobs"
JOBS_DIR.mkdir(exist_ok=True)


class Storage:
    def __init__(self):
        self.jobs_dir = JOBS_DIR

    def create_job_dir(self, job_id: str) -> Path:
        job_dir = self.jobs_dir / job_id
        (job_dir / "images").mkdir(parents=True, exist_ok=True)
        (job_dir / "output").mkdir(parents=True, exist_ok=True)
        return job_dir

    def update_job(self, job_id: str, data: Dict[str, Any]) -> None:
        job_file = self.jobs_dir / job_id / "job.json"
        job_file.parent.mkdir(parents=True, exist_ok=True)
        job_file.write_text(json.dumps(data, ensure_ascii=False))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        job_file = self.jobs_dir / job_id / "job.json"
        if not job_file.exists():
            return None
        try:
            return json.loads(job_file.read_text())
        except Exception:
            return None

    def get_model_path(self, job_id: str) -> Optional[Path]:
        job = self.get_job(job_id)
        if not job or not job.get("model_path"):
            return None
        p = Path(job["model_path"])
        return p if p.exists() else None

    def list_jobs(self) -> List[Dict[str, Any]]:
        jobs = []
        if not self.jobs_dir.exists():
            return jobs
        for d in sorted(self.jobs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            jf = d / "job.json"
            if jf.exists():
                try:
                    jobs.append(json.loads(jf.read_text()))
                except Exception:
                    pass
        return jobs


storage = Storage()
