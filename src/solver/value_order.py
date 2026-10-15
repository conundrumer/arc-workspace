"""The order on values."""

from engine import AdtValue, NilValue, RecordValue, Row, Value


def value_key(value: Value) -> tuple[object, ...]:
    """An order on values built from their parts: numbers, then symbols,
    then `nil` and records by their fields, then ADT values by constructor and
    arguments. An ordering of values that reaches output is by a key built
    from their parts, never by `repr`."""
    match value:
        case bool() | int() | float():
            return (0, value)
        case str():
            return (1, value)
        case NilValue():
            return (2,)
        case RecordValue(fields=fields):
            return (2, tuple(value_key(f) for f in fields))
        case AdtValue(constructor=c, args=args):
            return (3, c, tuple(value_key(a) for a in args))


def row_key(row: Row) -> tuple[object, ...]:
    """An order on rows built from their values' parts (`value_key`)."""
    return tuple(value_key(v) for v in row)
