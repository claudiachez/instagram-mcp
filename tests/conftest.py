
import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("IG_USER_ID", "1234567890")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("IG_GRAPH_VERSION", "v21.0")
    monkeypatch.setenv("IG_GRAPH_HOST", "graph.facebook.com")
    yield
