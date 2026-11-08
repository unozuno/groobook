import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """모든 테스트가 임시 data 디렉토리를 사용하도록 격리한다."""
    monkeypatch.setenv("GROOBOOK_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"
