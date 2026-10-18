"""The lint categories, as the annotation syntax names them."""

from enum import StrEnum

from engine.quotes import quotes


@quotes("solver-file.md", "Program",
        "A relation kept despite a hint has `// @ignore: <category> — "
        "<reason>`, with the category the hint gives, in the run of "
        "`@ignore` lines directly above its declaration.")
class Category(StrEnum):
    """The closed vocabulary of lint categories an `@ignore: <category>`
    line may name (docs/handbook/solver-file.md#program, the `@ignore`
    directive). A line that names a word outside it is a fault."""

    RESERVED_NAME = "reserved name"
    SHADOWED_TYPE = "shadowed type"
    LIB_NAME = "lib name"
    LIB_INTERNAL = "lib internal"
    ENUMERATOR_NAME = "enumerator name"
    LIB_CODE = "lib code"
    PARSE_UNSHARED_WITH_DETERMINE = "parse unshared with determine"
    DETERMINE_SCHEMA = "determine schema"
    DETERMINE_PREDICTION = "determine prediction"
    FAMILY_CASE = "family case"
    HEADER = "header"
    CLAIM = "claim"
    KEYWORD = "keyword"
    UNREAD_FIELD = "unread-field"
    CASE_SECTION = "case section"
    CASE_MARKER = "case marker"
    GLOSS = "gloss"
    WITNESS = "witness"
    ONE_CASE = "one case"
    RIGID_CHART = "rigid chart"
    ORIENTATION_LITERAL = "orientation literal"
    NONZERO_LITERAL = "nonzero literal"
    ARITHMETIC = "arithmetic"
    RANGE = "range"
    ORD = "ord"
    BANNED_TYPE = "banned type"
    OPEN_VALUE_FIELD = "open value field"
    DEMONSTRATED_CHOICE = "demonstrated choice"
    PARAMS_DATA = "params data"
    RECURSION = "recursion"
    DEAD = "dead"
    ALIAS_INLINE = "alias-inline"
    NEGATED_USE = "negated-use"
    CHOICE_DOMAIN = "choice-domain"
    SHARED_READ = "shared-read"
    CHOICE_TAG = "choice-tag"
    TYPED_ORDER = "typed-order"
    CROSS_CHOICE = "cross-choice"
    RAW_AGGREGATE = "raw-aggregate"
    SUBSUMED_ATOM = "subsumed-atom"
    LIB_IDIOM = "lib-idiom"
    NAMED_COMPLEMENT = "named-complement"
    NEGATED_VALUE = "negated-value"
    LONG_CLAUSE = "long-clause"
    DECL_PLACEMENT = "decl-placement"
    PASS_THROUGH = "pass-through"
    CHAIN_JOIN = "chain-join"
    SINGLE_CONSUMER = "single-consumer"
    DOMAIN_ENUMERATOR = "domain-enumerator"
    ARGMAX = "argmax"
    CONST_JOIN = "const-join"
    COMP_IDIOM = "comp-idiom"
    COMMON_SUBEXPR = "common-subexpr"
    HEAD_ZERO = "head-zero"
    HEAD_REPEAT = "head-repeat"
    IGNORE = "ignore"


HINTS = frozenset({
    Category.KEYWORD, Category.UNREAD_FIELD,
    Category.CASE_SECTION, Category.PASS_THROUGH, Category.CHAIN_JOIN,
    Category.SINGLE_CONSUMER, Category.DOMAIN_ENUMERATOR, Category.ARGMAX,
    Category.COMMON_SUBEXPR, Category.CONST_JOIN, Category.COMP_IDIOM,
    Category.HEAD_ZERO, Category.HEAD_REPEAT, Category.DETERMINE_PREDICTION,
})
"""The categories whose findings are hints: a hint changes neither the
verdict nor the exit code."""
