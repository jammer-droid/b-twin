---
doc_version: 2
last_updated: 2026-03-06
status: active
---

# BTWIN vs OpenClaw 아키텍처 Q&A (2026-03-05)

> 용어 기준: `docs/glossary.md`

## Q&A

### 용어 빠른 정의
- **정합성**: 실행 결과와 문서/상태 기록이 서로 맞는 정도
- **무결성**: 상태/문서가 변조·누락 없이 신뢰 가능한 정도
- **책임성**: 상태 전이에 대한 행위자·근거·승인 경로를 추적 가능한 정도
- **일관성(Consistency)**: 시점 간/소스 간 상태 충돌이 없는 운영 속성

### Q1. OpenClaw의 메모리 관리 방식은 어떻게 요약할 수 있나요?
**A.** OpenClaw는 기본적으로 파일 기반 메모리(예: 일일 로그, 장기 메모, 워크스페이스 문서)와 세션 컨텍스트를 결합해 상태를 유지합니다. 즉시성은 세션 히스토리가 담당하고, 지속성은 명시적으로 저장된 문서가 담당합니다. 따라서 “자동 영속 메모리”보다는 “명시적 기록 중심 메모리” 성격이 강합니다.

### Q2. OpenClaw 메모리 관리의 강점은 무엇인가요?
**A.** 감사 가능성(auditability)이 높습니다. 무엇이 언제 기록되었는지 파일/커밋 단위로 추적 가능하고, 팀 협업 시 변경 이력을 공유하기 쉽습니다. 또한 도메인별 메모리 분리(운영 노트, 사용자 정보, 프로젝트 문서)가 단순해 운영 부담이 낮습니다.

### Q3. OpenClaw 메모리 관리의 한계는 무엇인가요?
**A.** 런타임 상태와 문서 상태 사이에 시차가 발생할 수 있습니다. 여러 에이전트가 동시에 작업할 때 동일 사실의 최신 버전이 분산될 가능성이 있고, “누가 최종 상태를 확정했는지”에 대한 책임 경계가 약해질 수 있습니다.

### Q4. BTWIN과 OpenClaw의 공통점은 무엇인가요?
**A.** 둘 다 에이전트 실행을 실용적으로 운영하는 데 초점을 맞추며, 외부 도구 연동·문서화·자동화 워크플로우를 중시합니다. 또한 다중 세션/다중 작업 환경에서 인간이 감독 가능한 형태의 실행 증거를 남기는 것을 중요하게 봅니다.

### Q5. BTWIN과 OpenClaw의 핵심 차이는 무엇인가요?
**A.** OpenClaw가 범용 실행/연결 허브에 가깝다면, BTWIN은 상태 일관성과 책임 추적성을 강화하는 “운영 레이어”를 더 전면에 둡니다. 즉, OpenClaw가 작업을 수행하게 해주는 기반이라면 BTWIN은 작업 결과의 정합성과 책임 경로를 통제하는 상위 정책 레이어에 가깝습니다.

### Q6. BTWIN의 차별점(무결성)은 구체적으로 무엇인가요?
**A.** BTWIN은 문서·상태·실행 결과 간 불일치를 감지하고 복구하는 절차를 표준화합니다. 체크섬(checksum), 문서 버전(doc_version), 재동기화(refresh/reconcile) 같은 메커니즘으로 “현재 상태가 신뢰 가능한가”를 기계적으로 검증하는 데 초점을 둡니다.

### Q7. BTWIN의 차별점(책임성)은 어떻게 설명할 수 있나요?
**A.** 누가 어떤 상태 전이를 일으켰는지 추적 가능한 이벤트 중심 운영을 지향합니다. 상태를 확정하지 못한 작업은 `mark_pending`으로 명시하고, 확정·복구 절차를 별도 단계로 강제해 책임 구간을 분리합니다. 이는 사후 분석과 운영 감사에서 큰 이점을 줍니다.

### Q8. attached mode(OpenClaw 연동형)와 standalone mode(독립형)는 어떻게 다른가요?
**A.** attached mode(OpenClaw 연동형)는 OpenClaw 런타임/세션 컨텍스트와 긴밀히 결합되어 기존 도구·세션 흐름을 재사용하기 쉽습니다. standalone mode(독립형)는 외부 의존성을 줄이고 독립 실행·독립 복구에 유리합니다. 전자는 통합 편의성, 후자는 격리 안정성이 강점입니다.

### Q9. 어떤 상황에서 attached mode가 유리한가요?
**A.** 기존 OpenClaw 기반 운영이 이미 자리 잡아 있고, 동일 도구 체인과 세션 문맥을 빠르게 활용해야 할 때 유리합니다. 특히 다수의 운영 자동화가 OpenClaw 이벤트를 중심으로 구축된 환경에서 전환 비용이 낮습니다.

### Q10. 어떤 상황에서 standalone mode가 유리한가요?
**A.** 독립 배포, 제한된 네트워크, 혹은 특정 컴플라이언스 요구로 런타임 결합을 최소화해야 할 때 적합합니다. 장애 격리와 책임 분리가 쉬워 “부분 장애가 전체 운영에 전파되는 위험”을 줄이는 데 유리합니다.

### Q11. 왜 consistency layer(일관성 계층)가 중요한가요?
**A.** 실제 운영에서는 실행 성공과 상태 반영이 항상 동시에 일어나지 않습니다. 이 동기화 간극(sync gap)을 방치하면 잘못된 의사결정이 누적됩니다. consistency layer는 “실행 사실”과 “기록 상태”를 다시 맞추는 안전장치입니다.

### Q12. sync gap은 어떤 사례에서 자주 발생하나요?
**A.** (1) 비동기 작업 완료 후 문서 갱신 누락, (2) 다중 에이전트가 동일 리소스를 병렬 수정, (3) 외부 API 재시도 중 중복 반영, (4) 네트워크 단절 후 지연 동기화, (5) 수동 핫픽스가 자동 파이프라인 기록을 우회한 경우에 빈번합니다.

### Q13. BTWIN은 sync gap을 어떤 메서드로 다루나요?
**A.**
- `mark_pending`: 확정 전 상태를 명시해 오판을 방지
- `refresh`: 최신 원천 상태를 다시 수집
- `reconcile`: 실행 로그와 문서 상태를 대조·정렬
- `repair`: 불일치 상태를 복구하고 근거를 남김
- `checksum`: 콘텐츠/상태 무결성 검증
- `doc_version`: 문서 기준선과 변경 책임 추적

### Q14. multi-agent 협업에서 BTWIN 접근의 영향은 무엇인가요?
**A.** 역할 분리(실행자/검증자/승인자)가 명확해지고 충돌 복구 비용이 줄어듭니다. 특히 동일 태스크를 여러 에이전트가 분담할 때, 상태 확정 규칙이 없으면 생산성이 오히려 떨어지는데 BTWIN은 이 병목을 완화합니다.

### Q15. BTWIN vs OpenClaw 벤치마크에서 봐야 할 핵심 지표는 무엇인가요?
**A.** 단순 처리량보다 운영 신뢰성 지표가 중요합니다. 예: 상태 불일치율, 재동기화 평균 시간(MTTR-sync), 중복 작업률, 감사 추적 완결성, 롤백 성공률, 다중 에이전트 충돌률, 문서-실행 정합률.

### Q16. 우선순위 개선 과제는 무엇인가요?
**A.** 1순위는 sync gap 가시화(탐지/알림), 2순위는 자동 reconcile/repair 워크플로우, 3순위는 문서 버전 정책과 체크섬 기반 게이트 강화입니다. 즉 “빨리 실행”보다 “정확히 수렴”을 먼저 확보해야 합니다.

### Q17. P0/P1/P2 로드맵은 어떻게 요약되나요?
**A.**
- **P0(즉시 안정화):** `mark_pending` 강제, `refresh/reconcile` 표준 절차, 핵심 문서 `doc_version` 도입
- **P1(운영 자동화):** 불일치 자동 탐지, `repair` 반자동화, 체크섬 기반 검증 파이프라인
- **P2(고도화/확장):** 다중 에이전트 정책 엔진, 리스크 기반 승인 흐름, 벤치마크 대시보드 상시화

### Q18. 최종적으로 BTWIN 도입 의사결정의 포인트는 무엇인가요?
**A.** “더 많은 기능”보다 “더 높은 신뢰도”를 사는 선택인지가 핵심입니다. OpenClaw를 대체하기보다 보완하는 방식으로, 실행 계층 위에 무결성·책임성 계층을 얹어 운영 실패 비용을 낮추는 전략이 현실적일 수 있습니다. 다만 팀의 운영 성숙도, 감사 요구 수준, 기존 OpenClaw 자동화 의존도를 함께 평가해 도입 범위를 결정해야 합니다.

### Q19. 정합성과 일관성은 어떻게 구분하나요?
**A.** 정합성은 “현재 스냅샷에서 실행 결과와 기록이 맞는가”를 보는 개념이고, 일관성은 “여러 시점/소스에서 상태 충돌 없이 동일 규칙으로 수렴하는가”를 보는 개념입니다. 즉 정합성은 단면 정확도, 일관성은 시간축 안정성입니다.

### Q20. `mark_pending → refresh/reconcile/repair`는 어디서 강제되나요?
**A.** 강제 지점은 세 군데로 둡니다.
1) 쓰기 경로 훅: 신규/수정 문서 저장 시 `mark_pending`
2) 배치 훅: 세션 종료·배치 종료 시 `refresh + reconcile`
3) 운영 훅: 실패/불일치 감지 시 `repair(doc_id)` 호출 및 감사 로그 기록

### Q21. KPI는 어떻게 측정하나요?
**A.**
- 정합성 KPI: `mismatch_rate = (manifest-vector 불일치 건수 / 총 점검 건수)`
- 복구 KPI: `mttr_sync = 불일치 감지부터 indexed 복구까지 평균 시간`
- 운영 KPI: `repair_success_rate = 성공 repair / 전체 repair`

주기는 일 단위 수집, 주 단위 집계로 고정합니다.

### Q22. P0/P1/P2 단계별 완료 기준(Exit Criteria)은?
**A.**
- **P0 완료 기준:** `mismatch_rate < 1%`, `write→indexed p95 < 30s`, 핵심 문서 `doc_version` 100% 적용
- **P1 완료 기준:** 자동 탐지 커버리지 90% 이상, `repair_success_rate >= 95%`
- **P2 완료 기준:** 멀티에이전트 충돌률 주간 50% 감소, 감사 추적 누락 0건

## 핵심 의사결정 요약
- OpenClaw는 실행·연동 중심의 강력한 기반이며, BTWIN은 상태 일관성과 책임 추적을 강화하는 운영 레이어로 정의한다.
- attached mode는 통합 생산성, standalone mode는 격리 안정성을 우선한다.
- 운영 리스크의 본질은 sync gap이며, 이를 줄이는 consistency layer가 실질 성능(신뢰성)을 좌우한다.
- 핵심 통제축은 Q13의 표준 흐름(`mark_pending → refresh → reconcile → repair`)과 검증 기준(`checksum/doc_version`)이다.
- 로드맵은 P0 안정화, P1 자동화, P2 정책 고도화 순으로 추진한다.

## 즉시 실행 체크리스트 (2026-03-06 재분류)

- [x] **Action:** 용어집 v1 확정(정합성/무결성/책임성/일관성)  
  **Owner:** Architecture Lead  
  **Due:** 2026-03-12  
  **Evidence:** `docs/glossary.md`, `docs/runbook.md`, `docs/reports/2026-03-05-btwin-openclaw-qa.md`  
  **DoD 판정:** 구현 완료 (용어 정의와 참조 링크 반영)

- [x] **Action:** 핵심 문서 `doc_version` 필드 적용 + 검증 스크립트 추가  
  **Owner:** Core Maintainer  
  **Due:** 2026-03-14  
  **Evidence:** `scripts/doc_version_check.py`, `README.md`, `CONTRIBUTING.md`, `docs/runbook.md`, `docs/indexer-operations.md`, `docs/release-checklist.md`, `docs/plans/2026-03-05-runtime-modes-and-core-ports.md`  
  **DoD 판정:** 구현 완료 (검증 스크립트 추가 및 관리 문서 `doc_version` 필드 반영)

- [x] **Action:** `mark_pending` 사용 규칙 공표 및 코드리뷰 룰 추가  
  **Owner:** Tech Lead  
  **Due:** 2026-03-13  
  **Evidence:** `CONTRIBUTING.md` (`mark_pending` usage rules + review checklist)  
  **DoD 판정:** 구현 완료 (기여자 가이드에 병합 게이트 규칙 문서화)

- [x] **Action:** 배치/세션 종료 시 `refresh + reconcile` 기본 실행 파이프라인 반영  
  **Owner:** Ops Engineer  
  **Due:** 2026-03-16  
  **Evidence:** `scripts/end_of_batch_sync.sh`, `README.md`, `docs/runbook.md`, `docs/release-checklist.md`  
  **DoD 판정:** 구현 완료 (기본 실행 helper/가이드 반영, 운영 성공률 평가는 릴리스 운영 데이터 필요)

- [x] **Action:** 불일치 대응 Runbook(`repair`) + KPI(불일치율, MTTR-sync) 주간 리포트 시작  
  **Owner:** Reliability Owner  
  **Due:** 2026-03-18  
  **Evidence:** `docs/indexer-operations.md`, `docs/weekly-kpi-reporting.md`, `scripts/collect_kpi_snapshot.py`, `scripts/generate_weekly_kpi_report.py`, `docs/reports/weekly-kpi/2026-09.md`, `docs/reports/weekly-kpi/2026-10.md`  
  **DoD 판정:** 구현 완료 (자동 수집/리포트 스크립트 + 2개 연속 주차 리포트 파일 생성 완료, 운영 실측 데이터는 주간 누적 지속)
