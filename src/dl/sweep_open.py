"""Which parameters a sweep leaves open, and the review line each one takes.

A sweep line leaves its parameter open when it carries one of four clauses.
Each clause says something the pairs do not settle, and the review line
restates that in a few words, under the parameter's name.
"""

import re

from controlled_markdown import mctx
from dl.paths import REPO_ROOT

# Where a sweep's output is kept, one `<stem>.txt` per stem, stdout and
# stderr together, beside a `<stem>.sha` holding the hash of the solver code
# the sweep was made from.
SWEEP_CACHE = REPO_ROOT / ".scratch" / "retro" / "sweep"

# The clauses that leave a parameter open, as `dl.sweep` writes them. A
# `test refutes` clause leaves the parameter open only under the note that
# no determination picks the stored value, so the note is the clause here.
REFUTED = "a determination from train alone could pick it"
IN_KIND = "and stored are open values, differing in a nominal argument"
BELOW = "fit and are smaller than stored"
CASES = "the cases admit different values"

# A cached sweep from before the in-kind clause took its present words
# carries this form.
IN_KIND_EARLIER = (
    "differ from stored in kind, so the pairs do not fix this parameter")

# The sweep prints its progress to stderr, one line per parameter, and the
# elapsed time under the report. A cached sweep from before the progress line
# named itself, or from before the footer said `time limit`, carries the
# earlier form, so both forms match.
PROGRESS = re.compile(r"^(?:sweeping )?(\S+): \d+ (?:candidate )?values$")
FOOTER = re.compile(r"^(?:budget|time limit) \S+ elapsed \S+$")
REPORT = re.compile(r"^(\w+): (.+)$")

# A case group of a `the cases admit different values` line: the cases that
# admit the whole domain never read the parameter, and the cases that admit
# more than the smallest set leave it unexercised. The verb carries the
# count: `admits` for one case, `admit` for several.
WHOLE_DOMAIN = re.compile(r"^(?P<label>.+?) (?P<verb>admits?) the whole domain \[")
UNEXERCISED = re.compile(
    r"^(?P<label>.+?) (?P<verb>admits?) \[.*\], so the pairs do not exercise ")

type ReportLine = tuple[str, str]
type OpenParam = tuple[str, str, str]


def report_lines(text: str) -> list[ReportLine]:
    """The sweep's report lines as (parameter, line), in the order they
    stand. The progress lines and the footer are left out."""
    out: list[ReportLine] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or PROGRESS.match(line) or FOOTER.match(line):
            continue
        if m := REPORT.match(line):
            out.append((m.group(1), line))
    return out


def _case_phrases(line: str) -> list[str]:
    """What each case group of a `cases` line leaves open."""
    out: list[str] = []
    for part in line.split("; ")[1:]:
        if m := WHOLE_DOMAIN.match(part):
            many = m.group("verb") == "admit"
            out.append(mctx("the {label} case{s} never read{verb} it, so its "
                            "value is open there").format(
                label=m.group("label"), s="s" if many else "",
                verb="" if many else "s"))
        elif m := UNEXERCISED.match(part):
            many = m.group("verb") == "admit"
            out.append(
                mctx("the {label} case{s} do{verb} not exercise it").format(
                    label=m.group("label"), s="s" if many else "",
                    verb="" if many else "es"))
    return out


def open_phrase(line: str) -> str | None:
    """What the pairs leave open in this sweep line, or None when they leave
    nothing open. Several clauses read as several phrases, in the order the
    line carries them."""
    if CASES in line:
        return "; ".join(_case_phrases(line)) or CASES
    phrases: list[str] = []
    if REFUTED in line:
        phrases.append(
            mctx("only the test pairs refute the other values train admits, "
                 "so a determination from train alone could pick it"))
    if IN_KIND in line or IN_KIND_EARLIER in line:
        phrases.append(
            mctx("open values that differ from stored in a nominal argument"))
    if BELOW in line:
        phrases.append(mctx("values smaller than stored fit as well"))
    return "; ".join(phrases) or None


def review_line(param: str, line: str) -> str | None:
    """The header line the parameter takes, or None when its sweep line
    leaves nothing open."""
    phrase = open_phrase(line)
    if phrase is None:
        return None
    return mctx("// review sweep: {param} — {phrase}").format(
        param=param, phrase=phrase)


def open_params(text: str) -> list[OpenParam]:
    """The parameters a sweep leaves open, each as (parameter, its sweep
    line, the review line it takes)."""
    return [(param, line, written)
            for param, line in report_lines(text)
            if (written := review_line(param, line)) is not None]


# A sweep line states a settled value as `unique = ...` or, for a parameter
# holding several facts, `unique as a set = ...`. A line that states no
# value settles nothing: `not swept` is one.
SETTLED = re.compile(r"^\w+: unique (?:as a set )?= ")


def settled_params(text: str) -> list[ReportLine]:
    """The parameters a sweep settles on one value."""
    return [(param, line) for param, line in report_lines(text)
            if SETTLED.match(line)]


def marked_params(reviews: list[str]) -> set[str]:
    """The parameters a header's `review sweep:` values already name. A
    value opens with the parameter, then the em dash and the point."""
    return {value.split(" — ", 1)[0].strip() for value in reviews}
