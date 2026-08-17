"""Closed retry classification and safe recovery projection tests."""

import pytest

from app.agent_runs.executor import RetryClass, classify_retry


def test_retry_classifier_is_closed() -> None:
    assert {item.value for item in RetryClass} == {
        "never",
        "safe_transient_read",
        "ambiguous_manual_recovery",
    }
    assert (
        classify_retry("tool_timeout", authority="read", idempotency="pure_read")
        == RetryClass.SAFE_TRANSIENT_READ
    )
    assert (
        classify_retry(
            "tool_provider_failed", authority="propose", idempotency="pure_read"
        )
        == RetryClass.AMBIGUOUS_MANUAL_RECOVERY
    )
    assert (
        classify_retry("tool_output_invalid", authority="read", idempotency="pure_read")
        == RetryClass.NEVER
    )
    assert (
        classify_retry("future_code", authority="read", idempotency="future")
        == RetryClass.NEVER
    )


@pytest.mark.parametrize(
    "code",
    [
        "tool_policy_rejected",
        "tool_input_invalid",
        "tool_output_invalid",
        "tool_output_oversized",
        "tool_unavailable",
        "tool_controlled_failure",
        "database_transaction_failed",
        None,
    ],
)
def test_nonretryable_classes_never_inherit_safe_read_retry(
    code: str | None,
) -> None:
    assert (
        classify_retry(code, authority="read", idempotency="pure_read")
        == RetryClass.NEVER
    )
