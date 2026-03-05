from btwin.core.document_contracts import validate_document_contract


def test_collab_contract_requires_frontmatter_keys():
    ok, reason = validate_document_contract(
        record_type="collab",
        metadata={"recordId": "rec_1"},
    )

    assert ok is False
    assert "taskId" in reason


def test_convo_contract_validation_passes_with_required_keys():
    ok, reason = validate_document_contract(
        record_type="convo",
        metadata={
            "recordType": "convo",
            "requestedByUser": True,
        },
    )

    assert ok is True
    assert reason == ""


def test_unknown_record_type_rejected():
    ok, reason = validate_document_contract("unknown", metadata={})

    assert ok is False
    assert "unknown record_type" in reason
