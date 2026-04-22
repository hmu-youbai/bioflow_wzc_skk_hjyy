from app.repositories.file_repository import FileTaskRepository
from tests.test_repository_contract import repository_contract

def test_file_repository_contract(tmp_path):
    repo = FileTaskRepository(str(tmp_path / "repo"))
    repository_contract(repo)
