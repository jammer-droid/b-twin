from pathlib import Path

import yaml
from typer.testing import CliRunner

from btwin.cli.main import app


runner = CliRunner()


def test_runtime_show_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("BTWIN_OPENCLAW_CONFIG_PATH", raising=False)

    result = runner.invoke(app, ["runtime", "show"])

    assert result.exit_code == 0
    assert "Runtime mode: attached" in result.stdout
    assert "Configured OpenClaw config path: -" in result.stdout
    assert "Effective OpenClaw config path: -" in result.stdout


def test_runtime_show_reads_config_and_env_precedence_in_attached_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BTWIN_OPENCLAW_CONFIG_PATH", "/tmp/from-env.toml")

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.dump(
            {
                "runtime": {
                    "mode": "attached",
                    "openclaw_config_path": "~/.openclaw/custom.toml",
                }
            }
        )
    )

    result = runner.invoke(app, ["runtime", "show"])

    assert result.exit_code == 0
    assert "Runtime mode: attached" in result.stdout
    assert "Configured OpenClaw config path: ~/.openclaw/custom.toml" in result.stdout
    assert "Effective OpenClaw config path: /tmp/from-env.toml" in result.stdout


def test_runtime_show_standalone_mode_effective_path_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BTWIN_OPENCLAW_CONFIG_PATH", "/tmp/from-env.toml")

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
    assert "Configured OpenClaw config path: ~/.openclaw/custom.toml" in result.stdout
    assert "Effective OpenClaw config path: -" in result.stdout
