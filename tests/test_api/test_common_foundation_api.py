from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def _client(tmp_path: Path) -> TestClient:
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
        admin_token="secret-token",
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "scope"),
    [
        ("/api/workflows/health", "workflows"),
        ("/api/entries/health", "entries"),
        ("/api/sources/health", "sources"),
    ],
)
def test_common_foundation_health_routes_exist_with_shared_response_shape(
    tmp_path: Path, path: str, scope: str
):
    client = _client(tmp_path)

    res = client.get(path)

    assert res.status_code == 200
    assert res.json() == {
        "ok": True,
        "scope": scope,
        "status": "available",
    }
