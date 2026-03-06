from pathlib import Path
from unittest.mock import patch

import yaml

from btwin.api.collab_api import create_default_collab_app


def test_default_collab_app_uses_runtime_config_path_when_env_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("BTWIN_OPENCLAW_CONFIG_PATH", raising=False)

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.dump(
            {
                "runtime": {
                    "mode": "attached",
                    "openclaw_config_path": "~/.openclaw/from-config.toml",
                }
            }
        )
    )

    with patch("btwin.api.collab_api.create_collab_app") as create_app:
        create_app.return_value = object()
        create_default_collab_app()

    assert create_app.call_args.kwargs["runtime_mode"] == "attached"
    assert create_app.call_args.kwargs["openclaw_config_path"] == "~/.openclaw/from-config.toml"


def test_default_collab_app_env_openclaw_config_path_has_priority(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BTWIN_OPENCLAW_CONFIG_PATH", "/tmp/from-env.toml")

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.dump(
            {
                "runtime": {
                    "mode": "attached",
                    "openclaw_config_path": "~/.openclaw/from-config.toml",
                }
            }
        )
    )

    with patch("btwin.api.collab_api.create_collab_app") as create_app:
        create_app.return_value = object()
        create_default_collab_app()

    assert create_app.call_args.kwargs["runtime_mode"] == "attached"
    assert create_app.call_args.kwargs["openclaw_config_path"] == "/tmp/from-env.toml"


def test_default_collab_app_standalone_mode_ignores_env_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BTWIN_OPENCLAW_CONFIG_PATH", "/tmp/from-env.toml")

    cfg_path = Path(tmp_path) / ".btwin" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.dump(
            {
                "runtime": {
                    "mode": "standalone",
                    "openclaw_config_path": "~/.openclaw/from-config.toml",
                }
            }
        )
    )

    with patch("btwin.api.collab_api.create_collab_app") as create_app:
        create_app.return_value = object()
        create_default_collab_app()

    assert create_app.call_args.kwargs["runtime_mode"] == "standalone"
    assert create_app.call_args.kwargs["openclaw_config_path"] is None
