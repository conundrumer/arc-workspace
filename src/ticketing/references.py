"""Whether a text, such as a ticket's title, refers to a path of the
checkout: for one path, as `names` judges it, and for many paths at once,
as the one pattern `referring` builds matches. Both read the forms
`word_forms` gives a path, so the two judge a file's path alike."""

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

PATH_BEFORE = r"(?<![\w./-])"
"""What may not stand before a path that a text gives: any character of a
path, so that the path is not the end of a longer one."""

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
    """Whether `text` refers to `name`, as `CLOSED_ON_HELP` in `file_ticket.py`
    gives it: it holds `name` where `name` holds a `/`, or a form of
    `word_forms` as a whole word."""
    return ("/" in name and name in text) or any(whole_word(text, f) for f in word_forms(name))


def whole_word(text: str, word: str) -> bool:
    return re.search(BEFORE + re.escape(word) + AFTER, text) is not None


def referring(paths: Iterable[str]) -> re.Pattern[str]:
    """One pattern that a text matches where it refers to one of `paths`:
    to a file's path as `names` judges it, and to a directory's path,
    one that ends with a `/`, where the text gives a path under that
    directory. A pattern of no paths matches no text."""
    whole: set[str] = set()
    words: set[str] = set()
    dirs: set[str] = set()
    for p in paths:
        if p.endswith("/"):
            dirs.add(p)
            continue
        if "/" in p:
            whole.add(p)
        words.update(word_forms(p))
    parts = [re.escape(w) for w in sorted(whole)]
    if words:
        parts.append(BEFORE + alternation(words) + AFTER)
    if dirs:
        parts.append(PATH_BEFORE + alternation(dirs) + r"[\w.-]")
    return re.compile("|".join(parts)) if parts else NOTHING


def alternation(words: set[str]) -> str:
    return "(?:" + "|".join(re.escape(w) for w in sorted(words)) + ")"
