
import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("IG_USER_ID", "1234567890")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("IG_GRAPH_VERSION", "v21.0")
    monkeypatch.setenv("IG_GRAPH_HOST", "graph.facebook.com")
    # Point the accounts-file fallback at a nonexistent path so tests never read
    # a real ~/.instagram-mcp/accounts.json on the machine running them.
    monkeypatch.setenv("IG_ACCOUNTS_FILE", str(tmp_path / "no-accounts.json"))
    yield
