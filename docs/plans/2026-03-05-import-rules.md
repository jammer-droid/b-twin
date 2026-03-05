# B-TWIN Import Rules

Date: 2026-03-05
Status: Draft

## Purpose

외부 마크다운 디렉토리를 btwin-service의 `entries/` 포맷으로 변환하는 범용 임포트 규칙.
특정 폴더 구조에 의존하지 않고, 아무 마크다운 프로젝트든 입력으로 받을 수 있어야 한다.

## Scope

- **임포트 대상**: `.md` 파일만
- **제외 대상**: PDF, 이미지, `.docx`, 바이너리 등 비-마크다운 파일
- **제외 디렉토리**: `.git/`, `.claude/`, `node_modules/`, `.venv/` 등 도구 디렉토리

## Pipeline

```
소스 디렉토리 스캔
  → .md 파일 수집
  → 멀티섹션 감지 & 분리
  → 날짜 추출
  → Slug 생성
  → 태그 추론
  → Entry 생성 (frontmatter + content)
  → 벡터 인덱스 등록
  → summary.md 갱신
```

---

## 1. File Discovery

소스 디렉토리를 재귀 탐색하여 `.md` 파일을 수집한다.

### Skip rules

다음 경로는 스캔에서 제외한다:

- 도트 디렉토리: `.git/`, `.claude/`, `.venv/` 등 (`.*`)
- 패키지 디렉토리: `node_modules/`
- 기존 btwin 데이터 디렉토리: `entries/` (이미 btwin 포맷인 경우)

### Dedup

같은 파일을 두 번 임포트하지 않기 위해, 각 Entry의 메타데이터에 `source_path`(원본 절대 경로)를 기록한다.
임포트 시 기존 entries에서 동일한 `source_path`가 있으면 스킵하거나, `--force` 플래그로 덮어쓸 수 있게 한다.

---

## 2. Multi-Section Detection & Split

하나의 `.md` 파일 안에 날짜 기반 섹션이 반복되는 경우, 섹션별로 분리하여 각각 독립 Entry로 만든다.

### Detection

다음 패턴의 헤딩이 파일 내에 **2개 이상** 존재하면 멀티섹션 파일로 판정한다:

```
### 260226          ← YYMMDD
### ~260224         ← ~YYMMDD (범위/이전 표기)
## 2026-02-26       ← YYYY-MM-DD
## 2026/02/26       ← YYYY/MM/DD
### 260226 summary  ← YYMMDD + suffix (날짜 뒤에 텍스트 허용)
```

정규식: `^#{2,3}\s+~?(\d{6}|\d{4}[-/]\d{2}[-/]\d{2})\b`

### Split behavior

- 각 날짜 헤딩부터 다음 날짜 헤딩 직전까지를 하나의 섹션으로 자른다.
- 첫 날짜 헤딩 이전의 내용(파일 제목 등)은 모든 분리된 Entry의 앞에 prefix로 붙인다.
- 헤딩과 다음 날짜 헤딩 사이의 `---` 구분선은 제거한다.

### Split entry naming

분리된 Entry의 slug는 `{원본파일slug}-{날짜}` 형태:
- `smalltalk.md`의 `### 260226` 섹션 → slug: `smalltalk-260226`, date: `2026-02-26`

---

## 3. Date Extraction

각 Entry의 날짜를 다음 우선순위로 결정한다:

### Priority

1. **섹션 헤딩 날짜** (멀티섹션 분리 시): 해당 섹션의 헤딩에서 추출
2. **파일명 날짜 패턴**: 파일명에 포함된 날짜를 추출
3. **Frontmatter `date` 필드**: 파일에 이미 YAML frontmatter가 있는 경우
4. **파일 수정 시간 (mtime)**: 위 방법으로 날짜를 알 수 없을 때 fallback

### Filename date patterns

파일명에서 다음 패턴을 감지한다 (우선순위순):

| Pattern | Example | Parsed |
|---------|---------|--------|
| `YYYY-MM-DD` | `2026-02-24-report.md` | `2026-02-24` |
| `YYYYMMDD` | `20260224_report.md` | `2026-02-24` |
| `YYMMDD` | `report_260224.md` | `2026-02-24` |

정규식: `(\d{4}-\d{2}-\d{2})|(\d{8})|(\d{6})`

- `YYMMDD`는 `20` prefix를 붙여 `YYYY-MM-DD`로 변환한다.
- 파일명에 날짜 패턴이 여러 개 있으면 첫 번째를 사용한다.

### Output format

모든 날짜는 `YYYY-MM-DD` 형식으로 정규화한다.

---

## 4. Slug Generation

Entry의 고유 식별자(파일명)를 생성한다.

### Rules

1. 파일명에서 확장자(`.md`)를 제거한다.
2. 파일명에서 날짜 패턴과 주변 구분자(`_`, `-`)를 제거한다.
   - `00_report_260224.md` → `00-report`
   - `ta-roadmap.md` → `ta-roadmap`
3. 언더스코어(`_`)를 하이픈(`-`)으로 변환한다.
4. 연속 하이픈을 하나로 합친다.
5. 영문은 소문자로 변환한다.
6. 결과가 비어 있으면 `untitled`을 사용한다.

### Collision handling

같은 날짜에 같은 slug의 Entry가 이미 존재하면 **내용을 병합**한다.

- 기존 Entry의 본문 뒤에 `---` 구분선 + 새 내용을 이어붙인다.
- frontmatter의 `tags`는 합집합으로 머지한다.
- 벡터 인덱스도 병합된 전체 내용으로 갱신한다.

```markdown
# 병합 전
---
date: "2026-02-24"
slug: report
tags: [jobs]
---
기존 내용...

# 병합 후
---
date: "2026-02-24"
slug: report
tags: [jobs, adecco-korea]
---
기존 내용...

---

새로 추가된 내용...
```

이 규칙은 임포트뿐 아니라 `Storage.save_entry()`의 기본 동작에도 적용한다.
같은 date/slug에 새 내용이 들어오면 덮어쓰기가 아닌 append한다.

---

## 5. Tag Inference

디렉토리 경로를 기반으로 태그를 자동 생성한다. 특정 카테고리에 하드코딩하지 않는다.

### Rules

1. 소스 루트부터 파일까지의 디렉토리 경로에서, 각 폴더 이름을 태그로 변환한다.
2. 폴더 이름은 소문자 kebab-case로 정규화한다.
3. 소스 루트 디렉토리 자체의 이름은 태그에 포함하지 않는다.

### Examples

소스 루트가 `/Users/home/playground/b-twin/`일 때:

| File path | Tags |
|-----------|------|
| `library/smalltalk.md` | `[library]` |
| `jobs/AdeccoKorea/00_report_260224.md` | `[jobs, adecco-korea]` |
| `docs/ta-roadmap.md` | `[docs]` |
| `notes.md` (루트에 있는 파일) | `[]` (태그 없음) |

### CamelCase / PascalCase handling

`AdeccoKorea` → `adecco-korea` (대문자 경계에서 하이픈 삽입)

---

## 6. Entry Output Format

각 Entry는 btwin-service의 Storage 포맷에 맞게 저장한다.

### File structure

```
{data_dir}/entries/{YYYY-MM-DD}/{slug}.md
```

### Content format

```markdown
---
date: "2026-02-24"
slug: report
tags:
- jobs
- adecco-korea
source_path: /Users/home/playground/b-twin/jobs/AdeccoKorea/00_report_260224.md
imported_at: "2026-03-05T12:00:00+00:00"
---

(original markdown content)
```

### Frontmatter fields

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | `YYYY-MM-DD` |
| `slug` | string | Entry 식별자 |
| `tags` | list[string] | 디렉토리 기반 자동 태그 |
| `source_path` | string | 원본 파일 절대 경로 (dedup 용) |
| `imported_at` | string | 임포트 시각 ISO 8601 |

---

## 7. Vector Index Registration

임포트된 모든 Entry를 ChromaDB 벡터 인덱스에 등록한다.

- `doc_id`: `{date}/{slug}`
- `content`: Entry의 마크다운 본문
- `metadata`: `{ date, slug, tags }`

---

## 8. Summary Update

임포트 완료 후 `{data_dir}/summary.md`를 갱신한다.

각 Entry에 대해 본문 첫 줄(제목)을 preview로 추출하여 날짜별 섹션에 추가한다.
기존 `_update_summary()` 로직을 그대로 활용한다.

---

## 9. CLI Interface

```bash
# 기본 사용
btwin import /path/to/source

# 옵션
btwin import /path/to/source --dry-run      # 변환 결과만 미리보기, 실제 저장 안 함
btwin import /path/to/source --force         # 이미 임포트된 파일도 덮어쓰기
btwin import /path/to/source --data-dir DIR  # 타겟 data_dir 지정 (기본: ~/.btwin)
```

### Dry run output

```
Found 15 .md files, producing 19 entries (4 multi-section splits)

  library/smalltalk.md → 4 entries
    2026-02-26/smalltalk-260226
    2026-02-25/smalltalk-260225
    2026-02-24/smalltalk-260224
    2026-02-24/smalltalk-pre-260224
  jobs/AdeccoKorea/jd.md → 1 entry
    2026-02-24/jd  [tags: jobs, adecco-korea]
  ...

Proceed? [y/N]
```
