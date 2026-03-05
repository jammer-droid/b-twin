from pathlib import Path

from fastapi.testclient import TestClient

from btwin.api.collab_api import create_collab_app


def test_entries_ui_page_has_record_type_filter_controls(tmp_path: Path):
    app = create_collab_app(
        data_dir=tmp_path,
        initial_agents={"main", "codex-code", "research-bot"},
    )
    client = TestClient(app)

    res = client.get("/ui/entries")

    assert res.status_code == 200
    assert "Entries" in res.text
    assert "recordTypeFilter" in res.text
    assert "/api/entries" in res.text
    assert "collab" in res.text
    assert "convo" in res.text
