from pathlib import Path

from typer.testing import CliRunner

from btwin.cli.main import app


runner = CliRunner()


def test_sources_list_initializes_global_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    result = runner.invoke(app, ["sources", "list"])

    assert result.exit_code == 0
    assert "global" in result.stdout
    assert str((tmp_path / ".btwin").resolve()) in result.stdout


def test_sources_add_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    project_btwin = tmp_path / "project-a" / ".btwin"
    project_btwin.mkdir(parents=True)

    add = runner.invoke(app, ["sources", "add", str(project_btwin), "--name", "project-a"])
    assert add.exit_code == 0
    assert "Added source" in add.stdout

    listed = runner.invoke(app, ["sources", "list"])
    assert listed.exit_code == 0
    assert "project-a" in listed.stdout


def test_sources_scan_and_register(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    scan_root = tmp_path / "playground"
    (scan_root / "repo1" / ".btwin").mkdir(parents=True)
    (scan_root / "repo2" / ".btwin").mkdir(parents=True)

    result = runner.invoke(app, ["sources", "scan", str(scan_root), "--register"])

    assert result.exit_code == 0
    assert "Found 2 candidate" in result.stdout
    assert "Registered all discovered sources" in result.stdout

    listed = runner.invoke(app, ["sources", "list"])
    assert listed.exit_code == 0
    assert str((scan_root / "repo1" / ".btwin").resolve()) in listed.stdout
    assert str((scan_root / "repo2" / ".btwin").resolve()) in listed.stdout


def test_sources_refresh_reports_count(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    source = tmp_path / "project-b" / ".btwin"
    (source / "entries" / "2026-03-03").mkdir(parents=True)
    (source / "entries" / "2026-03-03" / "one.md").write_text("# one")

    add = runner.invoke(app, ["sources", "add", str(source), "--name", "project-b"])
    assert add.exit_code == 0

    refresh = runner.invoke(app, ["sources", "refresh"])
    assert refresh.exit_code == 0
    assert "Refreshed" in refresh.stdout

    listed = runner.invoke(app, ["sources", "list"])
    assert listed.exit_code == 0
    assert "entries: 1" in listed.stdout
