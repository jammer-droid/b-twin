"""Tests for btwin init and btwin mcp-proxy CLI commands."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from btwin.cli.main import app

runner = CliRunner()


def test_init_creates_mcp_json(tmp_path, monkeypatch):
    """btwin init <name> creates .mcp.json with correct content."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my-project"])
    assert result.exit_code == 0
    mcp_json = tmp_path / ".mcp.json"
    assert mcp_json.exists()
    data = json.loads(mcp_json.read_text())
    assert data["mcpServers"]["btwin"]["args"] == ["--project", "my-project"]


def test_init_auto_detect_from_directory(tmp_path, monkeypatch):
    """btwin init (no arg) falls back to cwd directory name."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    mcp_json = tmp_path / ".mcp.json"
    assert mcp_json.exists()
    data = json.loads(mcp_json.read_text())
    assert data["mcpServers"]["btwin"]["args"] == ["--project", tmp_path.name]


def test_init_auto_detect_from_git(tmp_path, monkeypatch):
    """btwin init extracts project name from git remote origin URL."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/cool-repo.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert data["mcpServers"]["btwin"]["args"] == ["--project", "cool-repo"]


def test_init_no_overwrite_without_force(tmp_path, monkeypatch):
    """Existing .mcp.json is NOT overwritten without --force, exit code 1."""
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / ".mcp.json"
    existing.write_text('{"existing": true}')
    result = runner.invoke(app, ["init", "test-project"])
    assert result.exit_code == 1
    # Original content must be intact
    assert json.loads(existing.read_text()) == {"existing": True}


def test_init_force_overwrites(tmp_path, monkeypatch):
    """--force flag overwrites existing .mcp.json."""
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / ".mcp.json"
    existing.write_text('{"existing": true}')
    result = runner.invoke(app, ["init", "new-project", "--force"])
    assert result.exit_code == 0
    data = json.loads(existing.read_text())
    assert data["mcpServers"]["btwin"]["args"] == ["--project", "new-project"]


def test_mcp_json_content_structure(tmp_path, monkeypatch):
    """Verify the full .mcp.json structure is valid for Claude Code."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "sample-project"])
    assert result.exit_code == 0
    data = json.loads((tmp_path / ".mcp.json").read_text())

    # Top-level key
    assert "mcpServers" in data
    # Server entry
    server = data["mcpServers"]["btwin"]
    assert "command" in server
    assert "args" in server
    # Command points to proxy.sh
    assert server["command"].endswith("proxy.sh")
    assert "~/.btwin/" in server["command"] or ".btwin/proxy.sh" in server["command"]
    # Args contain project binding
    assert server["args"] == ["--project", "sample-project"]


def test_init_success_message(tmp_path, monkeypatch):
    """btwin init prints a helpful success message."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my-project"])
    assert result.exit_code == 0
    assert ".mcp.json" in result.stdout
    assert "my-project" in result.stdout


def test_init_git_ssh_url(tmp_path, monkeypatch):
    """btwin init handles git SSH remote URLs (git@github.com:user/repo.git)."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:user/my-ssh-repo.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    data = json.loads((tmp_path / ".mcp.json").read_text())
    assert data["mcpServers"]["btwin"]["args"] == ["--project", "my-ssh-repo"]
