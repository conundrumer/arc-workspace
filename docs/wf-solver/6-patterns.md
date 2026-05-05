# Patterns

Guidelines for shaping solver code when a task fits a recurring form. Style.md is for hard rules every solver follows; patterns.md is for recipes that depend on task shape.

## CONSTS holds output as grid data when expressible

When the output can be represented as whole color grids — fixed grid data per input classification, or fixed regardless of input — declaring those grids in CONSTS lets the body read them via a relational join rather than build them from positions:

```python
output_for_shape: frozenset[tuple[
    frozenset[Position],
    frozenset[tuple[Position, Color]],
]]

return {(p, col)
        for (sh, g) in c.output_for_shape if sh == s
        for (p, col) in g}
```

The criterion is whether the output structure is grid data. Tasks where the output is a transformation of the input (recolor, shift) compute positions in the body. Tasks where the output is grid data per classification keep that data in CONSTS.

## Direct expression over relation indirection

A relation in CONSTS pays off when its keys carry structural content — shapes, color triples, mappings the body can't derive. When the keys collapse to a property the body already computes (a True/False, say), named scalar fields capture the same information more directly:

```python
# Less direct
class_color: frozenset[tuple[bool, Color]]

# More direct
sym: Color
asym: Color
```

## Mappings over specialty ops

When an operation per cell can be expressed as a learnable mapping, prefer the mapping over a relational op like symmetric difference, AND, OR, or other specialty operators:

```python
combine: frozenset[tuple[Color, Color, Color]] = frozenset({
    (C0, C0, C0), (C2, C2, C0),
    (C0, C2, C3), (C2, C0, C3),
})

return {(p, c_out)
        for (p_a, c_a) in left
        for (p_b, c_b) in right if p_a == p_b
        for (a, b, c_out) in combine if a == c_a and b == c_b}
```

The mapping carries the structure as data, parameterized per task. The body's primitive vocabulary stays bounded — adding XOR, AND, masked overlay, etc. as ops grows the surface without adding task-specific structure.

## Set difference for redundant negation

When two output rules differ only in a multi-conjunction predicate being negated, deriving the negated set via set arithmetic over already-computed positions can avoid restating the predicates:

```python
changed = {p for (p, _) in cleared | landed}
passthrough = {(p, col) for (p, col) in grid if p not in changed}
```

This applies most cleanly when the negated predicate has multiple conjoined parts. With single-predicate negation, direct conditional expression is sometimes clearer; predicate duplication isn't always wrong.
