from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def _client(tmp_path: Path) -> TestClient:
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
    )
    return TestClient(app)


def test_shared_ui_shell_page_loads_with_foundation_navigation(tmp_path: Path):
    client = _client(tmp_path)

    res = client.get("/ui")

    assert res.status_code == 200
    assert "B-TWIN" in res.text
    assert 'href="/ui/workflows"' in res.text
    assert 'href="/ui/entries"' in res.text
    assert 'href="/ui/sources"' in res.text
    assert 'href="/ui/summary"' in res.text
    assert 'href="/ops"' in res.text
    assert ">workflows<" in res.text
    assert ">entries<" in res.text
    assert ">sources<" in res.text
    assert ">summary<" in res.text
    assert ">ops<" in res.text
