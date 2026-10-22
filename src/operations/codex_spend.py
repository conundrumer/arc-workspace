"""The measured Codex spend of a change: the token counts of each accepted
turn (`CodexUsage`), the sources that give them with the model that ran each
(`CodexSource`), and their sum and its subscription dollars (`CodexSpend`).
`scripts/codex_spends.py` measures them. A source whose evidence is missing
keeps its counts and has an unknown cost, never a default."""

from dataclasses import dataclass
from enum import StrEnum

from ticketing.subscription import codex_cost


@dataclass(frozen=True)
class CodexUsage:
    """Token counts from one attributable turn; absent counts are unknown.
    Cached input is included in input; reasoning output is included in output.
    """
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class CodexSource:
    """A launcher's call record and its accepted turn, with missing evidence.
    A running source keeps its aggregate measurement partial.
    """
    source: str
    role: str
    thread: str | None
    turn: str | None
    usage: CodexUsage | None
    reason: str | None
    running: bool = False
    model: str | None = None
    """The model of the accepted turn's `turn_context`; None where the
    turn's evidence gives none or gives conflicting ones, which leaves the
    source's tokens counted and its cost unknown."""

    @property
    def dollars(self) -> float | None:
        """The subscription dollars of its usage, or None where the usage
        or the model is unknown."""
        return None if self.usage is None else codex_cost(self.usage, self.model, [])


class CodexStatus(StrEnum):
    ZERO = "zero"
    UNKNOWN = "unknown"
    PARTIAL = "partial"
    COMPLETE = "complete"


@dataclass(frozen=True)
class CodexSpend:
    """Attributable Codex sources; None on Spend means no source read yet.
    Totals preserve measured counts when other sources are unknown.
    """
    sources: tuple[CodexSource, ...] = ()
    inputs: tuple[tuple[str, int | None, int | None], ...] = ()

    @property
    def status(self) -> CodexStatus:
        if not self.sources:
            return CodexStatus.ZERO
        if all(s.usage is None for s in self.sources):
            return CodexStatus.UNKNOWN
        if any(s.reason is not None or s.running for s in self.sources):
            return CodexStatus.PARTIAL
        return CodexStatus.COMPLETE

    def totals(self, role: str | None = None) -> CodexUsage:
        sources = [s for s in self.sources if role is None or s.role == role]
        values = {}
        for name in CodexUsage.__dataclass_fields__:
            counts = [getattr(s.usage, name) for s in sources if s.usage is not None]
            known = [v for v in counts if v is not None]
            values[name] = sum(known) if known or not sources else None
        return CodexUsage(**values)

    def dollars(self, role: str | None = None) -> float:
        """The sum of the known subscription dollars of the sources of
        `role`, or of all, a lower bound where `dollars_known` fails."""
        return sum(d for s in self.sources if role is None or s.role == role
                   if (d := s.dollars) is not None)

    @property
    def dollars_known(self) -> bool:
        """Whether each source is read to its end and priced: the sum
        `dollars` gives is then the whole spend."""
        return self.status in (CodexStatus.ZERO, CodexStatus.COMPLETE) \
            and all(s.dollars is not None for s in self.sources)
