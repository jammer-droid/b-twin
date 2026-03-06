import re
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


def test_shared_ui_shell_navigation_links_resolve(tmp_path: Path):
    client = _client(tmp_path)

    shell = client.get("/ui")
    hrefs = set(re.findall(r'href="([^"]+)"', shell.text))

    assert {"/ui/workflows", "/ui/entries", "/ui/sources", "/ui/summary", "/ops"} <= hrefs

    for href in hrefs:
        linked = client.get(href)
        assert linked.status_code != 404, f"expected {href} to resolve, got 404"
