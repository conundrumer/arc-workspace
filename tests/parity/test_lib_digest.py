"""The digest of a lib record's Souffle sources, which `arclog-cli
lib-compare` computes again: a record whose digest the two sides compute
differently is never compared."""

from parity.lib import fnv1a64


def test_fnv1a64_gives_the_digest_of_the_engine_side() -> None:
    # The value the test of `engine/arclog-cli/src/lib_compare/sources.rs` states.
    assert fnv1a64(b"lib.dl\0souffle\0") == "b57d808609a766c8"
