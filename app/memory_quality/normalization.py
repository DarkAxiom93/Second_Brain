"""Shared exact-content normalization for Python and PostgreSQL queries."""

import re

# This literal pattern is also passed to PostgreSQL. NBSP and other Unicode
# separators remain significant rather than depending on locale-specific rules.
EXACT_WHITESPACE_PATTERN = "[ \t\n\r\f\v]+"
_WHITESPACE = re.compile(EXACT_WHITESPACE_PATTERN)


def normalize_exact_content(content: str) -> str:
    """Strip and collapse ASCII whitespace while preserving all other text."""

    return _WHITESPACE.sub(" ", content.strip(" \t\n\r\f\v"))
