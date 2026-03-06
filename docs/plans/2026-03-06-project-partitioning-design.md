---
doc_version: 1
last_updated: 2026-03-06
status: approved
---

# Project Partitioning Design

**Date:** 2026-03-06
**Status:** Approved

## Goal

B-TWIN을 여러 프로젝트에 걸쳐 사용할 때, 하나의 중앙 저장소(`~/.btwin/`)에서 프로젝트별로 데이터를 분리 저장/검색하는 구조를 만든다.

## 핵심 결정 사항

1. **경로 기반 파티셔닝** — `entries/{project}/{date}/{slug}.md`
2. **서버 바인딩** — LLM이 아닌 서버가 프로젝트를 강제
3. **마스터/프록시 구조** — 하나의 API 서버 + 경량 MCP 프록시
4. **검색** — 현재 프로젝트 우선, 옵션으로 전체 크로스 검색
5. **기존 데이터** — `_global` 프로젝트로 마이그레이션

## 아키텍처

### 마스터/프록시 구조

```
Bot Main     → MCP Proxy (project=main)       ─┐
Bot Research → MCP Proxy (project=research)    ─┼→ B-TWIN HTTP API (localhost:8787)
Bot Code     → MCP Proxy (project=code)        ─┤    (단일 프로세스, 상시 실행)
Claude Code  → MCP Proxy (project=btwin-svc)   ─┘
```

**마스터 (btwin serve-api):**
- 기존 FastAPI 서버. 하나만 상시 실행.
- 모든 저장, 검색, 인덱싱, 대시보드 담당.
- API 엔드포인트에 `project` 파라미터 추가.

**프록시 (btwin mcp-proxy):**
- 프로젝트별로 실행되는 초경량 MCP 서버.
- ChromaDB, 인덱서 등 무거운 의존성 없음 (`httpx` + `mcp`만 사용).
- 하는 일: MCP 도구 호출 → `project` 붙여서 HTTP 마스터에 전달 → 응답 반환.
- LLM은 `project` 파라미터를 모름. 프록시가 서버 시작 시점에 고정.

```bash
# 마스터 (1개, 상시)
btwin serve-api --port 8787

# 프록시 (클라이언트당 1개, 경량)
btwin mcp-proxy --project main --backend http://localhost:8787
btwin mcp-proxy --project research --backend http://localhost:8787
```

### 저장 구조

```
~/.btwin/entries/
  _global/                        ← 프로젝트 미지정 시 기본 폴백
    2026-03-06/slug.md
    convo/2026-03-06/slug.md
    collab/2026-03-06/slug.md
  btwin-service/
    2026-03-06/slug.md
    convo/2026-03-06/slug.md
    collab/2026-03-06/slug.md
  unity-project/
    ...
```

**규칙:**
- 모든 엔트리는 `entries/{project}/` 하위에 저장
- project 미설정 시 `_global` 사용
- 프론트매터에 `project` 필드 추가
- doc_id = `entries/{project}/{date}/{slug}.md` 또는 `entries/{project}/convo/{date}/{slug}.md`
- entry, convo, collab 모두 프로젝트별 분리
- 프로젝트 디렉토리는 첫 사용 시 자동 생성

### 검색 동작

- **기본:** 현재 프로젝트만 검색 (벡터 메타데이터 필터)
- **전체:** `scope="all"` 옵션으로 크로스 프로젝트 검색
- 벡터 인덱스는 단일 ChromaDB 컬렉션 유지, `project` 메타데이터 필드로 필터링
- 인덱서 매니페스트에 `project` 필드 추가

### 프로젝트 세팅 방법

**Claude Code 프로젝트:**
```bash
cd my-project
btwin init              # git repo명 자동 감지, .mcp.json 생성
btwin init my-project   # 명시적 이름 지정
```

생성되는 `.mcp.json`:
```json
{
  "mcpServers": {
    "btwin": {
      "command": "~/.btwin/proxy.sh",
      "args": ["--project", "my-project"]
    }
  }
}
```

**OpenClaw 봇 워크스페이스:**
```yaml
mcp_servers:
  btwin:
    command: ~/.btwin/proxy.sh
    args: [--project, main]
```

봇 워크스페이스 설정에 직접 지정. `btwin init` 불필요.

### 마이그레이션

기존 엔트리(25개)를 `_global` 프로젝트로 이동:
- `entries/{date}/{slug}.md` → `entries/_global/{date}/{slug}.md`
- `entries/convo/` → `entries/_global/convo/`
- `entries/collab/` → `entries/_global/collab/`
- 매니페스트 doc_id 갱신
- 벡터 인덱스 재인덱싱 (`reconcile` + `refresh`)

## 변경 범위

| 영역 | 변경 내용 |
|------|----------|
| Storage | `save_entry` 등 경로 생성에 project 삽입 |
| Indexer | 매니페스트 IndexEntry에 `project` 필드 추가 |
| Vector | 메타데이터에 `project` 추가, 검색 시 필터 지원 |
| HTTP API | 엔드포인트에 `project` 파라미터 추가 |
| MCP Proxy | 신규 — 경량 프록시 서버 (`btwin mcp-proxy`) |
| CLI | `btwin init` 명령 추가 |
| install.sh | `proxy.sh` 래퍼 생성 추가 |
| 마이그레이션 | 기존 엔트리 `_global`로 이동 스크립트 |
| 문서 | README, runbook에 프로젝트 파티셔닝 사용법 추가 |

## 의도적으로 포함하지 않는 것

- 프로젝트별 벡터 컬렉션 분리 (단일 컬렉션 + 메타데이터 필터로 충분)
- 프로젝트 권한/접근 제어
- 프로젝트 간 데이터 이동 도구
- 프록시 자동 시작/관리 데몬
