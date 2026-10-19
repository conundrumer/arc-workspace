"""The Determination candidates section: the `DET` and `DET_OR_RULE`
forms of `gen/` with no body, by the domains of the proposers they name,
and the determination plans the Souffle tooling keeps."""

import math
import re
from collections.abc import Iterator

from checker.determination_plan import ENUMERATION_LIMIT
from checker.plan_cache import PLAN_DIR
from controlled_markdown import mctx
from engine import checkout
from study.corpus_survey.bodies import DETERMINED
from study.corpus_survey.corpus import corpus
from study.corpus_survey.section import Section, body, items, ran
from study.corpus_survey.trees import head, is_list, is_sym

DOMAINS = {"AxisDomain": 2, "DiagAxisDomain": 2, "SenseDomain": 2, "DirDomain": 4, "DiagDirDomain": 4,
           "D4Domain": 8, "ColorDomain": 10, "NumberDomain": 30, "SymDomain": 16,
           "PositionDomain": 900, "BoxDomain": 216225}
"""The size of the domain of each domain proposer in a task of 30×30
grids: a number up to 30, a position of 900 cells, a box of a 30×30
grid."""

LISTED = 5
WIDE = ("BoxDomain", "PositionDomain")
"""The proposers of the widest domains, whose bodiless forms the section
lists."""

FACTOR = re.compile(r"\b(?:enumerable|narrowed)\((\d+)\)")
OVER = re.compile(r"over the enumeration limit \((\d+) > \d+\)")
BINS = ((1, 1), (2, 10), (11, 100))


def bodiless() -> Iterator[tuple[str, str, list[str]]]:
    """(stem, relation, proposers) of each `DET` and `DET_OR_RULE` form of
    `gen/` with no body."""
    c = corpus()
    for s in c.stems:
        for n in c.nodes(s):
            if head(n) in DETERMINED and not any(is_list(x) and head(x) != "ONE" for x in n[2:]):
                yield s, str(n[1]), [str(x) for x in n[2:] if is_sym(x)]


def plans() -> tuple[list[int], list[int]]:
    """The product of the factors of each kept plan's covered lines, and
    the product each plan over the enumeration limit reports."""
    products: list[int] = []
    over: list[int] = []
    for p in sorted((checkout.cache() / PLAN_DIR).iterdir()):
        text = p.read_text(errors="replace")
        products.append(math.prod(int(x) for x in FACTOR.findall(text)))
        over += [int(x) for x in OVER.findall(text)]
    return products, over


def determination() -> str:
    c = corpus()
    per: dict[str, int] = {}
    wide: list[str] = []
    for s, rel, props in bodiless():
        sizes = [DOMAINS[x] for x in props if x in DOMAINS]
        if sizes:
            per[s] = per.get(s, 1) * max(sizes)
        wide += [f"{s} `{rel}` {x}" for x in props if x in WIDE]
    top = sorted(per, key=lambda s: (-per[s], s))[:LISTED]
    products, over = plans()
    bins = [f"{lo} in {sum(1 for x in products if lo <= x <= hi)}" if lo == hi else
            f"{lo} to {hi} in {sum(1 for x in products if lo <= x <= hi)}" for lo, hi in BINS]
    bins.append(f"over {BINS[-1][1]} in {sum(1 for x in products if x > BINS[-1][1])}")
    return body(
        mctx("`DET` and `DET_OR_RULE` forms with no body, by the proposers they name, in `gen/`, and the Souffle tooling's determination plans. A file's product multiplies, over its forms with no body that name a domain proposer, the largest domain among the proposers a form names, at the domain's size in a task of 30×30 grids."),
        items([
            mctx("The largest products of domain proposers with no body per file: {top}; {n} files are over 100.")
            .format(top=", ".join(f"{s} {per[s]}" for s in top), n=sum(1 for v in per.values() if v > 100)),
            mctx("The forms with no body that name {wide}: {forms}.")
            .format(wide=" or ".join(f"`{w}`" for w in WIDE), forms=", ".join(wide) if wide else "none"),
            mctx("The {n} plans under `.cache/determination-plan/`, from every version of the Souffle solvers, with each covered line's `enumerable(n)` or `narrowed(n)` multiplied: product {bins}. The tool's `ENUMERATION_LIMIT` is {limit}. {k} plans report a product over it, up to {most}.")
            .format(n=len(products), bins=", ".join(bins), limit=ENUMERATION_LIMIT, k=len(over), most=max(over, default=0)),
        ]),
        ran(c.files() + ", and the plans of `.cache/determination-plan/`"))


DETERMINATION = Section("Determination candidates", 2, False, determination)
