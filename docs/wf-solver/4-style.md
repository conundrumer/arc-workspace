# Style

How a solver file looks. Souffle is the eventual target; the Python style mirrors what would land there.

`programs/lib.py` is the body's vocabulary — primitives, types, naming patterns. Read it alongside.

## Relations

- Relations are `set`s of tuples. Dicts are forbidden.
- Set-valued keys encode as `frozenset` + `==` (Souffle: count-trick).

## Docstring

- Short description of the task's rule.
- `Placeholders:` section for fallback patterns (e.g., raw Position destructure where a primitive would later sit). Each entry: `- <label>: <reason>` — `<label>` is the fallback technique (recurring across solvers; e.g., `position-destructure`); `<reason>` is the case-specific operation in the body.

## Imports

- `from programs.lib import *`.

## Consts

- Per-task `@dataclass(frozen=True)`, module-level `CONSTS` instance.
- Fields named by role.
- Mappings (and other values not covered by lib.py types) live here.

## Body

- Signature: `def solve(grid: Grid, c: Consts) -> Grid:`. For tiebreak tasks (task JSON contains `tiebreak` alts), signature adds `choice: ChoiceFn` (Souffle: `choice-domain`).
- References `c.<field>` for any family-parameterized value.
- Color and orientation literals never appear inline.
- Numbers that represent task structure (e.g. lengths, offsets, counts) belong in Consts.
- Use Dir-/Axis-parameterized primitives over Position destructure. When no primitive captures the pattern, raw destructure is allowed; list under `Placeholders:`.
- Each rule is one set comprehension. Comment with Datalog/Souffle form above.
- Singleton extraction from a relation uses iterable unpacking: `(x,) = {col for ... if ...}` — raises if not singleton.
- Python constructs without Souffle equivalents (e.g., `range`, `sorted`) get an inline `# <label>:` comment and a matching Placeholder entry.
- Recursive rules use an inline fixpoint loop:

  ```python
  rel: set[tuple[...]] = {... base case ...}
  while True:
      grew = {... step ...}
      if grew <= rel: break
      rel |= grew
  ```

## Example

```python
"""Apply a D4 transform to every cell."""

from dataclasses import dataclass

from programs.lib import *


@dataclass(frozen=True)
class Consts:
    flip: D4


CONSTS = Consts(flip=D4.FLIP_LR)


def solve(grid: Grid, c: Consts) -> Grid:
    # out(p', col) :- in(p, col), p' = apply(c.flip, p).
    return {(apply(c.flip, p), col) for (p, col) in grid}
```
