# 운영 모드 아키텍처 및 Core Ports 명세 (P0-1)

## 1) 배경/문제정의
현재 B-TWIN 런타임은 OpenClaw 결합 실행과 단독 실행 시 경계가 불명확해, 동일 이벤트가 서로 다른 저장/승인/감사 경로를 타면서 정합성 편차가 발생할 수 있다. 특히 네트워크 단절·재기동·버전 불일치 상황에서 동기화 공백이 누적되면, 사용자 관점의 "동작은 했는데 기록이 없다" 또는 "기록은 있는데 승인 근거가 없다" 문제가 생긴다.

본 문서는 운영 모드를 명시적으로 분리하고, 모드와 무관하게 동일하게 지켜야 할 코어 인터페이스(Ports) 및 불변조건을 정의하여, 향후 어댑터 교체/확장 시에도 데이터 신뢰성과 감사 가능성을 유지하는 것을 목표로 한다. 정책 준수/감사 추적 무결성이 약한 환경에서는 위험도 상승으로 간주하고 추가 승인 제약을 적용한다.

### 용어 표준 규칙
- 첫 등장 시에만 한/영 병기(예: 정합성(Consistency)), 이후 한국어 우선 사용
- 코드 식별자/상태값(`mark_pending`, `PENDING`, `append-only`)은 코드 표기를 유지
- 감사 관련 용어는 `감사 추적`으로 통일하고, 괄호로 `Audit trail`을 1회만 병기
- 용어 선호도:
  - Preferred: 정합성/무결성/책임성/감사 추적
  - Allowed(첫 등장 한정): Consistency/Integrity/Accountability/Audit trail
  - Deprecated: 동일 개념을 혼합 표기로 반복 병기하는 방식

## 2) 모드 정의 (OpenClaw 결합형 vs B-TWIN 단독형)

### A. OpenClaw 결합형
- 정의: OpenClaw 런타임(세션/도구/메시징 인프라)과 연동하여 B-TWIN 코어를 실행하는 모드
- 사용 맥락: 다중 채널 상호작용, 외부 도구 호출, 중앙 감사/운영 관제 필요 환경
- 장점: 풍부한 도구 접근성, 운영 가시성, 중앙 정책 집행 용이
- 제약: 외부 런타임 상태/권한 정책에 일부 의존

### B. B-TWIN 단독형
- 정의: OpenClaw 의존성을 최소화하고 B-TWIN 코어+로컬/직접 어댑터로 독립 실행하는 모드
- 사용 맥락: 오프라인/폐쇄망, 경량 배포, 특정 임베디드·온디바이스 환경
- 장점: 배포 단순성, 독립성, 의존성 축소
- 제약: 중앙 운영 기능(중앙 감사 추적/알림/도구 생태계) 제한 가능

## 3) 공통 코어 불변조건 (정합성/무결성/책임성)
모든 모드에서 아래 불변조건은 반드시 동일하게 만족해야 한다.

1. 정합성(Consistency)
   - 동일 입력 이벤트는 모드와 무관하게 동일 상태 전이를 생성해야 한다.
   - 이벤트 처리 결과는 idempotent key 기준 중복 적용이 금지된다.
2. 무결성(Integrity)
   - 상태 변경은 검증 가능한 버전(doc_version)과 체크섬(checksum)을 동반한다.
   - 승인 필요 액션은 승인 증적 없이 커밋될 수 없다.
3. 책임성(Accountability)
   - 모든 결정/변경은 감사 추적(Audit trail)으로 재현 가능해야 한다.
   - "누가/무엇이/언제/왜"를 재구성할 메타데이터를 누락 없이 남긴다.

## 4) Core Ports 명세

### 4.1 RecallPort
- 목적: 컨텍스트/기억 조회 및 저장 추상화
- 최소 연산:
  - `recall(query, scope, limit) -> RecallResult[]`
  - `remember(entry, tags, source, timestamp) -> MemoryRef`
- 계약:
  - 조회 결과는 `source`, `confidence`, `version` 메타 포함
  - 저장 시 `doc_version` 증가 규칙 준수

### 4.2 IdentityPort
- 목적: 주체(사용자/에이전트/시스템) 식별·역할 확인
- 최소 연산:
  - `resolve_subject(subject_hint) -> Subject`
  - `authorize(subject, action, resource) -> AuthorizationDecision`
- 계약:
  - 모든 결정에 `policy_id`, `decision_reason`, `ttl` 포함
  - 익명/불명 주체는 기본 거부(deny-by-default)

### 4.3 ApprovalPort
- 목적: 고위험/외부영향 액션에 대한 승인 워크플로
- 최소 연산:
  - `request_approval(action, risk_level, context) -> ApprovalTicket`
  - `get_approval(ticket_id) -> ApprovalStatus`
  - `record_approval_decision(ticket_id, approver, decision, reason)`
- 계약:
  - 승인 상태는 `PENDING|APPROVED|REJECTED|EXPIRED`
  - `APPROVED` 이전 최종 실행(commit) 금지

### 4.4 AuditPort
- 목적: 이벤트/상태변경/승인 결과의 불변 감사 로그 기록
- 최소 연산:
  - `append(event_type, payload, actor, trace_id, doc_version, checksum)`
  - `query(trace_id|time_range|actor|event_type)`
  - `verify_integrity(range) -> VerificationReport`
- 계약:
  - 로그 append-only 원칙
  - 검증 실패 항목은 `repair` 대상 큐에 자동 등록

## 5) 모드별 Adapter 매핑표

| Core Port | OpenClaw 결합형 Adapter | B-TWIN 단독형 Adapter | 비고 |
|---|---|---|---|
| RecallPort | OpenClaw Session/Memory Adapter | Local Store Adapter (SQLite/파일 기반) | 스키마는 동일 계약 유지 |
| IdentityPort | OpenClaw Auth/Policy Adapter | Local RBAC Adapter | 정책 해석기는 동일 규칙셋 공유 |
| ApprovalPort | OpenClaw Human-in-the-loop Adapter | Local Approval Queue Adapter | 단독형은 오프라인 승인 큐 지원 |
| AuditPort | OpenClaw Audit Sink Adapter | Local Append-only Log Adapter | 해시 체인/체크섬 규칙 공통 |

## 6) 상태 전이/동기화 공백 처리 시퀀스
동기화 공백(네트워크 단절, 프로세스 재시작, 버전 충돌) 발생 시 표준 시퀀스:

1. `mark_pending`
   - 미확정 변경을 pending 상태로 표시, 사용자 가시 상태와 내부 상태를 분리
2. `refresh`
   - 현재 원천(로컬/원격) 스냅샷 재조회, 최신 `doc_version` 확보
3. `reconcile`
   - 이벤트 로그와 문서 상태를 대조해 누락/중복/충돌 계산
4. `repair`
   - 정책 기반 자동 복구(재적용/롤포워드/보정 기록), 불가 시 수동 승인 경로 이관
5. `checksum`
   - 복구 결과의 체크섬 재계산 및 기준값 갱신
6. `doc_version`
   - 복구 커밋 후 문서 버전 단조 증가 보장, 감사 로그에 전이 이력 기록

### 시퀀스 규칙
- `reconcile` 이전 사용자 완료 응답 금지
- `repair`는 원본 로그를 덮어쓰지 않고 보정 이벤트를 추가
- 실패 시 재시도 한계 초과 항목은 격리 큐로 이동 후 승인 대기
- 격리 큐 항목은 T+30분 이내 담당자 알림을 발행하고 수동 승인 상태로 전환

## 7) 보안/권한 정책
- 기본 원칙: 최소권한(Least Privilege), 기본거부(Deny by Default), 명시적 승인(Explicit Approval)
- 데이터 보호:
  - 민감 필드는 저장 전 마스킹/암호화
  - 감사 로그는 변조 탐지(체크섬/해시 체인) 적용
- 실행 권한:
  - 외부 영향 액션(메시지 발송, 파일 파괴적 변경, 외부 API write)은 ApprovalPort 통과 필수
  - 모드 전환 권한은 관리자 역할로 제한
- 운영 통제:
  - 정책 변경은 버전관리 + 감사 이벤트 의무화
  - 비정상 실패율 급증 시 자동 read-only 보호 모드 전환 가능

## 8) KPI(정합성, 복구시간, 실패율) + 목표치
- 정합성 지표
  - 정의: 감사 검증 통과 비율 (`verified_events / total_events`)
  - 집계 규칙: rolling 24h, 테스트/리허설 이벤트 제외, AuditPort `verify_integrity` 로그 기준
  - 목표: **99.95% 이상**
- 복구시간(MTTR)
  - 정의: 동기화 공백 감지부터 정상 상태 복귀까지 평균 시간
  - 정상 상태 판정: backlog 임계치 이하 + `verify_integrity` 통과 + 사용자 영향 오류 0건
  - 집계 규칙: 주간(7d) 평균 + p95 병행, 강제 수동 중단 케이스는 별도 분류
  - 목표: **P0 구간 15분 이내**, P1 이후 **5분 이내**
- 실패율
  - 정의: 최종 사용자 영향 실패 요청 수 / 전체 사용자 요청 수
  - 집계 규칙: rolling 24h, 요청 단위 집계, 내부 재시도 후 자동 복구 성공 건은 분모에만 포함
  - 목표: **0.5% 이하(P0)**, **0.1% 이하(P1/P2)**

## 9) P0/P1/P2 단계별 적용 계획

### P0 (현재)
- 모드/포트 계약 문서화 및 용어 고정
- 최소 어댑터 인터페이스 시그니처 동결
- 동기화 공백 표준 시퀀스 합의

### P1
- 모드별 어댑터 프로토타입 구현 및 공통 계약 테스트 도입
- reconcile/repair 자동화율 상향
- KPI 계측 대시보드(정합성/MTTR/실패율) 연결

### P2
- 고급 충돌해결 정책(우선순위/의존 그래프) 적용
- 멀티노드 환경 확장 및 교차 감사 검증
- 운영 자동복구 + 승인 하이브리드 정책 정교화

## 10) 리스크/완화
1. 리스크: 모드별 구현 편차로 계약 위반 발생
   - 완화: 포트 계약 테스트를 CI 필수 게이트로 지정
2. 리스크: 오프라인 구간 장기화로 pending 적체
   - 완화: 적체 임계치 경보 + 배치 reconcile + 수동 승인 우회 경로
3. 리스크: 감사 로그 증가에 따른 성능 저하
   - 완화: 로그 세그먼트 보관정책, 인덱스 최적화, 비동기 질의 경로 분리
4. 리스크: 권한 오남용/정책 오설정
   - 완화: 정책 변경 2인 승인, 변경 전후 diff 감사 의무화

## 11) DoD
- [ ] 본 문서가 저장소 `docs/plans/2026-03-05-runtime-modes-and-core-ports.md`에 존재
- [ ] 필수 섹션 11개 모두 포함 및 한국어 작성 완료
- [ ] Core Ports 최소 4종(Recall/Identity/Approval/Audit) 계약 명시
- [ ] 모드별 Adapter 매핑표 포함
- [ ] 동기화 공백 처리 시퀀스 6단계(mark_pending~doc_version) 포함
- [ ] KPI 목표치 수치화 완료
- [ ] 단계별(P0/P1/P2) 적용 계획 및 리스크/완화 정의

### DoD 증빙 링크/책임자
| 항목 | 증빙/링크 | Owner | Target Date |
|---|---|---|---|
| Port 계약 테스트 템플릿 초안 | `docs/templates/core-port-contract-test-template.md` (작성 예정) | Core Maintainer | 2026-03-12 |
| P1 착수 승인 로그 | `docs/reports/2026-03-xx-p1-kickoff-approval.md` (작성 예정) | Tech Lead | 2026-03-13 |
| KPI 소스맵 문서 | `docs/plans/2026-03-xx-kpi-sourcemap.md` (작성 예정) | Reliability Owner | 2026-03-14 |
