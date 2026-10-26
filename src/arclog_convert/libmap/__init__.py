"""The mapping from the present lib's names onto the lib of
`src/arclog_convert/lib-signature.dl`, as data.

- `REL`: each renamed lib relation, by its present name: its new name and
  its column renames, by the present column name. Where `guard` is given,
  the new relation's column at that present column ranges over a wider
  type, and the guard relation, of one column, holds the present type.
- `COMP`: each renamed component, by its present name: its new name and its
  relation renames, by the present relation name. Where `keep` is given, an
  instance that reads one of those relations keeps its present name.
- `DERIVATIONS`: each derivation a `DET` line or a `param` form names, by
  the converter's name for it: the name it is emitted under.

`rename.rename` applies `REL`, `COMP` and `DERIVATIONS` to arclog,
arcdata and arcscene text, and `rewrite` replaces each expansion's site in
a parsed Souffle solver by its shape, and with its `macros` config, each
lib name the expansion config of `macros` defines by its definition.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Renamed:
    name: str
    parts: dict[str, str] = field(default_factory=dict)
    keep: frozenset[str] = frozenset()
    guard: tuple[str, str, str] | None = None
    """The present column, the guard relation and that relation's column."""


REL: dict[str, Renamed] = {
    "dist": Renamed("margin", {"P": "B"}),
    "axis_dim": Renamed("frame_extent"),
    "axis_dims": Renamed("axis_extents"),
    "corner_anchor": Renamed("same_corner"),
    "slab_anchor": Renamed("same_slab"),
    "dir_of": Renamed("corner_dir", {"D": "C", "Dir": "D"}),
    "rotation": Renamed("c4_turn", {"D": "T"}),
    "flip_of": Renamed("axis_inversion", {"D": "T"}, guard=("A", "axis_elem", "A")),
    "diag_flip_of": Renamed("reflection", {"Da": "A", "D": "T"}, guard=("Da", "diag_axis_elem", "Da")),
    "turn": Renamed("turn", {"D_out": "D2"}),
    "stride": Renamed("divide", {"W": "Side", "G": "Gap", "N": "Part", "K": "Remainder"}),
}
COMP: dict[str, Renamed] = {
    "Tally": Renamed("Cardinality", {"item": "member", "tally": "size"}),
    "Unanimous": Renamed("Singleton", {"item": "member", "clash": "plural"}),
    "KeyedSetCompare": Renamed("Inclusion", {"pattern_member": "pattern", "observed_member": "observed",
                                             "covers": "superset", "equals": "equal"}),
    "Canon": Renamed("Quotient", {"equiv": "equivalent", "rep": "representative", "id": "class"}),
    "Order": Renamed("Order", {"elem": "member", "rank_desc": "dual_rank", "first": "minimal",
                               "last": "maximal", "next": "successor"}),
    "CycleWalk": Renamed("Walk", {"succ": "successor", "step": "steps"}),
    "Take": Renamed("Unfold", {"init_taken": "initial_taken", "init_untaken": "initial_untaken"}),
    "GraphDistance": Renamed("Distance", {"seed": "source", "pred": "predecessor"}),
    "Components": Renamed("Connectivity", {"label": "component"}),
    "Bbox": Renamed("BoundingBox"),
    "Closed": Renamed("Enclosure", {"region": "enclosed"}),
    "Frame2D": Renamed("Frame"),
    "Occurrences": Renamed("Occurrences", {"placement": "candidate"}),
    "Reach": Renamed("Flood", {"seed": "source", "reach": "reached"}),
    "Rim": Renamed("Boundary", {"rim": "boundary", "rim_dir": "exposed"}),
    "OffsetInvariance": Renamed("Periods", {"min_period": "fundamental_period", "period": "approximate_period"}),
}
REPLACED: frozenset[str] = frozenset({"Ray"})
"""The components that keep their name and take the signature's relations
in place of their own, since the expansions write every instance anew."""
DERIVATIONS: dict[str, str] = {"Frame2D": "Frame", "SepTiles": "Division"}


def rewrite(prog, lib, ground: bool = False, only: set[str] | None = None, macros: bool = False):
    """The program with each expansion's site replaced by its shape; each
    site left in place, with the reason; and each instance that stands for
    an expanded one under another name and what each relation of its shape
    holds, as `instances.expand` gives them.
    `lib` is the present lib's `Lib`. With `ground`, the shape holds the
    atoms the Souffle engine needs to ground it. With `only`, only the
    expansions of those names apply: a component's name, or a relation's,
    `crop`, `box_edge`, `box_corner` and the division relations. With
    `macros`, the expansion config `macros.expand` applies last, and each
    site it leaves in place is given with the reason."""
    from arclog_convert.libmap import box, cells, division, instances, orders
    from arclog_convert.libmap import macros as config
    specs = {k: v for k, v in (orders.SPECS | cells.SPECS | division.SPECS).items() if only is None or k in only}
    prog, judgment, moved, held = instances.expand(prog, lib, specs)
    if only is None or only & box.IDIOMS:
        prog, j2 = box.idioms(prog, ground)
        judgment |= j2
    if only is None or only & division.HOISTED:
        prog, j3 = division.hoist(prog, lib, ground)
        judgment |= j3
    if macros:
        prog, j4 = config.expand(prog, lib)
        judgment |= j4
    return prog, judgment, moved, held
