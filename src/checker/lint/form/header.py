"""The lint checks on a solver's header: the header's form, the
keywords it names, with the handbook's list of those keywords, and what a
keyword asks of the program."""

import re
from pathlib import Path
from typing import Annotated

from checker.finding import (
    Finding,
    LintNamed,
    LintSentence,
)
from checker.lint.form.declared_types import demonstrated_choice
from checker.lint.view import (
    lint,
)
from checker.runs import Runs
from engine import (
    checkout,
)
from engine.quotes import quotes
from solver.annotations import (
    HEADER_RANK,
    REVIEW_RANK,
    SIBLING_DROPS,
    ClaimKind,
    HeaderWord,
)
from solver.category import Category
from solver.aggregate import (
    Solver,
)


def keywords_doc() -> Path:
    """The handbook's list of keywords a solver header may name."""
    return checkout.handbook() / "keywords.md"


KEYWORD_BULLET = re.compile(r"^- `([^`]+)`")

INDUCE: Annotated[str,
    quotes("keywords.md", "Transformation",
           "`induce` — the input pairs content with the content a rule maps "
           "it to, and that rule varies per input")] = "induce"


def doc_keywords(written: str) -> dict[str, list[str]]:
    """The keywords of docs/handbook/keywords.md, in doc order, per `##`
    section: the leading code span of each bullet."""
    out: dict[str, list[str]] = {}
    section: list[str] = []
    for line in written.splitlines():
        if line.startswith("## "):
            section = out.setdefault(line[3:].strip(), [])
        elif m := KEYWORD_BULLET.match(line):
            section.append(m.group(1))
    return out


def known_keywords() -> frozenset[str]:
    """Every keyword docs/handbook/keywords.md lists (`doc_keywords`)."""
    return frozenset(w for words in doc_keywords(
        keywords_doc().read_text()).values() for w in words)


def header_keywords(solver: Solver) -> tuple[int, tuple[str, ...]] | None:
    """The line of the solver's `@keywords:` field and its words, every
    line of the field read; None where the header has none."""
    fields = sorted((f for f in solver.annotations.header
                     if f.word == HeaderWord.KEYWORDS), key=lambda f: f.line)
    return None if not fields else (fields[0].line, fields[0].words)


@quotes("solver-file.md", "Header",
        "`@scene` and `@rule` are in dependency order.")
@quotes("solver-file.md", "Header",
        "A `// review <kind>: <text>` line stands last in the header.")
@quotes("principles.md", "The concept",
        "**concept statement**: the claims that express the concept.")
@quotes("style.md", "Header",
        "`@scene` is only included when `@claim` or `@relaxed` denotes it")
def check_header(solver: Solver, runs: Runs) -> list[Finding]:
    """The header lines that break its grammar, and the fields it lacks.
    Serves readability: the header is what a reader of the corpus reads
    first."""
    ann = solver.annotations
    out: list[Finding] = []

    def flag(line: int, sentence: LintSentence, *names: str) -> None:
        out.append(lint(line, LintNamed(Category.HEADER, sentence, names)))

    if ann.task_id is None:
        return [lint(1, LintNamed(Category.HEADER, LintSentence.NO_TASK_ID,
                                  ()))]
    placed = sorted(
        [(f.line, HEADER_RANK[f.word]) for f in ann.header]
        + [(c.line, HEADER_RANK[c.kind]) for c in ann.claims
           if c.constructor is None]
        + [(r.line, REVIEW_RANK) for r in ann.reviews])
    last = -1
    for line, rank in placed:
        if rank < last:
            flag(line, LintSentence.HEADER_ORDER)
        last = max(last, rank)
    seen: set[HeaderWord] = set()
    for f in sorted(ann.header, key=lambda f: f.line):
        if f.word == HeaderWord.DRAFT:
            if f.line > 2:
                flag(f.line, LintSentence.DRAFT_PLACE)
            continue
        if f.word in seen:
            flag(f.line, LintSentence.FIELD_TWICE, f.word)
        elif (f.word in SIBLING_DROPS and HeaderWord.REPRESENTATIVE in seen
              or f.word == HeaderWord.REPRESENTATIVE
              and not seen.isdisjoint(SIBLING_DROPS)):
            flag(f.line, LintSentence.SIBLING_DROPS)
        seen.add(f.word)
    for r in ann.reviews:
        if not r.kind:
            flag(r.line, LintSentence.REVIEW_KIND)
    slugs: set[str] = set()
    for c in ann.claims:
        if c.constructor is not None:
            continue
        if c.slug in slugs:
            flag(c.line, LintSentence.SLUG_TWICE, c.slug)
        slugs.add(c.slug)
    for c in ann.header_prose[:1]:
        flag(c.line, LintSentence.HEADER_PROSE)
    if not seen & {HeaderWord.KEYWORDS, HeaderWord.REPRESENTATIVE}:
        flag(1, LintSentence.NO_KEYWORDS)
    elif (HeaderWord.KEYWORDS in seen and HeaderWord.OUTPUT not in seen
          and not any(c.kind == ClaimKind.RULE for c in ann.claims
                      if c.constructor is None)):
        flag(1, LintSentence.NO_RULE)
    return out


@quotes("solver-file.md", "Header",
        "`@keywords` lists the keywords any case claims.")
def check_keyword(solver: Solver, runs: Runs) -> list[Finding]:
    """A word of the `@keywords:` line that docs/handbook/keywords.md does not
    list, a hint: a session adds the keyword it needs and proposes it in its
    review. Serves readability: keywords index the corpus."""
    got = header_keywords(solver)
    if got is None:
        return []
    line, words = got
    known = known_keywords()
    return [lint(line, LintNamed(
                Category.KEYWORD, LintSentence.UNKNOWN_KEYWORD, (w,)))
            for w in words if w not in known]


@quotes("procedure.md", "Every pass",
        "If the solver's `@keywords:` line lists `induce`, judge by "
        "[Demonstrated choice](docs/handbook/solver-file.md#demonstrated-choice) "
        "whether the task is a nested task, and where it is, give the solver "
        "the case that section gives.")
def check_demonstrated_choice(solver: Solver, runs: Runs) -> list[Finding]:
    """A `@keywords:` line that holds `induce` in a solver that declares
    no `DemonstratedChoice` at the top level. A sibling's keywords stand
    in its representative's header, so a sibling gets none. Serves the
    concept's form: the rules a nested task's inputs demonstrate stand as
    the constructors of `DemonstratedChoice`."""
    got = header_keywords(solver)
    if got is None or INDUCE not in got[1] \
            or demonstrated_choice(solver, runs) is not None:
        return []
    return [lint(got[0], LintNamed(
        Category.DEMONSTRATED_CHOICE, LintSentence.NO_DEMONSTRATED_CHOICE,
        ()))]
