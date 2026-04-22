from __future__ import annotations
from app.repositories.base import TaskRepository
from app.repositories.file_repository import FileTaskRepository
from app.repositories.mysql_repository import MySQLTaskRepository
from app.repositories.sqlite_repository import SQLiteTaskRepository
from app.settings import Settings

def build_repository(settings: Settings) -> TaskRepository:
    if settings.repository_type == "file":
        return FileTaskRepository(settings.data_dir)
    if settings.repository_type == "mysql":
        repo = MySQLTaskRepository(settings.database_url)
        repo.create_schema()
        return repo
    if settings.repository_type == "sqlite":
        repo = SQLiteTaskRepository(settings.database_url)
        repo.create_schema()
        return repo
    raise ValueError(f"unsupported repository type: {settings.repository_type}")
