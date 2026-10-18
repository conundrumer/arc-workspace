"""Whether a text, such as a ticket's title, refers to a path of the
checkout: for one path, as `names` judges it, and for many files at once,
as the one pattern `referring` builds matches. Both read the forms
`word_forms` gives a path."""

import re
from collections.abc import Iterable
from pathlib import PurePosixPath

MODULE_ROOTS = ("src", "scripts", "tools/console", ".")
"""The directories under which a file's path names a module: the packages'
sources, the scripts and the console, which run with their directory on
the import path, and the checkout's root, from which `tests` is a
package."""

BEFORE = r"(?<![\w-])"
AFTER = r"(?![\w-])"
"""The bounds of a whole word: no word character and no `-` on either
side, so that a `/` or a `.` may stand there."""

FORM_BEFORE = r"(?<![\w./-])"
"""What may not stand before a form that `referring` matches: a word
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
    return ("/" in name and name in text) or any(whole_word(text, f) for f in forms)


def whole_word(text: str, word: str) -> bool:
    return re.search(BEFORE + re.escape(word) + AFTER, text) is not None


def referring(paths: Iterable[str]) -> re.Pattern[str]:
    """One pattern that a text matches where it gives one of the files
    `paths` whole, or a form of `word_forms` of one that holds a `.` or a
    `/`, bounded after as a whole word and before by `FORM_BEFORE`. A form
    with no `.` and no `/`, such as a script's bare module name, is a word
    common in prose and matches nothing. A pattern of no paths matches no
    text."""
    files = list(paths)
    whole = {p for p in files if "/" in p}
    words = {f for p in files for f in word_forms(p) if "." in f or "/" in f}
    parts = [re.escape(w) for w in sorted(whole)]
    if words:
        parts.append(FORM_BEFORE + alternation(words) + AFTER)
    return re.compile("|".join(parts)) if parts else NOTHING


def alternation(words: set[str]) -> str:
    return "(?:" + "|".join(re.escape(w) for w in sorted(words)) + ")"
