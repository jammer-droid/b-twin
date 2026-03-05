from pathlib import Path

import yaml
from typer.testing import CliRunner

from btwin.cli.main import app


runner = CliRunner()


def test_promotion_schedule_shows_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["promotion", "schedule"])

    assert result.exit_code == 0
    assert "0 9,21 * * *" in result.stdout


def test_promotion_schedule_set_updates_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["promotion", "schedule", "--set", "0 */6 * * *"])

    assert result.exit_code == 0
    assert "updated" in result.stdout.lower()

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    loaded = yaml.safe_load(cfg_path.read_text())
    assert loaded["promotion"]["schedule"] == "0 */6 * * *"
