"""The lines of the relabeling check (`checker.relabeling`)."""

from checker.payloads.relabeling import (
    ColorCycle,
    ColorSwap,
    Complement,
    D4Image,
    Relabeling,
    UnobservedPayload,
)
from checker.store.witness import D4
from controlled_markdown import mctx


_D4_GERUND: dict[D4, str] = {
    D4.CW: mctx("turning {params} a quarter turn clockwise"),
    D4.HT: mctx("turning {params} a half turn"),
    D4.CC: mctx("turning {params} a quarter turn counterclockwise"),
    D4.LR: mctx("mirroring {params} left-right"),
    D4.TB: mctx("mirroring {params} top-bottom"),
    D4.DG: mctx("mirroring {params} across the main diagonal"),
    D4.AD: mctx("mirroring {params} across the anti-diagonal"),
}


def relabeling_text(r: Relabeling) -> str:
    """A relabeling as the line of its finding names it."""
    match r:
        case ColorSwap(stored=a, free=b):
            return mctx("swapping the colors {a} and {b}").format(a=a, b=b)
        case ColorCycle(colors=cs):
            order = ", ".join(str(c) for c in cs)
            return mctx("taking each of the colors {order} to the next and "
                        "the last to the first").format(order=order)
        case Complement(parameter=p):
            return mctx("complementing `{p}` within its grid").format(p=p)
        case D4Image(element=d):
            return _D4_GERUND[d].format(
                params=mctx("the stored parameters outside every `RIGID` "
                            "block"))


def _remedy(r: Relabeling) -> str:
    """What the line of a finding on `r` has its reader store in place."""
    match r:
        case D4Image():
            return mctx(
                "state the stored shape in one pose, in a `RIGID` block: see "
                "[`RIGID`](docs/handbook/patterns.md"
                "#rigid-a-stored-shape-and-its-attached-parts-in-every-"
                "orientation)")
        case ColorSwap() | ColorCycle():
            return mctx(
                "state each stored color as an `Ident` class, and read the "
                "color each class takes from the input")
        case Complement():
            return mctx(
                "store the cells as `Ident` classes, a `GRID_HxW` of `Ident` "
                "values, and read the color each class takes from the input")


def unobserved_line(at: str, p: UnobservedPayload) -> str:
    """The line of an `unobserved-relabeling` finding at `at`."""
    names = ", ".join(f"`{n}`" for n in p.parameters)
    return mctx(
        "{at}: {relabeling}, which changes {names}, changes no output on any "
        "input of the task, nor on the input of any witness entry that "
        "assigns none of the parameters it changes; {remedy}"
    ).format(at=at, relabeling=relabeling_text(p.relabeling), names=names,
             remedy=_remedy(p.relabeling))
