import json
import logging
from pathlib import Path

from btwin.core.agent_registry import AgentRegistry, resolve_openclaw_config_path


def test_resolve_openclaw_config_path_prefers_override() -> None:
    path = resolve_openclaw_config_path("~/custom/openclaw.json")
    assert path.as_posix().endswith("custom/openclaw.json")


def test_registry_loads_agents_from_openclaw_config(tmp_path: Path) -> None:
    config_path = tmp_path / "openclaw.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "main": {"model": "x"},
                    "codex-code": {"model": "x"},
                }
            }
        )
    )

    registry = AgentRegistry(config_path=config_path, extra_agents={"research-bot"})

    assert registry.is_allowed("main")
    assert registry.is_allowed("codex-code")
    assert registry.is_allowed("research-bot")


def test_registry_reload_keeps_initial_agents_when_file_missing(tmp_path: Path) -> None:
    registry = AgentRegistry(
        config_path=tmp_path / "missing.json",
        initial_agents={"main", "codex-code"},
        extra_agents={"research-bot"},
    )

    summary = registry.reload()

    assert summary["count"] == 3
    assert registry.is_allowed("main")
    assert registry.is_allowed("codex-code")
    assert registry.is_allowed("research-bot")


def test_registry_falls_back_on_corrupt_json(tmp_path: Path, caplog) -> None:
    """Corrupt JSON config should not crash; fall back to initial + extra agents."""
    config_path = tmp_path / "openclaw.json"
    config_path.write_text("{not valid json!!!")

    with caplog.at_level(logging.WARNING):
        registry = AgentRegistry(
            config_path=config_path,
            initial_agents={"main"},
            extra_agents={"helper"},
        )
        # Constructor skips reload() when initial_agents is provided,
        # so call it explicitly to exercise the corrupt JSON path.
        summary = registry.reload()

    assert registry.is_allowed("main")
    assert registry.is_allowed("helper")
    assert registry.agents == {"main", "helper"}
    assert summary["count"] == 2
    assert "Failed to load agent config" in caplog.text
