"""Pure orchestration and validation for evidence-backed answers."""

from dataclasses import dataclass

from app.answers.provider import AnswerProvider, InvalidAnswerResponseError
from app.repositories.memories import ScoredMemory

MAX_EVIDENCE_PER_MEMORY = 2000
MAX_EVIDENCE_CONTEXT = 12000
INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The stored Memories do not provide enough evidence to answer this question."
)


@dataclass(frozen=True)
class ValidatedAnswer:
    answer_status: str
    answer: str
    citations: list[ScoredMemory]


def build_evidence_context(evidence: list[ScoredMemory]) -> str:
    context = ""
    for index, item in enumerate(evidence, 1):
        block = f"M{index}\n{item.memory.content[:MAX_EVIDENCE_PER_MEMORY]}"
        separator = "\n\n" if context else ""
        remaining = MAX_EVIDENCE_CONTEXT - len(context)
        addition = (separator + block)[:remaining]
        context += addition
        if len(context) == MAX_EVIDENCE_CONTEXT:
            break
    return context


def answer_from_evidence(
    *, query: str, evidence: list[ScoredMemory], provider: AnswerProvider
) -> ValidatedAnswer:
    result = provider.answer(
        query=query, evidence_context=build_evidence_context(evidence)
    )
    if result.answer_status == "insufficient_evidence":
        return ValidatedAnswer(result.answer_status, INSUFFICIENT_EVIDENCE_MESSAGE, [])
    mapping = {f"M{index}": item for index, item in enumerate(evidence, 1)}
    selected: set[str] = set()
    for label in result.citation_labels:
        if label not in mapping:
            raise InvalidAnswerResponseError
        selected.add(label)
    citations = [item for label, item in mapping.items() if label in selected]
    if not citations:
        raise InvalidAnswerResponseError
    return ValidatedAnswer("answered", result.answer, citations)
