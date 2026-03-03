"""E2E tests for B-TWIN context pipeline.

These tests call the actual LLM API to verify that:
1. RAG retrieval returns relevant past records (not irrelevant ones)
2. Multi-session context accumulates correctly
3. Session summaries capture key content

Requires BTWIN_API_KEY environment variable.
Run: uv run pytest tests/test_e2e/ -v
"""

import os
import pytest
from pathlib import Path

from btwin.config import BTwinConfig, LLMConfig
from btwin.core.btwin import BTwin

SKIP_REASON = "BTWIN_API_KEY not set — skipping E2E tests"
pytestmark = pytest.mark.skipif(
    not os.environ.get("BTWIN_API_KEY"), reason=SKIP_REASON
)


@pytest.fixture
def twin(tmp_path):
    """Create a BTwin instance with real LLM for E2E testing."""
    config = BTwinConfig(
        llm=LLMConfig(
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            api_key=os.environ.get("BTWIN_API_KEY", ""),
        ),
        data_dir=tmp_path,
    )
    return BTwin(config)


class TestRAGRetrieval:
    """Test 1: RAG 파이프라인이 관련 기록을 정확히 가져오는가?"""

    def test_retrieves_relevant_context(self, twin):
        """관련 있는 기록이 상위에, 관련 없는 기록은 하위에 나오는지 검증."""
        twin.record(
            "TA 전환을 목표로 언리얼과 후디니를 공부하기로 했다. "
            "Frostbite VP 경험이 언리얼 블루프린트로 자연스럽게 연결된다.",
            topic="ta-career-plan",
        )
        twin.record(
            "EA에서 Frostbite 엔진의 Visual Programming 기반 UI 개발 업무를 한다. "
            "노드 기반 개발 방식이 셰이더 그래프와 비슷하다.",
            topic="ea-frostbite-work",
        )
        twin.record(
            "Python FastAPI로 웹 API를 만들었다. REST endpoint 설계와 비동기 처리를 배웠다.",
            topic="python-web-api",
        )

        results = twin.search("머티리얼 에디터 노드 연결이 익숙하더라", n_results=3)

        assert len(results) == 3

        top2_slugs = {r["metadata"].get("slug", "") for r in results[:2]}
        # At least one of the top 2 should be TA or Frostbite related
        ta_or_frostbite = any("ta-career-plan" in s or "ea-frostbite-work" in s for s in top2_slugs)
        assert ta_or_frostbite, f"Expected TA or Frostbite in top 2, got: {top2_slugs}"

    def test_llm_response_uses_context(self, twin):
        """LLM 응답이 과거 맥락을 실제로 참조하는지 검증."""
        twin.record(
            "TA(Technical Artist)로 커리어를 전환하려고 한다. "
            "언리얼 셰이더와 후디니 프로시저럴 파이프라인을 공부할 계획이다. "
            "EA에서 Frostbite VP 경험이 이 전환의 기반이 된다.",
            topic="ta-transition",
        )

        response = twin.chat("오늘 머티리얼 에디터 노드 연결해봤는데 익숙하더라")

        context_keywords = ["TA", "Frostbite", "VP", "셰이더", "후디니", "노드"]
        response_lower = response.lower()
        found = [kw for kw in context_keywords if kw.lower() in response_lower]
        assert len(found) >= 1, (
            f"LLM response should reference past context. "
            f"Keywords checked: {context_keywords}. Found: {found}. "
            f"Response: {response[:200]}"
        )


class TestContextAccumulation:
    """Test 2: 여러 세션에 걸쳐 맥락이 누적되는가?"""

    def test_multi_session_context(self, twin):
        """세션 1, 2의 기록이 세션 3 대화에서 활용되는지 검증."""
        twin.chat("TA로 전환하려고 해. 셰이더와 VFX 쪽이 재밌어.")
        twin.end_session()

        twin.chat("언리얼 머티리얼 에디터 공부 시작했어. 기본 노드 연결은 됐어.")
        twin.end_session()

        response = twin.chat("다음에 뭘 공부하면 좋을까?")

        context_keywords = ["셰이더", "VFX", "머티리얼", "언리얼", "TA", "shader", "material"]
        response_lower = response.lower()
        found = [kw for kw in context_keywords if kw.lower() in response_lower]
        assert len(found) >= 1, (
            f"Session 3 response should reference sessions 1-2. "
            f"Response: {response[:300]}"
        )


class TestSummaryQuality:
    """Test 3: 세션 요약이 핵심 내용을 담고 있는가?"""

    def test_summary_captures_key_content(self, twin):
        """대화의 핵심 주제/결정이 요약에 포함되는지 검증."""
        twin.chat("TA 전환을 위해 언리얼 셰이더부터 공부하려고 해")
        twin.chat("구체적으로 HLSL 커스텀 노드를 먼저 해볼까 해")
        twin.chat("스타일라이즈드 환경 씬을 만드는 게 첫 번째 프로젝트야")

        result = twin.end_session()
        assert result is not None

        summary = result["summary"]
        key_topics = ["셰이더", "HLSL", "스타일라이즈드"]
        found = [t for t in key_topics if t in summary]
        assert len(found) >= 2, (
            f"Summary should contain key topics. "
            f"Expected: {key_topics}. Found: {found}. "
            f"Summary: {summary[:300]}"
        )

    def test_saved_entry_exists_on_disk(self, twin):
        """세션 종료 후 마크다운 파일이 실제로 디스크에 저장되는지 검증."""
        twin.chat("언리얼 공부 기록")
        result = twin.end_session()
        assert result is not None

        entries = twin.storage.list_entries()
        assert len(entries) == 1
        assert len(entries[0].content) > 10
