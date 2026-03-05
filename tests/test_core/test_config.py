import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from btwin.config import BTwinConfig, load_config, resolve_data_dir


def test_load_config_from_yaml(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text("""
llm:
  provider: anthropic
  model: claude-haiku-4-5-20251001
session:
  timeout_minutes: 5
""")
    config = load_config(cfg_file)

    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-haiku-4-5-20251001"
    assert config.session.timeout_minutes == 5


def test_default_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BTWIN_DATA_DIR", raising=False)
    config = BTwinConfig()
    assert config.llm.provider == "anthropic"
    assert config.llm.model == "claude-haiku-4-5-20251001"
    assert config.session.timeout_minutes == 10
    assert config.data_dir == Path.home() / ".btwin"


def test_data_dir_expansion():
    config = BTwinConfig()
    assert config.data_dir.is_absolute()


def test_unknown_key_rejected():
    with pytest.raises(ValidationError):
        BTwinConfig(unknown_key="value")


def test_runtime_defaults_to_attached():
    config = BTwinConfig()
    assert config.runtime.mode == "attached"
    assert config.runtime.openclaw_config_path is None


def test_runtime_mode_loads_from_yaml(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        """
runtime:
  mode: standalone
  openclaw_config_path: ~/.openclaw/config.toml
"""
    )

    config = load_config(cfg_file)

    assert config.runtime.mode == "standalone"
    assert config.runtime.openclaw_config_path == Path("~/.openclaw/config.toml")


def test_runtime_mode_rejects_invalid_value():
    with pytest.raises(ValidationError):
        BTwinConfig(runtime={"mode": "invalid"})


# --- resolve_data_dir tests ---


def test_resolve_data_dir_env_var(tmp_path, monkeypatch):
    """BTWIN_DATA_DIR env var takes highest priority."""
    monkeypatch.setenv("BTWIN_DATA_DIR", str(tmp_path / "custom"))
    result = resolve_data_dir()
    assert result == tmp_path / "custom"


def test_resolve_data_dir_project_local(tmp_path, monkeypatch):
    """Per-project .btwin/ directory detected from CWD."""
    project_btwin = tmp_path / ".btwin"
    project_btwin.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BTWIN_DATA_DIR", raising=False)
    result = resolve_data_dir()
    assert result == project_btwin


def test_resolve_data_dir_global_default(tmp_path, monkeypatch):
    """Falls back to ~/.btwin when no env var or project dir."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BTWIN_DATA_DIR", raising=False)
    result = resolve_data_dir()
    assert result == Path.home() / ".btwin"
