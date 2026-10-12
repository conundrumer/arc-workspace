"""The lines of `keywords`, `since` and `size`."""

from checker.render.faults import parse_failure_text
from controlled_markdown import mctx
from engine import ParseFailure

KEYWORD_ROW = "  {n:4d}  {word}"
UNKNOWN_KEYWORD = mctx("{stem}: {word} is not in keywords.md")
UNKNOWN_KEYWORDS = mctx("unknown keywords: {n}")
SKIPPED_REWRITE = mctx("skipped {sha}: a mechanical rewrite, touching {n} "
                       "solvers of {total}, more than the {share:.0%} share")
WINDOW_REWRITE = mctx("the window holds a corpus-wide rewrite: its commits "
                      "touch {n} solvers of {total}, more than the "
                      "{share:.0%} share, so the scope is the {kept} solvers "
                      "added since then.")
IN_SCOPE = mctx("{n} solvers in scope.")
SIZE_ROW = "{count}\t{stem}"
SIZE_UNREAD = mctx("{stem}: {error}")


def size_unread(stem: str, failure: ParseFailure) -> str:
    return SIZE_UNREAD.format(stem=stem, error=parse_failure_text(failure))
