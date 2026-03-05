from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def test_promoted_ui_page_renders_history_elements(tmp_path: Path):
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
    )
    client = TestClient(app)

    res = client.get("/ui/promoted")

    assert res.status_code == 200
    assert "Promoted History" in res.text
    assert "/api/promotions/history" in res.text
    assert "sourceRecordId" in res.text
