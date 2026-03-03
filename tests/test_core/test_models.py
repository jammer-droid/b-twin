from datetime import datetime

from btwin.core.models import Message, Session, Entry


def test_message_creation():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert isinstance(msg.timestamp, datetime)


def test_session_creation():
    session = Session(topic="career")
    assert session.topic == "career"
    assert session.messages == []
    assert isinstance(session.created_at, datetime)


def test_session_add_message():
    session = Session()
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there")
    assert len(session.messages) == 2
    assert session.messages[0].role == "user"
    assert session.messages[1].role == "assistant"


def test_entry_creation():
    entry = Entry(
        date="2026-03-02",
        slug="career-direction",
        content="# Career Direction\n\nDiscussed TA transition.",
        metadata={"topic": "career"},
    )
    assert entry.date == "2026-03-02"
    assert entry.slug == "career-direction"
    assert "TA transition" in entry.content


def test_session_to_messages_list():
    session = Session()
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi")
    messages = session.to_llm_messages()
    assert messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
