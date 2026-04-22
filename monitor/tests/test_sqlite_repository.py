from app.repositories.sqlite_repository import SQLiteTaskRepository
from tests.test_repository_contract import repository_contract

def test_sqlite_repository_contract(tmp_path):
    db_path = tmp_path / "sandbox.db"
    repo = SQLiteTaskRepository(f"sqlite:///{db_path}")
    repo.create_schema()
    repository_contract(repo)
