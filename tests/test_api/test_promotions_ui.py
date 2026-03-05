from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def test_promotions_ui_page_renders_core_elements(tmp_path: Path):
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
    )
    client = TestClient(app)

    res = client.get("/ui/promotions")

    assert res.status_code == 200
    assert "Promotions" in res.text
    assert "statusFilter" in res.text
    assert "approve" in res.text
    assert "/api/promotions" in res.text
