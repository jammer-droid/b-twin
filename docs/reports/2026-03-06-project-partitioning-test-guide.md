---
doc_version: 1
last_updated: 2026-03-06
status: active
---

# 프로젝트 파티셔닝 테스트 가이드

## 0) 사전 준비

```bash
cd b-twin
uv sync
```

---

## 1) 프로젝트별 저장/검색

### 자동화 테스트

```bash
uv run pytest -q tests/test_core/test_storage.py tests/test_core/test_btwin.py
uv run pytest -q tests/test_api/test_collab_api.py
uv run pytest -q tests/test_cli/test_project_cli.py
```

### 수동 검증

```bash
# API 서버 시작
uv run btwin serve-api &

# 프로젝트 지정 저장
curl -X POST http://127.0.0.1:8787/api/mcp/record \
  -H 'Content-Type: application/json' \
  -d '{"content": "test note", "topic": "test", "projectId": "my-proj"}'

# 프로젝트 스코프 검색 (해당 프로젝트만)
curl -X POST http://127.0.0.1:8787/api/mcp/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "test", "projectId": "my-proj", "scope": "project"}'

# 전체 검색
curl -X POST http://127.0.0.1:8787/api/mcp/search \
  -H 'Content-Type: application/json' \
  -d '{"query": "test", "scope": "all"}'
```

확인 포인트:
- `_global/` 아래 파일 생성 확인 (projectId 미지정 시)
- `my-proj/` 아래 파일 생성 확인 (projectId 지정 시)
- `scope: "project"` — 해당 프로젝트 결과만 반환
- `scope: "all"` — 모든 프로젝트 결과 반환

---

## 2) 마이그레이션 검증

```bash
# 테스트
uv run pytest -q tests/test_scripts/test_migrate_to_project_layout.py

# 수동 검증 (테스트 데이터로)
export BTWIN_DATA_DIR=/tmp/btwin-migration-test
mkdir -p "$BTWIN_DATA_DIR/entries/2026-03-06"
echo "test" > "$BTWIN_DATA_DIR/entries/2026-03-06/test.md"

python scripts/migrate_to_project_layout.py

# 확인: 파일이 _global/ 아래로 이동됨
ls "$BTWIN_DATA_DIR/entries/_global/2026-03-06/test.md"

# 정리
rm -rf /tmp/btwin-migration-test
```

확인 포인트:
- 기존 엔트리가 `entries/_global/` 하위로 이동
- 원본 위치에 파일 없음
- 마이그레이션 후 `btwin indexer reconcile` + `btwin indexer refresh` 정상 완료

---

## 3) MCP 프록시 연결

### 자동화 테스트

```bash
uv run pytest -q tests/test_mcp/test_proxy.py
uv run pytest -q tests/test_cli/test_project_cli.py
```

### 수동 검증

```bash
# btwin init으로 .mcp.json 생성
cd /tmp && mkdir test-proj && cd test-proj && git init
btwin init test-proj

# .mcp.json 확인
cat .mcp.json
# proxy.sh 경로, args에 --project test-proj 포함 확인

# 정리
rm -rf /tmp/test-proj
```

확인 포인트:
- `.mcp.json`에 `proxy.sh` 커맨드 경로
- `args`에 `["--project", "test-proj"]` 포함
- `btwin init` 재실행 시 덮어쓰기 확인 프롬프트

---

## 4) 프로젝트별 인덱서 상태

```bash
# API
curl http://127.0.0.1:8787/api/indexer/status?projectId=my-proj

# CLI
btwin indexer status
```

---

## 5) 전체 회귀

```bash
uv run pytest -q
```
