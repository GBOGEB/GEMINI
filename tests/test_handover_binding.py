import copy

import pytest

from src.handover_binding import bind_evidence


def _batch(verdict: str = "ACCEPT", package_count: int = 1) -> dict:
    return {
        "schema_version": 1,
        "batch_verdict": verdict,
        "package_count": package_count,
        "packages": [],
    }


def _ic3_pass() -> dict:
    return {
        "result": "PASS",
        "classification": "IC3_DRIVE_READONLY_GT0_STEP_PASS",
    }


def test_exact_ic3_pass_and_nonempty_content_accept_is_ready() -> None:
    binding = bind_evidence(_batch(), _ic3_pass())

    assert binding["transport_gate"]["state"] == "PASS"
    assert binding["content_gate"]["state"] == "ACCEPT"
    assert binding["control_readiness"] == "READY_FOR_REVIEW"
    assert binding["blockers"] == []


def test_content_accept_cannot_compensate_for_failed_auth() -> None:
    binding = bind_evidence(
        _batch(),
        {"result": "FAIL", "classification": "OIDC_WIF_AUTH_FAILED"},
    )

    assert binding["transport_gate"]["state"] == "WITHHELD"
    assert binding["content_gate"]["state"] == "ACCEPT"
    assert binding["control_readiness"] == "WITHHELD"
    assert binding["blockers"] == ["transport:OIDC_WIF_AUTH_FAILED"]


def test_ic3_pass_cannot_compensate_for_content_reject() -> None:
    binding = bind_evidence(_batch("REJECT"), _ic3_pass())

    assert binding["transport_gate"]["state"] == "PASS"
    assert binding["content_gate"]["state"] == "REJECT"
    assert binding["control_readiness"] == "WITHHELD"
    assert binding["blockers"] == ["content:BATCH_REJECTED"]


def test_deferred_content_withholds_readiness() -> None:
    binding = bind_evidence(_batch("DEFER"), _ic3_pass())

    assert binding["content_gate"]["state"] == "DEFER"
    assert binding["control_readiness"] == "WITHHELD"


def test_zero_package_accept_is_not_promoted_to_ready() -> None:
    binding = bind_evidence(_batch("ACCEPT", package_count=0), _ic3_pass())

    assert binding["content_gate"]["state"] == "DEFER"
    assert binding["content_gate"]["classification"] == "BATCH_ZERO_OR_UNPROVEN_PACKAGES"
    assert binding["control_readiness"] == "WITHHELD"


def test_malformed_evidence_fails_closed() -> None:
    binding = bind_evidence(
        {"batch_verdict": "UNKNOWN", "package_count": 1},
        {"result": "PASS"},
    )

    assert binding["content_gate"]["state"] == "REJECT"
    assert binding["transport_gate"]["state"] == "WITHHELD"
    assert binding["control_readiness"] == "WITHHELD"
    assert len(binding["blockers"]) == 2


def test_binding_does_not_mutate_or_promote_input_receipts() -> None:
    batch = _batch()
    batch["source_status"] = "DECLARED"
    ic3 = _ic3_pass()
    batch_before = copy.deepcopy(batch)
    ic3_before = copy.deepcopy(ic3)

    binding = bind_evidence(batch, ic3)

    assert batch == batch_before
    assert ic3 == ic3_before
    assert batch["source_status"] == "DECLARED"
    assert binding["source_claims_promoted"] is False
    assert binding["authority_transfer"] is False
    assert binding["formal_credit_delta"] == 0


def test_non_mapping_inputs_are_rejected() -> None:
    with pytest.raises(TypeError):
        bind_evidence([], _ic3_pass())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        bind_evidence(_batch(), [])  # type: ignore[arg-type]


def test_non_scalar_batch_verdict_returns_invalid_receipt() -> None:
    binding = bind_evidence(
        {"batch_verdict": [], "package_count": 1},
        _ic3_pass(),
    )
    assert binding["content_gate"]["state"] == "REJECT"
    assert binding["content_gate"]["classification"] == "BATCH_RECEIPT_INVALID"
    assert binding["control_readiness"] == "WITHHELD"
