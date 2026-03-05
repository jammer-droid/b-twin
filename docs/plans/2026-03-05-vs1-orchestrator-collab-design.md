# VS1 상세 설계서 — Orchestrator-first Collab Framework

Date: 2026-03-05  
Status: Conditional GO (idempotency/concurrency/auth 규약 반영 완료 후 실행)
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

필수 필드(저장 시점 기준):
- `recordId: string` (서버 생성, immutable)
- `taskId: string`
- `recordType: "collab"`
- `summary: string`
- `evidence: string[]` (최소 1개)
- `nextAction: string[]` (최소 1개)
- `status: "draft" | "handed_off" | "completed"`
- `authorAgent: string` (동적 agent registry에 존재해야 함)
- `createdAt: string` (ISO-8601)
- `version: number` (상태 전이 CAS용, 생성 시 `1`)

권장 보조 필드:
- `updatedAt`, `tags`, `sourceRefs`

저장 형식:
- markdown + frontmatter
- 경로: `entries/collab/YYYY-MM-DD/<taskId>-<status>-<recordId>.md`

### 4.1 recordId 규칙

- 형식: `rec_<ULID>` (예: `rec_01JNV2N5X6WQ...`)
- 고유성: 전체 저장소 전역 unique
- API 매핑: `GET /api/collab/records/{recordId}`의 `{recordId}`는 frontmatter의 `recordId`와 동일
- 파일 매핑: 파일명 suffix와 frontmatter `recordId`가 일치해야 하며 불일치 시 데이터 무결성 오류로 처리

### 4.2 중복 생성 정책

- `POST /api/collab/records`는 `Idempotency-Key` 헤더 지원
- 동일 `Idempotency-Key` + 동일 payload 재요청: `200` + `idempotent: true`로 기존 레코드 반환
- 동일 `taskId + status + authorAgent` 조합이 이미 존재하고 payload가 다를 때: `409 DUPLICATE_RECORD`

---

## 5) 상태 전이 규칙 (VS1)

허용 전이:
- `draft -> handed_off`
- `draft -> completed` (단일 에이전트 처리 완료 시 허용)
- `handed_off -> completed`

거부 전이 예시:
- `completed -> draft`
- `completed -> handed_off`

### 5.1 멱등성 규약 (handoff/complete)

- 동일 요청 재시도 시(동일 `recordId`, 동일 목표 상태): `200` + `idempotent: true`
- 이미 목표 상태를 지났는데 역행 전이를 시도하면: `409 INVALID_STATE_TRANSITION`
- 클라이언트는 `Idempotency-Key` 헤더를 전송할 수 있고, 서버는 최근 키를 캐시해 재시도 안정성을 제공

### 5.2 동시성/원자성 규약

- 상태 전이 API는 `expectedVersion`을 반드시 받는다
- 서버는 CAS(compare-and-swap) 방식으로 원자적 전이를 수행한다
  - 조건: `currentVersion == expectedVersion`
  - 성공 시: 상태 변경 + `version += 1`
  - 실패 시: `409 CONCURRENT_MODIFICATION` + `details.currentVersion` 반환

---

## 6) HTTP API 계약 (정본)

## 6.1 Create record
`POST /api/collab/records`

Headers:
- `Idempotency-Key: <string>` (권장)

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

Response(201):
```json
{
  "recordId": "rec_01JNV2N5X6WQ...",
  "status": "draft",
  "version": 1,
  "idempotent": false
}
```

재시도 응답(200):
```json
{
  "recordId": "rec_01JNV2N5X6WQ...",
  "status": "draft",
  "version": 1,
  "idempotent": true
}
```

## 6.2 List records
`GET /api/collab/records?status=&authorAgent=&taskId=`

- UI 기본 필터: `status in [draft, handed_off]`

## 6.3 Get detail
`GET /api/collab/records/{recordId}`

- `recordId`, `version`, `frontmatter`, `content` 반환

## 6.4 Handoff gate
`POST /api/collab/handoff`

Request:
```json
{
  "recordId": "rec_01JNV2N5X6WQ...",
  "expectedVersion": 1,
  "fromAgent": "research-bot",
  "toAgent": "codex-code"
}
```

- 조건 미충족 시 4xx + 표준 에러 응답
- 성공 시 상태 `handed_off`, `version += 1`
- 동일 요청 재시도는 `200 idempotent=true`

## 6.5 Complete gate
`POST /api/collab/complete`

Request:
```json
{
  "recordId": "rec_01JNV2N5X6WQ...",
  "expectedVersion": 2,
  "actorAgent": "codex-code"
}
```

- 조건 미충족 시 4xx + 표준 에러 응답
- 성공 시 상태 `completed`, `version += 1`
- 동일 요청 재시도는 `200 idempotent=true`

## 6.6 Agent registry reload (admin)
`POST /api/admin/agents/reload`

- in-memory registry 재로딩
- 권한 필요(`main` 또는 로컬 admin token)
- 성공/실패 모두 audit 로그 기록

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
- `DUPLICATE_RECORD`
- `CONCURRENT_MODIFICATION`
- `FORBIDDEN`

---

## 8) Agent Registry 설계

소스 병합:
1. OpenClaw config (`openclaw.json`) 기반 agent 목록
2. 사용자 추가 whitelist (`extraAgents`) 병합

경로 우선순위:
1. `BTWIN_OPENCLAW_CONFIG_PATH` (env)
2. 기본 경로 fallback (`~/.openclaw/openclaw.json`)
3. CLI/UI override (요청 시 지정)

갱신 방식:
- 시작 시 1회 로드
- 수동 reload 제공:
  - CLI: `btwin agents reload`
  - HTTP: `POST /api/admin/agents/reload`

### 8.1 권한 경계 (AuthN/AuthZ)

- Gate API(`handoff`, `complete`) 호출 시 `X-Actor-Agent` 또는 body actor 필드 필수
- Gate API 호출 주체는 agent registry에 존재해야 하며, 불일치 시 `403 FORBIDDEN`
- Admin API(`agents/reload`)는 아래 중 하나만 허용
  - `actorAgent == main`(Vincent)
  - 로컬 admin token 검증 성공
- Admin/Gate 호출 결과(성공/실패)는 모두 audit 로그에 `traceId`, `actor`, `endpoint`, `result`로 기록

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
3. actor/author 권한 검증
4. 멱등성 키/재시도 판정
5. 상태 전이 유효성 검사
6. CAS(`expectedVersion`) 원자성 검사
7. 통과 시 상태 변경 + `version += 1`

실패 시:
- 상태 변경 없음
- 표준 에러 반환
- traceId 발급/로깅

재시도 규칙:
- 동일 목표 상태 재요청은 `200 + idempotent=true`
- 버전 충돌은 `409 CONCURRENT_MODIFICATION`

---

## 11) 테스트 전략 (VS1)

### Unit
- schema 검증
- 상태 전이 검증
- authorAgent/actor 권한 검증
- recordId 생성 규칙/포맷 검증
- 멱등성 키 해석 및 중복 정책 검증

### API
- create/list/detail 성공 케이스
- create 재시도 idempotent 케이스(동일 Idempotency-Key)
- 동일 taskId+status 중복 생성 충돌 케이스(`409 DUPLICATE_RECORD`)
- handoff/complete gate reject 케이스
- handoff/complete CAS 충돌 케이스(`409 CONCURRENT_MODIFICATION`)
- reload API 권한 검증(`403 FORBIDDEN`) + 성공 케이스

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
4. handoff/complete 멱등성 + CAS 충돌 규약이 테스트로 검증됨
5. `recordId` 생성/매핑 규약이 API/저장소/테스트에서 일관됨
6. UI가 목록/상세/필터/거절 사유(`traceId` 포함)를 표시
7. agent registry 동적 검증 + reload(HTTP/CLI) 권한 규칙이 동작
8. 에러 표준(`errorCode/message/details/traceId`) 일관 적용

---

## 13) 리스크 및 완화

- 리스크: OpenClaw config 경로/형식 차이
  - 완화: env override + fallback + 명시적 에러
- 리스크: 중복 요청/재시도로 인한 중복 레코드
  - 완화: `Idempotency-Key` + `DUPLICATE_RECORD` 정책 고정
- 리스크: 동시 전이 요청 경합(레이스 컨디션)
  - 완화: `expectedVersion` 기반 CAS + `CONCURRENT_MODIFICATION` 응답
- 리스크: admin/gate API 오남용
  - 완화: actor 검증 + admin token + audit 로그
- 리스크: UI와 API 계약 불일치
  - 완화: API schema fixture + contract test

---

## 14) 구현 순서 (VS1 권장)

1. schema + state machine + `recordId` 규칙 고정
2. storage path + create/list/detail API
3. create 중복/멱등성(`Idempotency-Key`) 정책 구현
4. gate API(handoff/complete) + `expectedVersion` CAS 구현
5. agent registry + reload (CLI/HTTP) + 권한 경계 구현
6. UI 목록/상세/필터 + reject reason/traceId 표시
7. 통합 테스트/회귀(중복/경합/권한 케이스 포함)

---

이 문서는 VS1 구현 시 단일 기준 문서(SSOT)로 사용한다.
