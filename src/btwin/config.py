"""Configuration management for B-TWIN."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


def resolve_data_dir() -> Path:
    """Resolve data directory with precedence: env var > project-local > global default."""
    # 1. Environment variable (highest priority)
    env_dir = os.environ.get("BTWIN_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    # 2. Per-project .btwin/ directory
    project_dir = Path.cwd() / ".btwin"
    if project_dir.is_dir():
        return project_dir

    # 3. Global default
    return Path.home() / ".btwin"


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    api_key: str | None = None


class SessionConfig(BaseModel):
    timeout_minutes: int = 10


class PromotionConfig(BaseModel):
    enabled: bool = True
    schedule: str = "0 9,21 * * *"


class BTwinConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    promotion: PromotionConfig = Field(default_factory=PromotionConfig)
    data_dir: Path = Field(default_factory=resolve_data_dir)


def load_config(path: Path) -> BTwinConfig:
    """Load config from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return BTwinConfig(**data)
