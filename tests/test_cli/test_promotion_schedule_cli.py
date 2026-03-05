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


def test_promotion_schedule_set_preserves_other_config_sections(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.dump(
            {
                "llm": {"provider": "anthropic", "model": "x", "api_key": "k"},
                "session": {"timeout_minutes": 15},
                "promotion": {"enabled": True, "schedule": "0 9 * * *"},
            }
        )
    )

    result = runner.invoke(app, ["promotion", "schedule", "--set", "0 */8 * * *"])

    assert result.exit_code == 0
    loaded = yaml.safe_load(cfg_path.read_text())
    assert loaded["llm"]["provider"] == "anthropic"
    assert loaded["session"]["timeout_minutes"] == 15
    assert loaded["promotion"]["schedule"] == "0 */8 * * *"


def test_promotion_schedule_handles_non_dict_promotion_section(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.dump({"promotion": "broken"}))

    result = runner.invoke(app, ["promotion", "schedule", "--set", "0 */12 * * *"])

    assert result.exit_code == 0
    loaded = yaml.safe_load(cfg_path.read_text())
    assert isinstance(loaded["promotion"], dict)
    assert loaded["promotion"]["schedule"] == "0 */12 * * *"


def test_promotion_schedule_rejects_invalid_cron(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["promotion", "schedule", "--set", "invalid-cron"])

    assert result.exit_code != 0
    assert "Invalid cron format" in result.output
