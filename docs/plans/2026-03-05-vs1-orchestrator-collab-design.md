# VS1 상세 설계서 — Orchestrator-first Collab Framework

Date: 2026-03-05  
Status: Approved for VS1 execution
Related:
- `docs/plans/2026-03-05-orchestrator-first-collab-framework.md`
- `docs/dashboard-implementation-spec.md`

---

## 1) 목표

VS1의 목표는 다음 2가지를 동시에 만족하는 것이다.

1. **협업 기록 강제**: handoff/complete 시점에 collab 레코드가 없으면 진행 차단
2. **운영 가시성 확보**: 최소 UI에서 collab 상태(진행중 우선)와 거절 사유를 즉시 확인

---

## 2) 범위 (VS1 확정)

### In Scope
- HTTP API 정본 계약 정의/구현
- MCP는 HTTP/엔진 계약을 호출하는 adapter 역할만 수행
- collab 스키마(B) 강제
- hard gate (handoff + complete) 차단 동작
- UI: 목록 + 상세 + 상태 필터 + 거절 사유 표시
- authorAgent 동적 레지스트리 검증
- agents reload: CLI + HTTP 둘 다 제공

### Out of Scope (VS1 제외)
- promotion queue 본 구현
- global 승격 배치 워커
- convo 고도화(명시기록 강제 정책 고급화)
- watcher 기반 자동 레지스트리 갱신

---

## 3) 핵심 설계 원칙

1. **API-first contract**
   - 프레임워크/웹은 외부 계약(HTTP schema)을 기준으로 개발
2. **Adapter 흡수**
   - 엔진 내부 변경은 adapter/facade에서 흡수, API 계약은 유지
3. **정책 분리**
   - 엔진은 데이터 처리 중심, 강제 정책은 프레임워크(게이트) 레이어에서 관리
4. **작업 상태와 승격 상태 분리**
   - collab 상태: `draft -> handed_off -> completed`
   - 승격은 별도 트랙(이 문서의 VS1 범위 밖)

---

## 4) 데이터 계약 (Collab Record Schema B)

필수 필드:
- `taskId: string`
- `recordType: "collab"`
- `summary: string`
- `evidence: string[]` (최소 1개)
- `nextAction: string[]` (최소 1개)
- `status: "draft" | "handed_off" | "completed"`
- `authorAgent: string` (동적 agent registry에 존재해야 함)
- `createdAt: string` (ISO-8601)

권장 보조 필드:
- `updatedAt`, `tags`, `sourceRefs`

저장 형식:
- markdown + frontmatter
- 경로: `entries/collab/YYYY-MM-DD/<taskId>-<status>-<id>.md`

---

## 5) 상태 전이 규칙 (VS1)

허용 전이:
- `draft -> handed_off`
- `draft -> completed` (단일 에이전트 처리 완료 시 허용)
- `handed_off -> completed`

거부 전이 예시:
- `completed -> draft`
- `completed -> handed_off`

---

## 6) HTTP API 계약 (정본)

## 6.1 Create record
`POST /api/collab/records`

Request:
```json
{
  "taskId": "jeonse-e2e-001",
  "recordType": "collab",
  "summary": "E2E 서버 충돌 원인 파악 및 수정",
  "evidence": ["tsx integration 11/11 pass"],
  "nextAction": ["CI 스크립트 정리"],
  "status": "draft",
  "authorAgent": "codex-code",
  "createdAt": "2026-03-05T15:54:00+09:00"
}
```

## 6.2 List records
`GET /api/collab/records?status=&authorAgent=&taskId=`

- UI 기본 필터: `status in [draft, handed_off]`

## 6.3 Get detail
`GET /api/collab/records/{recordId}`

## 6.4 Handoff gate
`POST /api/collab/handoff`

- 조건 미충족 시 4xx + 표준 에러 응답
- 성공 시 상태 `handed_off`

## 6.5 Complete gate
`POST /api/collab/complete`

- 조건 미충족 시 4xx + 표준 에러 응답
- 성공 시 상태 `completed`

## 6.6 Agent registry reload (admin)
`POST /api/admin/agents/reload`

- in-memory registry 재로딩

---

## 7) 에러 응답 표준

모든 4xx/5xx는 아래 구조 사용:

```json
{
  "errorCode": "GATE_REJECTED",
  "message": "collab record required before handoff",
  "details": {
    "taskId": "jeonse-e2e-001",
    "required": ["recordId", "status"]
  },
  "traceId": "trc_01J..."
}
```

대표 에러 코드:
- `INVALID_SCHEMA`
- `INVALID_AUTHOR_AGENT`
- `INVALID_STATE_TRANSITION`
- `GATE_REJECTED`
- `RECORD_NOT_FOUND`

---

## 8) Agent Registry 설계

소스 병합:
1. OpenClaw config (`openclaw.json`) 기반 agent 목록
2. 사용자 추가 whitelist (`extraAgents`) 병합

경로 우선순위:
1. `BTWIN_OPENCLOW_CONFIG_PATH` (env)
2. 기본 경로 fallback (`~/.openclaw/openclaw.json`)
3. CLI/UI override (요청 시 지정)

갱신 방식:
- 시작 시 1회 로드
- 수동 reload 제공:
  - CLI: `btwin agents reload`
  - HTTP: `POST /api/admin/agents/reload`

---

## 9) UI 요구사항 (VS1)

페이지: `Collab`

필수 UI 요소:
1. **목록 테이블**
   - 컬럼: `taskId`, `status`, `authorAgent`, `createdAt`
2. **상태 필터**
   - `draft`, `handed_off`, `completed`, `all`
   - 기본값: `draft + handed_off`
3. **상세 패널**
   - `summary`, `evidence`, `nextAction`, raw frontmatter
4. **게이트 거절 피드백**
   - 에러 `message` + `traceId` 표시

---

## 10) 하드 게이트 동작 정의

handoff/complete 요청 시 검사 순서:
1. schema 유효성 검사
2. record 존재 검사
3. authorAgent 검증
4. 상태 전이 유효성 검사
5. 통과 시 상태 변경

실패 시:
- 상태 변경 없음
- 표준 에러 반환
- traceId 발급/로깅

---

## 11) 테스트 전략 (VS1)

### Unit
- schema 검증
- 상태 전이 검증
- authorAgent 검증

### API
- create/list/detail 성공 케이스
- handoff/complete gate reject 케이스
- reload API 동작

### UI
- 진행중 기본 필터 동작
- 상세 패널 렌더링
- gate reject 메시지 + traceId 표시

### E2E(경량)
- 레코드 없는 handoff/complete -> 차단
- 레코드 생성 후 handoff/complete -> 성공

---

## 12) VS1 완료 조건 (DoD)

아래가 모두 충족되면 VS1 완료:

1. HTTP 정본 API 6개 구현 및 테스트 통과
2. MCP adapter가 동일 계약으로 동작
3. hard gate가 handoff/complete에서 실제 차단
4. UI가 목록/상세/필터/거절 사유를 표시
5. agent registry 동적 검증 + reload(HTTP/CLI) 동작
6. 에러 표준(`errorCode/message/details/traceId`) 일관 적용

---

## 13) 리스크 및 완화

- 리스크: OpenClaw config 경로/형식 차이
  - 완화: env override + fallback + 명시적 에러
- 리스크: 상태 전이 누락으로 인한 운영 혼선
  - 완화: 서버 단 전이 테이블 강제
- 리스크: UI와 API 계약 불일치
  - 완화: API schema fixture + contract test

---

## 14) 구현 순서 (VS1 권장)

1. schema + state machine
2. storage path + create/list/detail API
3. gate API(handoff/complete)
4. agent registry + reload (CLI/HTTP)
5. UI 목록/상세/필터
6. reject reason + traceId 표시
7. 통합 테스트/회귀

---

이 문서는 VS1 구현 시 단일 기준 문서(SSOT)로 사용한다.
