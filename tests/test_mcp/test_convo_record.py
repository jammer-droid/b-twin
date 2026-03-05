from unittest.mock import MagicMock, patch

from btwin.mcp.server import btwin_convo_record


@patch("btwin.mcp.server._get_audit_logger")
@patch("btwin.mcp.server._get_twin")
def test_explicit_convo_record_saves_under_convo_dir(mock_get_twin, mock_get_audit_logger):
    mock = MagicMock()
    mock.record_convo.return_value = {
        "date": "2026-03-05",
        "slug": "convo-123",
        "path": "/tmp/.btwin/entries/convo/2026-03-05/convo-123.md",
    }
    mock_get_twin.return_value = mock
    mock_get_audit_logger.return_value = MagicMock()

    result = btwin_convo_record(content="기억해줘", requested_by_user=True)

    mock.record_convo.assert_called_once_with("기억해줘", requested_by_user=True)
    assert "entries/convo" in result
