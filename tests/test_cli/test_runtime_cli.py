from pathlib import Path

import yaml
from typer.testing import CliRunner

from btwin.cli.main import app


runner = CliRunner()


def test_runtime_show_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["runtime", "show"])

    assert result.exit_code == 0
    assert "Runtime mode: attached" in result.stdout
    assert "OpenClaw config path: -" in result.stdout


def test_runtime_show_reads_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.dump(
            {
                "runtime": {
                    "mode": "standalone",
                    "openclaw_config_path": "~/.openclaw/custom.toml",
                }
            }
        )
    )

    result = runner.invoke(app, ["runtime", "show"])

    assert result.exit_code == 0
    assert "Runtime mode: standalone" in result.stdout
    assert "OpenClaw config path: ~/.openclaw/custom.toml" in result.stdout
