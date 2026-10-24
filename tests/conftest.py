import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Every test gets its own empty database and signing key."""
    monkeypatch.setenv("SATYAPAN_HOME", str(tmp_path / "home"))
