"""Whether a text, such as a ticket's title, refers to a path of the
checkout: for one path, as `names` judges it, and for many files at once,
as `Referring` judges it. Both read the forms `word_forms` gives a path."""

import re
from collections.abc import Iterable
from pathlib import PurePosixPath

MODULE_ROOTS = ("src", "scripts", ".")
"""The directories under which a file's path names a module: the packages'
sources and the scripts, which run with their directory on
the import path, and the checkout's root, from which `tests` is a
package."""

WORD_CHARS = r"\w-"
BEFORE = rf"(?<![{WORD_CHARS}])"
AFTER = rf"(?![{WORD_CHARS}])"
"""The bounds of a whole word: no word character and no `-` on either
side, so that a `/` or a `.` may stand there."""

FORM_ENDS = "./"
"""The characters outside `WORD_CHARS` that may stand after a form and
stand in a path."""

PATH_CHARS = FORM_ENDS + WORD_CHARS
"""The characters of a path's run in a text (`WORD`)."""

FORM_BEFORE = rf"(?<![{PATH_CHARS}])"
"""What may not stand before a form that `Referring` finds: a word
character, a `-`, or a `/` or a `.`, after which the form is the end of
another file's path or module name."""

NOTHING = re.compile(r"(?!)")


def module_names(path: str) -> list[str]:
    """The name of the module the file at `path`, from the checkout's root,
    is under each of `MODULE_ROOTS` that holds it."""
    p = PurePosixPath(path)
    names: list[str] = []
    for root in MODULE_ROOTS:
        if root != "." and not p.is_relative_to(root):
            continue
        parts = list((p if root == "." else p.relative_to(root)).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            names.append(".".join(parts))
    return names


def word_forms(name: str) -> list[str]:
    """The words that refer to `name` where they stand whole in a text:
    `name` itself where it holds no `/`; otherwise its file name and, for a
    module other than an `__init__.py`, each of `module_names`. A
    package's name is no form of its `__init__.py`, since a whole word may
    have a `/` or a `.` on each side, so that the name stands in each text
    that gives any module of the package."""
    if "/" not in name:
        return [name]
    path = PurePosixPath(name)
    forms = [path.name]
    if path.suffix == ".py" and path.name != "__init__.py":
        forms += module_names(name)
    return forms


def names(text: str, name: str) -> bool:
    """Whether `text` refers to `name`, as `CLOSED_ON_HELP` in
    `ticket_citations.py` gives it: it holds `name` where `name` holds a
    `/`, or a form of `word_forms` as a whole word."""
    return refers(text, name, word_forms(name))


def refers(text: str, name: str, forms: Iterable[str]) -> bool:
    """`names` of `text` and `name`, with `forms` the `word_forms` of
    `name`, for a caller that judges many texts against one name."""
    return PreparedReference(name, forms)(text)


class PreparedReference:
    """The `names` rule for one name and its forms, prepared for reuse
    across texts. `forms` gives the `word_forms` of `name`."""

    def __init__(self, name: str, forms: Iterable[str]) -> None:
        self.path = name if "/" in name else None
        self.words = tuple(whole_word_pattern(f) for f in forms)

    def __call__(self, text: str) -> bool:
        return (self.path is not None and self.path in text) \
            or any(p.search(text) is not None for p in self.words)


def whole_word_pattern(word: str) -> re.Pattern[str]:
    return re.compile(BEFORE + re.escape(word) + AFTER)


def whole_word(text: str, word: str) -> bool:
    return whole_word_pattern(word).search(text) is not None


WORD = re.compile(rf"[{PATH_CHARS}]+")
"""A run of the characters `FORM_BEFORE` and `AFTER` bound: a form made of
them that `Referring` finds starts where such a run starts, and a whole
path made of them lies inside one run."""


class Referring:
    """Whether a text gives one of the files `paths` whole, or a form of
    `word_forms` of one that holds a `.` or a `/`, bounded after as a whole
    word and before by `FORM_BEFORE`. A form with no `.` and no `/`, such as
    a script's bare module name, is a word common in prose and refers to no
    file. Of no paths, no text refers to one.

    A path or form made of the characters of `WORD` is found by a lookup in
    a set, for each run of `WORD` in the text, so the cost of a judgment
    grows with the text and not with the count of paths; any other is found
    by a pattern."""

    def __init__(self, paths: Iterable[str]) -> None:
        files = list(paths)
        whole = {p for p in files if "/" in p}
        words = {f for p in files for f in word_forms(p) if "." in f or "/" in f}
        self.whole = {p for p in whole if WORD.fullmatch(p)}
        self.words = {w for w in words if WORD.fullmatch(w)}
        self.starts = {p[:k] for p in self.whole for k in range(1, len(p))}
        parts = [re.escape(p) for p in sorted(whole - self.whole)]
        if rest := words - self.words:
            parts.append(FORM_BEFORE + alternation(rest) + AFTER)
        self.rest = re.compile("|".join(parts)) if parts else NOTHING

    def __call__(self, text: str) -> bool:
        return any(self.run_refers(m[0]) for m in WORD.finditer(text)) \
            or self.rest.search(text) is not None

    def run_refers(self, run: str) -> bool:
        """Whether a run of `WORD`, bounded on each side by a character
        outside it or by an end of the text, gives a form at its start that
        ends before a character of `FORM_ENDS` or at its end, as `AFTER`
        bounds it, or holds a whole path."""
        ends = [i for i, c in enumerate(run) if c in FORM_ENDS] + [len(run)]
        if any(run[:i] in self.words for i in ends):
            return True
        if not self.whole or "/" not in run:
            return False
        for i in range(len(run)):
            for j in range(i + 1, len(run) + 1):
                if run[i:j] in self.whole:
                    return True
                if run[i:j] not in self.starts:
                    break
        return False


def alternation(words: set[str]) -> str:
    return "(?:" + "|".join(re.escape(w) for w in sorted(words)) + ")"
