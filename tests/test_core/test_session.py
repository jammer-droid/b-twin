from btwin.core.session import SessionManager


def test_create_session():
    mgr = SessionManager()
    session = mgr.start_session()
    assert session is not None
    assert mgr.has_active_session()


def test_create_session_with_topic():
    mgr = SessionManager()
    session = mgr.start_session(topic="career")
    assert session.topic == "career"


def test_add_message_creates_session():
    mgr = SessionManager()
    mgr.add_message("user", "Hello")
    assert mgr.has_active_session()
    assert len(mgr.current_session.messages) == 1


def test_end_session():
    mgr = SessionManager()
    mgr.add_message("user", "Hello")
    session = mgr.end_session()
    assert session is not None
    assert len(session.messages) == 1
    assert not mgr.has_active_session()


def test_end_session_no_active():
    mgr = SessionManager()
    session = mgr.end_session()
    assert session is None


def test_get_conversation_history():
    mgr = SessionManager()
    mgr.add_message("user", "Hello")
    mgr.add_message("assistant", "Hi there")
    history = mgr.get_conversation()
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "Hello"}


def test_start_session_warns_on_overwrite(caplog):
    mgr = SessionManager()
    mgr.start_session(topic="first")
    mgr.add_message("user", "Hello")

    import logging
    with caplog.at_level(logging.WARNING):
        mgr.start_session(topic="second")

    assert "Overwriting active session" in caplog.text
    assert mgr.current_session.topic == "second"
