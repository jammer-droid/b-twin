"""One-time import script for /Users/home/playground/b-twin data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from btwin.config import BTwinConfig
from btwin.core.btwin import BTwin

SOURCE = Path("/Users/home/playground/b-twin")

# --- smalltalk.md sections ---

SMALLTALK = SOURCE / "library" / "smalltalk.md"
smalltalk_raw = SMALLTALK.read_text()

# Split manually by known section boundaries
sections = []
lines = smalltalk_raw.split("\n")

# Find section start indices
sec_starts = []
for i, line in enumerate(lines):
    if line.startswith("### "):
        sec_starts.append(i)

prefix = "\n".join(lines[:sec_starts[0]]).rstrip() if sec_starts else ""

for idx, start in enumerate(sec_starts):
    end = sec_starts[idx + 1] if idx + 1 < len(sec_starts) else len(lines)
    heading = lines[start]
    body_lines = lines[start + 1:end]
    # Remove trailing --- separators
    body = "\n".join(body_lines).strip().rstrip("-").strip()
    content = prefix + "\n\n" + heading + "\n" + body if prefix else heading + "\n" + body
    sections.append((heading, content))

# Map sections to entries
SMALLTALK_ENTRIES = [
    {
        "heading": "### 260226",
        "date": "2026-02-26",
        "slug": "indie-game-project-cleanup",
        "tags": ["career", "indie-game", "project-management"],
    },
    {
        "heading": "### 260225",
        "date": "2026-02-25",
        "slug": "ea-offer-career-direction",
        "tags": ["career", "ea-korea", "ta", "unreal", "houdini"],
    },
    {
        "heading": "### ~260224",
        "date": "2026-02-24",
        "slug": "houdini-course-indie-dev",
        "tags": ["career", "houdini", "indie-game", "unity"],
    },
    {
        "heading": "### 260224",
        "date": "2026-02-24",
        "slug": "adecco-interview-prep-thoughts",
        "tags": ["career", "ea-korea", "interview"],
    },
]

# --- All import entries ---

ENTRIES = []

# Smalltalk sections
for meta in SMALLTALK_ENTRIES:
    for heading, content in sections:
        if heading.strip() == meta["heading"]:
            ENTRIES.append({
                "content": content,
                "date": meta["date"],
                "slug": meta["slug"],
                "tags": meta["tags"],
                "source_path": str(SMALLTALK.resolve()),
            })
            break

# Single-file entries
SINGLE_FILES = [
    {
        "path": "library/summary.md",
        "date": "2026-03-02",
        "slug": "library-summary",
        "tags": ["summary", "career"],
    },
    {
        "path": "jobs/AdeccoKorea/jd.md",
        "date": "2026-02-24",
        "slug": "ea-ui-engineer-jd",
        "tags": ["job-posting", "ea-korea", "ui-engineering"],
    },
    {
        "path": "jobs/AdeccoKorea/00_report_260224.md",
        "date": "2026-02-24",
        "slug": "ea-jd-analysis",
        "tags": ["job-analysis", "ea-korea", "interview"],
    },
    {
        "path": "jobs/AdeccoKorea/01_interview_qa_260224.md",
        "date": "2026-02-24",
        "slug": "ea-interview-qa",
        "tags": ["interview", "ea-korea", "qa-prep"],
    },
    {
        "path": "jobs/AdeccoKorea/02_storyline_260224.md",
        "date": "2026-02-24",
        "slug": "ea-interview-storyline",
        "tags": ["interview", "ea-korea", "storyline"],
    },
    {
        "path": "jobs/AdeccoKorea/03_prep_260224.md",
        "date": "2026-02-24",
        "slug": "ea-interview-prep",
        "tags": ["interview", "ea-korea", "prep"],
    },
    {
        "path": "jobs/AdeccoKorea/04_review_260225.md",
        "date": "2026-02-25",
        "slug": "ea-interview-review",
        "tags": ["interview", "ea-korea", "review", "retrospective"],
    },
    {
        "path": "jobs/AdeccoKorea/00_report_260302.md",
        "date": "2026-03-02",
        "slug": "ea-jd-analysis-v2",
        "tags": ["job-analysis", "ea-korea", "interview"],
    },
    {
        "path": "jobs/AdeccoKorea/01_interview_qa_260302.md",
        "date": "2026-03-02",
        "slug": "ea-interview-qa-v2",
        "tags": ["interview", "ea-korea", "qa-prep"],
    },
    {
        "path": "jobs/AdeccoKorea/02_storyline_260302.md",
        "date": "2026-03-02",
        "slug": "ea-interview-storyline-v2",
        "tags": ["interview", "ea-korea", "storyline"],
    },
    {
        "path": "docs/ta-roadmap.md",
        "date": "2026-02-25",
        "slug": "ta-career-roadmap",
        "tags": ["career", "ta", "unreal", "houdini", "roadmap"],
    },
    {
        "path": "docs/plans/2026-02-26-btwin-service-design.md",
        "date": "2026-02-26",
        "slug": "btwin-service-design",
        "tags": ["btwin", "design", "product"],
    },
    {
        "path": "docs/plans/btwin-update.md",
        "date": "2026-02-26",
        "slug": "btwin-service-design-v2",
        "tags": ["btwin", "design", "product"],
    },
    {
        "path": "docs/plans/2026-03-02-btwin-mvp-design.md",
        "date": "2026-03-02",
        "slug": "btwin-mvp-design",
        "tags": ["btwin", "design", "architecture"],
    },
    {
        "path": "docs/plans/2026-03-02-btwin-mvp-implementation.md",
        "date": "2026-03-02",
        "slug": "btwin-mvp-implementation",
        "tags": ["btwin", "implementation", "plan"],
    },
]

for item in SINGLE_FILES:
    file_path = SOURCE / item["path"]
    ENTRIES.append({
        "content": file_path.read_text(),
        "date": item["date"],
        "slug": item["slug"],
        "tags": item["tags"],
        "source_path": str(file_path.resolve()),
    })


def main():
    config = BTwinConfig()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    twin = BTwin(config)

    print(f"Importing {len(ENTRIES)} entries into {config.data_dir}...\n")

    for entry in ENTRIES:
        result = twin.import_entry(
            content=entry["content"],
            date=entry["date"],
            slug=entry["slug"],
            tags=entry["tags"],
            source_path=entry["source_path"],
        )
        print(f"  ✓ {result['date']}/{result['slug']}")

    print(f"\nDone! {len(ENTRIES)} entries imported.")
    print(f"Data dir: {config.data_dir}")
    print(f"Entries dir: {config.data_dir / 'entries'}")


if __name__ == "__main__":
    main()
