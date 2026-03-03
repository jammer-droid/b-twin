from unittest.mock import MagicMock, patch

from btwin.core.llm import LLMClient
from btwin.config import LLMConfig


def test_build_messages_with_context():
    client = LLMClient(LLMConfig())
    messages = client.build_messages(
        system_prompt="You are B-TWIN.",
        conversation=[
            {"role": "user", "content": "Hello"},
        ],
        context=["Past record: User is interested in TA career."],
    )
    assert messages[0]["role"] == "system"
    assert "B-TWIN" in messages[0]["content"]
    assert "TA career" in messages[0]["content"]
    assert messages[1]["role"] == "user"


def test_build_messages_without_context():
    client = LLMClient(LLMConfig())
    messages = client.build_messages(
        system_prompt="You are B-TWIN.",
        conversation=[
            {"role": "user", "content": "Hello"},
        ],
    )
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_model_string():
    config = LLMConfig(provider="anthropic", model="claude-haiku-4-5-20251001")
    client = LLMClient(config)
    assert client.model_string == "anthropic/claude-haiku-4-5-20251001"


@patch("btwin.core.llm.completion")
def test_generate_slug_sanitization(mock_completion):
    """Verify generate_slug strips quotes, spaces, and special chars."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '  "Unreal Material!!  Study" \n'
    mock_completion.return_value = mock_response

    client = LLMClient(LLMConfig())
    slug = client.generate_slug([{"role": "user", "content": "test"}])

    assert slug == "unreal-material----study"
    assert all(c.isalnum() or c == "-" for c in slug)


@patch("btwin.core.llm.completion")
def test_generate_slug_none_content(mock_completion):
    """Verify generate_slug handles None content gracefully."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = None
    mock_completion.return_value = mock_response

    client = LLMClient(LLMConfig())
    slug = client.generate_slug([{"role": "user", "content": "test"}])

    assert slug == "untitled"
