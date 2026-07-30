"""Unit coverage for conservative explicit-polarity contradiction rules."""

import pytest

from app.memory_quality.contradiction import detect_opposing_states


@pytest.mark.parametrize(
    ("left", "right", "left_state", "right_state"),
    [
        ("service is ready", "service is not ready", "is", "is not"),
        ("nodes are ready", "nodes are not ready", "are", "are not"),
        ("service was ready", "service was not ready", "was", "was not"),
        ("nodes were ready", "nodes were not ready", "were", "were not"),
        ("service can retry", "service cannot retry", "can", "cannot"),
        ("service can retry", "service can not retry", "can", "can not"),
    ],
)
def test_every_supported_explicit_negation_form(
    left: str, right: str, left_state: str, right_state: str
) -> None:
    result = detect_opposing_states(left, right)
    assert result is not None
    assert result.evidence_type == "explicit_negation"
    assert (result.target_state, result.candidate_state) == (
        left_state,
        right_state,
    )
    assert detect_opposing_states(right, left) is not None


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("feature enabled", "feature disabled"),
        ("feature active", "feature inactive"),
        ("flag true", "flag false"),
        ("feature on", "feature off"),
        ("service available", "service unavailable"),
    ],
)
def test_every_supported_boolean_state_pair(left: str, right: str) -> None:
    result = detect_opposing_states(left, right)
    assert result is not None
    assert result.evidence_type == "opposing_boolean_state"


def test_case_ascii_whitespace_and_surrounding_punctuation_are_normalized() -> None:
    result = detect_opposing_states("  (Service)\tIS\nready. ", "service is NOT ready!")
    assert result is not None
    assert result.evidence_type == "explicit_negation"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("alpha is ready", "beta is not ready"),
        ("service is ready", "service is not healthy"),
        ("service is ready now", "service is not ready tomorrow"),
        ("service is ready", "service is ready"),
        ("service is fast", "service is slow"),
        ("replicas 2", "replicas 3"),
        ("version 2 is active", "version 3 is inactive"),
        ("alpha\u00a0service is ready", "alpha service is not ready"),
    ],
)
def test_non_exact_anchors_and_unsupported_conflicts_are_excluded(
    left: str, right: str
) -> None:
    assert detect_opposing_states(left, right) is None
