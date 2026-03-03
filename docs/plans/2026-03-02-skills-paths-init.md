# Skills Layer, Dynamic Paths & Init Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add MCP wrapper skills for explicit tool invocation, flexible data paths, and a `btwin init` command that replaces hardcoded config.

**Architecture:** (1) Bundle SKILL.md templates in `src/btwin/skills/` for Claude Code integration. (2) Add env var and per-project data path support to config. (3) Add `btwin init` CLI command that generates `.mcp.json` and copies skills to any project.

**Tech Stack:** Python, Typer CLI, YAML, importlib.resources (for bundled files)

---

### Task 1: Create MCP Wrapper Skills (SKILL.md templates)

Create 4 skill template files bundled with the btwin package. These are Claude Code skill definitions that instruct Claude to use specific MCP tools explicitly.

**Files:**
- Create: `src/btwin/skills/btwin-record/SKILL.md`
- Create: `src/btwin/skills/btwin-search/SKILL.md`
- Create: `src/btwin/skills/btwin-save/SKILL.md`
- Create: `src/btwin/skills/btwin-status/SKILL.md`
- Create: `src/btwin/skills/__init__.py` (empty, makes it a package for importlib)

**Step 1: Create `src/btwin/skills/__init__.py`**

```python
```

(Empty file — just makes skills a package so importlib.resources can find it.)

**Step 2: Create `src/btwin/skills/btwin-record/SKILL.md`**

```markdown
---
name: btwin-record
description: Use when the user wants to save a note, thought, or piece of information to B-TWIN for future retrieval
---

# B-TWIN Record

현재 대화에서 중요한 내용을 B-TWIN에 기록합니다.

## When to Use

- 사용자가 "기록해줘", "저장해줘", "메모해줘" 등을 요청할 때
- `/btwin-record` 실행 시

## Workflow

1. 사용자의 요청에서 기록할 핵심 내용을 추출
2. 적절한 topic slug 결정 (예: "career-ta", "unreal-study")
3. `btwin_record` MCP 도구를 호출하여 저장

## Steps

1. **내용 정리**: 대화에서 기록할 핵심 내용을 마크다운으로 정리
   - 사용자의 생각, 결정, 학습 내용 위주
   - 간결하되 나중에 검색했을 때 맥락을 알 수 있도록
2. **토픽 결정**: 내용에 맞는 topic slug 생성 (영문 소문자, 하이픈 구분)
3. **MCP 도구 호출**: `btwin_record(content=정리된_내용, topic=토픽_슬러그)` 호출
4. **결과 확인**: 저장 경로를 사용자에게 알려줌

## Rules

- 반드시 `btwin_record` MCP 도구를 사용할 것
- topic은 영문 소문자와 하이픈만 사용 (예: "shader-study", "career-plan")
- 내용은 한국어로 작성
```

**Step 3: Create `src/btwin/skills/btwin-search/SKILL.md`**

```markdown
---
name: btwin-search
description: Use when the user wants to search past records, memories, or notes stored in B-TWIN
---

# B-TWIN Search

B-TWIN에 저장된 과거 기록을 시맨틱 검색합니다.

## When to Use

- 사용자가 "검색해줘", "찾아줘", "전에 뭐라고 했었지?" 등을 요청할 때
- `/btwin-search` 실행 시

## Workflow

1. 사용자의 질문에서 검색 쿼리 추출
2. `btwin_search` MCP 도구로 검색
3. 결과를 정리하여 사용자에게 전달

## Steps

1. **쿼리 구성**: 사용자의 질문에서 핵심 키워드나 의미를 추출하여 검색 쿼리 작성
2. **MCP 도구 호출**: `btwin_search(query=검색_쿼리, n_results=5)` 호출
3. **결과 정리**: 검색 결과를 읽기 쉽게 정리하여 제시
   - 날짜와 토픽 포함
   - 관련 내용 요약

## Rules

- 반드시 `btwin_search` MCP 도구를 사용할 것
- 검색 결과가 없으면 사용자에게 명확히 알려줌
- 결과가 여러 개면 가장 관련성 높은 것부터 정리
```

**Step 4: Create `src/btwin/skills/btwin-save/SKILL.md`**

```markdown
---
name: btwin-save
description: Use when the user wants to save and end the current conversation session in B-TWIN
---

# B-TWIN Save Session

현재 대화 세션을 요약하고 B-TWIN에 저장합니다.

## When to Use

- 사용자가 "대화 저장해줘", "세션 끝내줘", "마무리하자" 등을 요청할 때
- `/btwin-save` 실행 시

## Workflow

1. 현재 대화 내용을 요약
2. 적절한 slug 생성
3. `btwin_end_session` MCP 도구로 저장

## Steps

1. **세션 상태 확인**: `btwin_session_status()` 호출하여 활성 세션 확인
2. **대화 요약**: 현재 대화의 핵심 내용을 마크다운 bullet point로 요약
   - 주요 논의 사항
   - 결정된 내용
   - 다음 단계 (있다면)
3. **Slug 생성**: 대화 주제를 반영하는 영문 slug 생성 (예: "career-ta-discussion")
4. **MCP 도구 호출**: `btwin_end_session(summary=요약_내용, slug=슬러그)` 호출
5. **결과 확인**: 저장 경로와 요약 내용을 사용자에게 알려줌

## Rules

- 반드시 `btwin_end_session` MCP 도구를 사용할 것
- summary는 한국어로, slug는 영문 소문자+하이픈으로
- 세션이 없으면 사용자에게 알려줌
```

**Step 5: Create `src/btwin/skills/btwin-status/SKILL.md`**

```markdown
---
name: btwin-status
description: Use when the user wants to check B-TWIN session status or see what's currently being tracked
---

# B-TWIN Status

현재 B-TWIN 세션 상태를 확인합니다.

## When to Use

- 사용자가 "세션 상태", "지금 기록 중이야?", "btwin 상태" 등을 물을 때
- `/btwin-status` 실행 시

## Steps

1. **MCP 도구 호출**: `btwin_session_status()` 호출
2. **결과 전달**: 세션 활성 여부, 토픽, 메시지 수, 시작 시간을 사용자에게 알려줌
3. **추가 안내**: 세션이 없으면 `btwin_start_session`으로 시작할 수 있다고 안내

## Rules

- 반드시 `btwin_session_status` MCP 도구를 사용할 것
```

**Step 6: Commit**

```bash
cd /Users/home/playground/btwin-service
git add src/btwin/skills/
git commit -m "feat: add MCP wrapper skill templates (record, search, save, status)"
```

---

### Task 2: Add Data Path Options (env var + per-project)

Add environment variable support and per-project data directory detection to the config system.

**Precedence (highest to lowest):**
1. `BTWIN_DATA_DIR` environment variable
2. Per-project `.btwin/` directory (if `.btwin/` exists in CWD)
3. Global default `~/.btwin/`

**Files:**
- Modify: `src/btwin/config.py`
- Modify: `src/btwin/mcp/server.py` (update `_get_twin` to use new resolution)
- Test: `tests/test_core/test_config.py`

**Step 1: Write the failing tests**

In `tests/test_core/test_config.py`, add:

```python
import os
from btwin.config import resolve_data_dir


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
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_core/test_config.py -v`
Expected: FAIL (resolve_data_dir not found)

**Step 3: Implement `resolve_data_dir`**

In `src/btwin/config.py`, add:

```python
import os

def resolve_data_dir() -> Path:
    """Resolve data directory with precedence: env var > project-local > global default."""
    # 1. Environment variable (highest priority)
    env_dir = os.environ.get("BTWIN_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    # 2. Per-project .btwin/ directory
    project_dir = Path.cwd() / ".btwin"
    if project_dir.is_dir():
        return project_dir

    # 3. Global default
    return Path.home() / ".btwin"
```

Update `BTwinConfig` default:

```python
class BTwinConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: LLMConfig = Field(default_factory=LLMConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    data_dir: Path = Field(default_factory=resolve_data_dir)
```

**Step 4: Update MCP server config resolution**

In `src/btwin/mcp/server.py`, update `_get_twin()`:

```python
def _get_twin() -> BTwin:
    global _twin
    if _twin is None:
        config_path = Path.home() / ".btwin" / "config.yaml"
        if config_path.exists():
            config = load_config(config_path)
        else:
            config = BTwinConfig()
        # Also check project-local config
        project_config = Path.cwd() / ".btwin" / "config.yaml"
        if project_config.exists() and project_config != config_path:
            config = load_config(project_config)
        _twin = BTwin(config)
    return _twin
```

**Step 5: Run tests**

Run: `cd /Users/home/playground/btwin-service && uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
cd /Users/home/playground/btwin-service
git add src/btwin/config.py src/btwin/mcp/server.py tests/test_core/test_config.py
git commit -m "feat: add data path resolution (env var, per-project, global default)"
```

---

### Task 3: Add `btwin init` CLI Command

Add a CLI command that generates `.mcp.json` and copies skills to any project directory. This replaces the hardcoded path approach.

**Files:**
- Modify: `src/btwin/cli/main.py` (add `init` command)
- Test: `tests/test_cli/test_init.py`

**Step 1: Write the failing tests**

Create `tests/test_cli/__init__.py` (empty) and `tests/test_cli/test_init.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch

from btwin.cli.main import _generate_mcp_config, _get_skills_dir


def test_generate_mcp_config_with_uv():
    """Generates config using uv when btwin is not globally installed."""
    config = _generate_mcp_config(service_dir="/path/to/btwin-service")
    parsed = json.loads(config)
    assert "btwin" in parsed["mcpServers"]
    server = parsed["mcpServers"]["btwin"]
    assert server["command"] == "uv"
    assert "/path/to/btwin-service" in server["args"]
    assert "serve" in server["args"]


def test_generate_mcp_config_global():
    """Generates config using btwin directly when globally installed."""
    config = _generate_mcp_config(service_dir=None)
    parsed = json.loads(config)
    server = parsed["mcpServers"]["btwin"]
    assert server["command"] == "btwin"
    assert server["args"] == ["serve"]


def test_get_skills_dir():
    """Skills directory exists in the package."""
    skills_dir = _get_skills_dir()
    assert skills_dir.is_dir()
    assert (skills_dir / "btwin-record" / "SKILL.md").exists()


def test_init_creates_files(tmp_path):
    """Init command creates .mcp.json and .claude/skills/ in target dir."""
    from typer.testing import CliRunner
    from btwin.cli.main import app

    runner = CliRunner()
    result = runner.invoke(app, ["init", "--target", str(tmp_path)])
    assert result.exit_code == 0

    # Check .mcp.json created
    mcp_json = tmp_path / ".mcp.json"
    assert mcp_json.exists()
    config = json.loads(mcp_json.read_text())
    assert "btwin" in config["mcpServers"]

    # Check skills copied
    skills_dir = tmp_path / ".claude" / "skills"
    assert (skills_dir / "btwin-record" / "SKILL.md").exists()
    assert (skills_dir / "btwin-search" / "SKILL.md").exists()
    assert (skills_dir / "btwin-save" / "SKILL.md").exists()
    assert (skills_dir / "btwin-status" / "SKILL.md").exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_cli/test_init.py -v`
Expected: FAIL

**Step 3: Implement**

In `src/btwin/cli/main.py`, add:

```python
import json
import shutil
from importlib import resources


def _get_skills_dir() -> Path:
    """Get the path to bundled skill templates."""
    return Path(resources.files("btwin.skills"))


def _generate_mcp_config(service_dir: str | None = None) -> str:
    """Generate .mcp.json content."""
    if service_dir:
        server_config = {
            "command": "uv",
            "args": ["--directory", service_dir, "run", "btwin", "serve"],
        }
    else:
        server_config = {
            "command": "btwin",
            "args": ["serve"],
        }
    return json.dumps({"mcpServers": {"btwin": server_config}}, indent=2)


@app.command()
def init(
    target: str = typer.Option(".", help="Target project directory"),
    service_dir: str = typer.Option(None, help="Path to btwin-service (for uv mode). If omitted, assumes global install."),
):
    """Initialize B-TWIN in a project — generates .mcp.json and installs skills."""
    target_path = Path(target).resolve()

    # 1. Generate .mcp.json
    mcp_config = _generate_mcp_config(service_dir=service_dir)
    mcp_path = target_path / ".mcp.json"
    mcp_path.write_text(mcp_config + "\n")
    console.print(f"[green]Created {mcp_path}[/green]")

    # 2. Copy skills
    skills_src = _get_skills_dir()
    skills_dest = target_path / ".claude" / "skills"
    for skill_dir in skills_src.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            dest = skills_dest / skill_dir.name
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(skill_dir / "SKILL.md", dest / "SKILL.md")
            console.print(f"  [dim]Installed skill: /{skill_dir.name}[/dim]")

    console.print(f"\n[bold green]B-TWIN initialized in {target_path}[/bold green]")
    console.print("[dim]Open a new Claude Code session to use B-TWIN tools and skills.[/dim]")
```

**Step 4: Run tests**

Run: `cd /Users/home/playground/btwin-service && uv run pytest tests/test_cli/test_init.py -v`
Then: `cd /Users/home/playground/btwin-service && uv run pytest -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
cd /Users/home/playground/btwin-service
git add src/btwin/cli/main.py tests/test_cli/__init__.py tests/test_cli/test_init.py
git commit -m "feat: add btwin init command for project setup (MCP config + skills)"
```

---

### Task 4: Update b-twin project with `btwin init`

Run `btwin init` on the b-twin project to replace the hardcoded `.mcp.json` and install the new skills.

**Files:**
- Modify: `/Users/home/playground/b-twin/.mcp.json` (regenerated)
- Create: `/Users/home/playground/b-twin/.claude/skills/btwin-record/SKILL.md`
- Create: `/Users/home/playground/b-twin/.claude/skills/btwin-search/SKILL.md`
- Create: `/Users/home/playground/b-twin/.claude/skills/btwin-save/SKILL.md`
- Create: `/Users/home/playground/b-twin/.claude/skills/btwin-status/SKILL.md`

**Step 1: Run btwin init**

```bash
cd /Users/home/playground/btwin-service && uv run btwin init \
  --target /Users/home/playground/b-twin \
  --service-dir /Users/home/playground/btwin-service
```

**Step 2: Verify .mcp.json**

```bash
cat /Users/home/playground/b-twin/.mcp.json
```

Expected: Same content as before but generated by the init command.

**Step 3: Verify skills installed**

```bash
ls /Users/home/playground/b-twin/.claude/skills/btwin-*/SKILL.md
```

Expected: 4 skill files present.

**Step 4: Commit in b-twin repo**

```bash
cd /Users/home/playground/b-twin
git add .mcp.json .claude/skills/btwin-*/SKILL.md
git commit -m "feat: add B-TWIN MCP skills and regenerate .mcp.json via btwin init"
```
