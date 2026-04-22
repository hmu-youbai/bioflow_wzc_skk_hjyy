from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass
class Settings:
    repository_type: str = os.getenv("REPOSITORY_TYPE", "file").strip().lower()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./sandbox_service.db")
    data_dir: str = os.getenv("DATA_DIR", "/tmp/sandbox_service")
    isolate_bin: str = os.getenv("ISOLATE_BIN", "isolate")
    list_tasks_default_limit: int = int(os.getenv("LIST_TASKS_DEFAULT_LIMIT", "100"))

def get_settings() -> Settings:
    return Settings()
