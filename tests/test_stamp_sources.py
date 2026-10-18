"""`cli.common.stamp` keys the plan cache and the parity record, so a file
that the stamped code imports and that no pattern of `SOURCES` matches can
change with the stamp left the same, and the kept plans and records stay
read as current with nothing to show it."""

from engine import checkout
from cli.common import stamped_paths
from handbook.paths import scripts_importable
from tests.conftest import script

scripts_importable()
dependents = script("dependents")

PACKAGES = "src/"
"""The directory of the packages a stamped file can import."""


def test_sources_hold_the_import_closure() -> None:
    stamped = stamped_paths(checkout.ROOT)
    graph = dependents.Graph(checkout.ROOT, ())
    reached = set(dependents.reached(
        lambda p: graph.edges(p, dependents.Reach.IMPORTS),
        {p for p in stamped if p.endswith(dependents.PYTHON_SUFFIX)}))
    assert sorted(p for p in reached - stamped if p.startswith(PACKAGES)) == []
