"""Generated from the lib by scripts/context.py."""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import NamedTuple

from engine.program import Primitive
from lib_components.call import (Columns, GridTypes, PyRow, PyValue, Relation, Size,
                                  call)


class LibType(StrEnum):
    """The types the lib declares, by name."""

    COLOR = "Color"
    DIR = "Dir"
    AXIS = "Axis"
    DIAG_DIR = "DiagDir"
    DIAG_AXIS = "DiagAxis"
    D4 = "D4"
    SYM = "Sym"
    SENSE = "Sense"
    C4 = "C4"
    DIR8 = "Dir8"
    AXIS4 = "Axis4"
    IDENT = "Ident"
    EXAMPLE = "Example"
    BOX = "Box"
    DIM = "Dim"
    POSITION = "Position"
    OFFSET = "Offset"
    UNIT = "Unit"


type TypeArg = Primitive | LibType


class TallyRows(NamedTuple):
    """The output relations of `Tally` (programs/lib/sets.dl)."""

    tally: Relation


def Tally(Key: TypeArg, Member: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, item: Iterable[PyRow] | None = None, domain: Iterable[PyRow] | None = None) -> TallyRows:
    """Runs `Tally` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Tally', [Key, Member],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'item': Columns((Key, Member, ), True), 'domain': Columns((Key, ), True), 'tally': Columns((Key, Primitive.NUMBER, ), True)},
               {'item': item, 'domain': domain},
               ['tally'], sizes)
    return TallyRows(got['tally'])


class ExcessRows(NamedTuple):
    """The output relations of `Excess` (programs/lib/sets.dl)."""

    excess: Relation


def Excess(Key: TypeArg, Member: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, plus: Iterable[PyRow] | None = None, minus: Iterable[PyRow] | None = None) -> ExcessRows:
    """Runs `Excess` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Excess', [Key, Member],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'plus': Columns((Key, Member, ), True), 'minus': Columns((Key, Member, ), True), 'excess': Columns((Key, Primitive.NUMBER, ), True)},
               {'plus': plus, 'minus': minus},
               ['excess'], sizes)
    return ExcessRows(got['excess'])


class ModeRows(NamedTuple):
    """The output relations of `Mode` (programs/lib/sets.dl)."""

    tally: Relation
    mode: Relation


def Mode(Key: TypeArg, Member: TypeArg, Token: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, item: Iterable[PyRow] | None = None) -> ModeRows:
    """Runs `Mode` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Mode', [Key, Member, Token],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'item': Columns((Key, Member, Token, ), True), 'tally': Columns((Key, Member, Primitive.NUMBER, ), True), 'mode': Columns((Key, Member, ), True)},
               {'item': item},
               ['tally', 'mode'], sizes)
    return ModeRows(got['tally'], got['mode'])


class UnanimousRows(NamedTuple):
    """The output relations of `Unanimous` (programs/lib/sets.dl)."""

    clash: Relation
    value: Relation


def Unanimous(Key: TypeArg, Val: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, item: Iterable[PyRow] | None = None) -> UnanimousRows:
    """Runs `Unanimous` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Unanimous', [Key, Val],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'item': Columns((Key, Val, ), True), 'clash': Columns((Key, ), True), 'value': Columns((Key, Val, ), True)},
               {'item': item},
               ['clash', 'value'], sizes)
    return UnanimousRows(got['clash'], got['value'])


class ExtremesRows(NamedTuple):
    """The output relations of `Extremes` (programs/lib/sets.dl)."""

    high: Relation
    low: Relation


def Extremes(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cand: Iterable[PyRow] | None = None) -> ExtremesRows:
    """Runs `Extremes` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Extremes', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cand': Columns((Key, Primitive.NUMBER, ), True), 'high': Columns((Key, Primitive.NUMBER, ), True), 'low': Columns((Key, Primitive.NUMBER, ), True)},
               {'cand': cand},
               ['high', 'low'], sizes)
    return ExtremesRows(got['high'], got['low'])


class ArgExtremesRows(NamedTuple):
    """The output relations of `ArgExtremes` (programs/lib/sets.dl)."""

    high: Relation
    low: Relation


def ArgExtremes(Key: TypeArg, Val: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cand: Iterable[PyRow] | None = None) -> ArgExtremesRows:
    """Runs `ArgExtremes` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('ArgExtremes', [Key, Val],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cand': Columns((Key, Val, Primitive.NUMBER, ), True), 'high': Columns((Key, Val, Primitive.NUMBER, ), True), 'low': Columns((Key, Val, Primitive.NUMBER, ), True)},
               {'cand': cand},
               ['high', 'low'], sizes)
    return ArgExtremesRows(got['high'], got['low'])


class KeyedSetCompareRows(NamedTuple):
    """The output relations of `KeyedSetCompare` (programs/lib/sets.dl)."""

    pattern_size: Relation
    covers: Relation
    equals: Relation


def KeyedSetCompare(Key: TypeArg, Pat: TypeArg, Member: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, pattern_member: Iterable[PyRow] | None = None, observed_member: Iterable[PyRow] | None = None) -> KeyedSetCompareRows:
    """Runs `KeyedSetCompare` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('KeyedSetCompare', [Key, Pat, Member],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'pattern_member': Columns((Pat, Member, ), False), 'observed_member': Columns((Key, Member, ), False), 'pattern_size': Columns((Pat, Primitive.NUMBER, ), False), 'covers': Columns((Key, Pat, ), False), 'equals': Columns((Key, Pat, ), False)},
               {'pattern_member': pattern_member, 'observed_member': observed_member},
               ['pattern_size', 'covers', 'equals'], sizes)
    return KeyedSetCompareRows(got['pattern_size'], got['covers'], got['equals'])


class IdentOfRows(NamedTuple):
    """The output relations of `IdentOf` (programs/lib/sets.dl)."""

    id: Relation


def IdentOf(T: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, value: Iterable[PyRow] | None = None) -> IdentOfRows:
    """Runs `IdentOf` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('IdentOf', [T],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'value': Columns((T, ), False), 'id': Columns((T, LibType.IDENT, ), False)},
               {'value': value},
               ['id'], sizes)
    return IdentOfRows(got['id'])


class CanonRows(NamedTuple):
    """The output relations of `Canon` (programs/lib/sets.dl)."""

    rep: Relation
    id: Relation


def Canon(T: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, equiv: Iterable[PyRow] | None = None, edge: Iterable[PyRow] | None = None) -> CanonRows:
    """Runs `Canon` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Canon', [T],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'equiv': Columns((T, T, ), False), 'edge': Columns((T, T, ), False), 'rep': Columns((T, T, ), False), 'id': Columns((T, LibType.IDENT, ), False)},
               {'equiv': equiv, 'edge': edge},
               ['rep', 'id'], sizes)
    return CanonRows(got['rep'], got['id'])


class DemonstrationConsistencyRows(NamedTuple):
    """The output relations of `DemonstrationConsistency` (programs/lib/sets.dl)."""

    counterexample: Relation
    consistent: Relation


def DemonstrationConsistency(Key: TypeArg, Demonstrated: TypeArg, Object: TypeArg, Index: TypeArg, Value: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, value: Iterable[PyRow] | None = None, prediction: Iterable[PyRow] | None = None, demonstration: Iterable[PyRow] | None = None) -> DemonstrationConsistencyRows:
    """Runs `DemonstrationConsistency` (programs/lib/sets.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('DemonstrationConsistency', [Key, Demonstrated, Object, Index, Value],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'value': Columns((Key, Object, Index, Value, ), True), 'prediction': Columns((Key, Demonstrated, Object, Index, Value, ), True), 'demonstration': Columns((Key, Object, Object, ), True), 'counterexample': Columns((Key, Demonstrated, Object, Object, ), True), 'consistent': Columns((Key, Demonstrated, Object, Object, ), True)},
               {'value': value, 'prediction': prediction, 'demonstration': demonstration},
               ['counterexample', 'consistent'], sizes)
    return DemonstrationConsistencyRows(got['counterexample'], got['consistent'])


class OrdinalRows(NamedTuple):
    """The output relations of `Ordinal` (programs/lib/orders.dl)."""

    rank: Relation
    rank_desc: Relation


def Ordinal(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, idx_set: Iterable[PyRow] | None = None) -> OrdinalRows:
    """Runs `Ordinal` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Ordinal', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'idx_set': Columns((Key, Primitive.NUMBER, ), True), 'rank': Columns((Key, Primitive.NUMBER, Primitive.NUMBER, ), True), 'rank_desc': Columns((Key, Primitive.NUMBER, Primitive.NUMBER, ), True)},
               {'idx_set': idx_set},
               ['rank', 'rank_desc'], sizes)
    return OrdinalRows(got['rank'], got['rank_desc'])


class OrderRows(NamedTuple):
    """The output relations of `Order` (programs/lib/orders.dl)."""

    rank: Relation
    rank_desc: Relation
    first: Relation
    last: Relation
    next: Relation


def Order(Key: TypeArg, T: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, elem: Iterable[PyRow] | None = None, before: Iterable[PyRow] | None = None) -> OrderRows:
    """Runs `Order` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Order', [Key, T],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'elem': Columns((Key, T, ), True), 'before': Columns((Key, T, T, ), True), 'rank': Columns((Key, T, Primitive.NUMBER, ), True), 'rank_desc': Columns((Key, T, Primitive.NUMBER, ), True), 'first': Columns((Key, T, ), True), 'last': Columns((Key, T, ), True), 'next': Columns((Key, T, T, ), True)},
               {'elem': elem, 'before': before},
               ['rank', 'rank_desc', 'first', 'last', 'next'], sizes)
    return OrderRows(got['rank'], got['rank_desc'], got['first'], got['last'], got['next'])


class GraphDistanceRows(NamedTuple):
    """The output relations of `GraphDistance` (programs/lib/orders.dl)."""

    distance: Relation
    pred: Relation


def GraphDistance(Key: TypeArg, Node: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, edge: Iterable[PyRow] | None = None, seed: Iterable[PyRow] | None = None) -> GraphDistanceRows:
    """Runs `GraphDistance` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('GraphDistance', [Key, Node],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'edge': Columns((Key, Node, Node, ), True), 'seed': Columns((Key, Node, ), True), 'distance': Columns((Key, Node, Primitive.NUMBER, ), True), 'pred': Columns((Key, Node, Node, ), True)},
               {'edge': edge, 'seed': seed},
               ['distance', 'pred'], sizes)
    return GraphDistanceRows(got['distance'], got['pred'])


class ReachabilityRows(NamedTuple):
    """The output relations of `Reachability` (programs/lib/orders.dl)."""

    reachable: Relation


def Reachability(Key: TypeArg, Node: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, edge: Iterable[PyRow] | None = None) -> ReachabilityRows:
    """Runs `Reachability` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Reachability', [Key, Node],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'edge': Columns((Key, Node, Node, ), True), 'reachable': Columns((Key, Node, Node, ), True)},
               {'edge': edge},
               ['reachable'], sizes)
    return ReachabilityRows(got['reachable'])


class IndexCycleRows(NamedTuple):
    """The output relations of `IndexCycle` (programs/lib/orders.dl)."""

    succ: Relation


def IndexCycle(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, idx: Iterable[PyRow] | None = None) -> IndexCycleRows:
    """Runs `IndexCycle` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('IndexCycle', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'idx': Columns((Key, Primitive.NUMBER, ), True), 'succ': Columns((Key, Primitive.NUMBER, Primitive.NUMBER, ), True)},
               {'idx': idx},
               ['succ'], sizes)
    return IndexCycleRows(got['succ'])


class CycleWalkRows(NamedTuple):
    """The output relations of `CycleWalk` (programs/lib/orders.dl)."""

    walk: Relation


def CycleWalk(Key: TypeArg, T: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, succ: Iterable[PyRow] | None = None, step: Iterable[PyRow] | None = None) -> CycleWalkRows:
    """Runs `CycleWalk` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('CycleWalk', [Key, T],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'succ': Columns((Key, T, T, ), True), 'step': Columns((Key, Primitive.NUMBER, ), True), 'walk': Columns((Key, T, Primitive.NUMBER, T, ), True)},
               {'succ': succ, 'step': step},
               ['walk'], sizes)
    return CycleWalkRows(got['walk'])


class TakeRows(NamedTuple):
    """The output relations of `Take` (programs/lib/orders.dl)."""

    taken: Relation
    untaken: Relation


def Take(Key: TypeArg, T: TypeArg, Item: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, start: Iterable[PyRow] | None = None, step: Iterable[PyRow] | None = None, take: Iterable[PyRow] | None = None, init_taken: Iterable[PyRow] | None = None, init_untaken: Iterable[PyRow] | None = None) -> TakeRows:
    """Runs `Take` (programs/lib/orders.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Take', [Key, T, Item],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'start': Columns((Key, T, ), True), 'step': Columns((Key, T, T, ), True), 'take': Columns((Key, T, Item, ), True), 'init_taken': Columns((Key, Item, ), True), 'init_untaken': Columns((Key, Item, ), True), 'taken': Columns((Key, T, Item, ), True), 'untaken': Columns((Key, T, Item, ), True)},
               {'start': start, 'step': step, 'take': take, 'init_taken': init_taken, 'init_untaken': init_untaken},
               ['taken', 'untaken'], sizes)
    return TakeRows(got['taken'], got['untaken'])


class DirFrameRows(NamedTuple):
    """The output relations of `DirFrame` (programs/lib/box.dl)."""

    extent: Relation


def DirFrame(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, dir: Iterable[PyRow] | None = None, dist_set: Iterable[PyRow] | None = None) -> DirFrameRows:
    """Runs `DirFrame` (programs/lib/box.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('DirFrame', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'dir': Columns((LibType.DIR, ), False), 'dist_set': Columns((Key, Primitive.NUMBER, ), True), 'extent': Columns((Key, Primitive.NUMBER, ), True)},
               {'dir': dir, 'dist_set': dist_set},
               ['extent'], sizes)
    return DirFrameRows(got['extent'])


class AxisFrameRows(NamedTuple):
    """The output relations of `AxisFrame` (programs/lib/box.dl)."""

    cell: Relation


def AxisFrame(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, extent: Iterable[PyRow] | None = None) -> AxisFrameRows:
    """Runs `AxisFrame` (programs/lib/box.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('AxisFrame', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'extent': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'cell': Columns((Key, LibType.AXIS, LibType.POSITION, ), True)},
               {'extent': extent},
               ['cell'], sizes)
    return AxisFrameRows(got['cell'])


class Frame2DRows(NamedTuple):
    """The output relations of `Frame2D` (programs/lib/box.dl)."""

    cell: Relation


def Frame2D(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, extent: Iterable[PyRow] | None = None) -> Frame2DRows:
    """Runs `Frame2D` (programs/lib/box.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Frame2D', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'extent': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'cell': Columns((Key, LibType.POSITION, ), True)},
               {'extent': extent},
               ['cell'], sizes)
    return Frame2DRows(got['cell'])


class DirPackRows(NamedTuple):
    """The output relations of `DirPack` (programs/lib/box.dl)."""

    axis_pos: Relation
    box: Relation


def DirPack(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, edge: Iterable[PyRow] | None = None) -> DirPackRows:
    """Runs `DirPack` (programs/lib/box.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('DirPack', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'edge': Columns((Key, LibType.DIR, Primitive.NUMBER, ), True), 'axis_pos': Columns((Key, LibType.AXIS, LibType.BOX, ), True), 'box': Columns((Key, LibType.BOX, ), True)},
               {'edge': edge},
               ['axis_pos', 'box'], sizes)
    return DirPackRows(got['axis_pos'], got['box'])


class Divide2DRows(NamedTuple):
    """The output relations of `Divide2D` (programs/lib/cells.dl)."""

    tile: Relation


def Divide2D(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None, dim: Iterable[PyRow] | None = None, gap: Iterable[PyRow] | None = None) -> Divide2DRows:
    """Runs `Divide2D` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Divide2D', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((LibType.POSITION, ), False), 'dim': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'gap': Columns((Primitive.NUMBER, ), False), 'tile': Columns((Key, LibType.POSITION, LibType.POSITION, LibType.POSITION, ), True)},
               {'cell': cell, 'dim': dim, 'gap': gap},
               ['tile'], sizes)
    return Divide2DRows(got['tile'])


class Tile2DRows(NamedTuple):
    """The output relations of `Tile2D` (programs/lib/cells.dl)."""

    tile: Relation


def Tile2D(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None, dim: Iterable[PyRow] | None = None, gap: Iterable[PyRow] | None = None) -> Tile2DRows:
    """Runs `Tile2D` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Tile2D', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((LibType.POSITION, ), False), 'dim': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'gap': Columns((Primitive.NUMBER, ), False), 'tile': Columns((Key, LibType.POSITION, LibType.POSITION, LibType.POSITION, ), True)},
               {'cell': cell, 'dim': dim, 'gap': gap},
               ['tile'], sizes)
    return Tile2DRows(got['tile'])


class DividerTilesRows(NamedTuple):
    """The output relations of `DividerTiles` (programs/lib/cells.dl)."""

    div_dist: Relation
    on_divider: Relation
    part_idx: Relation
    part_of: Relation
    tile_of: Relation


def DividerTiles(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None, divider: Iterable[PyRow] | None = None) -> DividerTilesRows:
    """Runs `DividerTiles` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('DividerTiles', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, ), True), 'divider': Columns((Key, LibType.AXIS, LibType.POSITION, ), True), 'div_dist': Columns((Key, LibType.AXIS, LibType.DIR, Primitive.NUMBER, ), True), 'on_divider': Columns((Key, LibType.POSITION, LibType.AXIS, ), True), 'part_idx': Columns((Key, LibType.POSITION, LibType.DIR, Primitive.NUMBER, ), True), 'part_of': Columns((Key, LibType.POSITION, LibType.AXIS, LibType.POSITION, ), True), 'tile_of': Columns((Key, LibType.POSITION, LibType.POSITION, ), True)},
               {'cell': cell, 'divider': divider},
               ['div_dist', 'on_divider', 'part_idx', 'part_of', 'tile_of'], sizes)
    return DividerTilesRows(got['div_dist'], got['on_divider'], got['part_idx'], got['part_of'], got['tile_of'])


class DiagonalRows(NamedTuple):
    """The output relations of `Diagonal` (programs/lib/cells.dl)."""

    diagonal: Relation


def Diagonal(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None, corner: Iterable[PyRow] | None = None) -> DiagonalRows:
    """Runs `Diagonal` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Diagonal', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, ), True), 'corner': Columns((Key, LibType.DIAG_DIR, ), True), 'diagonal': Columns((Key, LibType.POSITION, Primitive.NUMBER, ), True)},
               {'cell': cell, 'corner': corner},
               ['diagonal'], sizes)
    return DiagonalRows(got['diagonal'])


class DiagPlacementRows(NamedTuple):
    """The output relations of `DiagPlacement` (programs/lib/cells.dl)."""

    nearer: Relation
    quadrant: Relation
    diag_cell: Relation


def DiagPlacement(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None) -> DiagPlacementRows:
    """Runs `DiagPlacement` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('DiagPlacement', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, ), True), 'nearer': Columns((Key, LibType.POSITION, LibType.DIR, ), True), 'quadrant': Columns((Key, LibType.POSITION, LibType.DIAG_DIR, ), True), 'diag_cell': Columns((Key, LibType.POSITION, LibType.DIAG_DIR, Primitive.NUMBER, ), True)},
               {'cell': cell},
               ['nearer', 'quadrant', 'diag_cell'], sizes)
    return DiagPlacementRows(got['nearer'], got['quadrant'], got['diag_cell'])


class RayRows(NamedTuple):
    """The output relations of `Ray` (programs/lib/cells.dl)."""

    cast: Relation
    ray: Relation
    clear_cast: Relation
    clear: Relation
    stop: Relation


def Ray(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, dir: Iterable[PyRow] | None = None, cell: Iterable[PyRow] | None = None, mark: Iterable[PyRow] | None = None, blocked: Iterable[PyRow] | None = None) -> RayRows:
    """Runs `Ray` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Ray', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'dir': Columns((Key, LibType.DIR8, ), True), 'cell': Columns((Key, LibType.POSITION, ), True), 'mark': Columns((Key, LibType.POSITION, ), True), 'blocked': Columns((Key, LibType.POSITION, ), True), 'cast': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'ray': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'clear_cast': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'clear': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'stop': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True)},
               {'dir': dir, 'cell': cell, 'mark': mark, 'blocked': blocked},
               ['cast', 'ray', 'clear_cast', 'clear', 'stop'], sizes)
    return RayRows(got['cast'], got['ray'], got['clear_cast'], got['clear'], got['stop'])


class BetweenRows(NamedTuple):
    """The output relations of `Between` (programs/lib/cells.dl)."""

    between: Relation
    cast: Relation
    ray: Relation
    clear_cast: Relation
    clear: Relation
    stop: Relation


def Between(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, axis: Iterable[PyRow] | None = None, dir: Iterable[PyRow] | None = None, cell: Iterable[PyRow] | None = None, mark: Iterable[PyRow] | None = None, blocked: Iterable[PyRow] | None = None) -> BetweenRows:
    """Runs `Between` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Between', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'axis': Columns((Key, LibType.AXIS4, ), True), 'between': Columns((Key, LibType.POSITION, ), True), 'dir': Columns((Key, LibType.DIR8, ), True), 'cell': Columns((Key, LibType.POSITION, ), True), 'mark': Columns((Key, LibType.POSITION, ), True), 'blocked': Columns((Key, LibType.POSITION, ), True), 'cast': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'ray': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'clear_cast': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'clear': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True), 'stop': Columns((Key, LibType.POSITION, LibType.DIR8, Primitive.NUMBER, LibType.POSITION, ), True)},
               {'axis': axis, 'dir': dir, 'cell': cell, 'mark': mark, 'blocked': blocked},
               ['between', 'cast', 'ray', 'clear_cast', 'clear', 'stop'], sizes)
    return BetweenRows(got['between'], got['cast'], got['ray'], got['clear_cast'], got['clear'], got['stop'])


class SlideRows(NamedTuple):
    """The output relations of `Slide` (programs/lib/cells.dl)."""

    run: Relation
    rim_dir: Relation
    halt: Relation
    rest: Relation


def Slide(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, node: Iterable[PyRow] | None = None, dir: Iterable[PyRow] | None = None) -> SlideRows:
    """Runs `Slide` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Slide', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'node': Columns((Key, LibType.POSITION, ), True), 'dir': Columns((Key, LibType.DIR8, ), True), 'run': Columns((Key, LibType.POSITION, LibType.DIR8, LibType.POSITION, ), True), 'rim_dir': Columns((Key, LibType.POSITION, LibType.DIR8, ), True), 'halt': Columns((Key, LibType.POSITION, LibType.DIR8, LibType.POSITION, ), True), 'rest': Columns((Key, LibType.POSITION, LibType.DIR8, LibType.POSITION, ), True)},
               {'node': node, 'dir': dir},
               ['run', 'rim_dir', 'halt', 'rest'], sizes)
    return SlideRows(got['run'], got['rim_dir'], got['halt'], got['rest'])


class GravityRows(NamedTuple):
    """The output relations of `Gravity` (programs/lib/cells.dl)."""

    travel: Relation


def Gravity(Key: TypeArg, Body: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None, dir: Iterable[PyRow] | None = None, blocked: Iterable[PyRow] | None = None) -> GravityRows:
    """Runs `Gravity` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Gravity', [Key, Body],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, Body, LibType.POSITION, ), True), 'dir': Columns((Key, LibType.DIR, ), True), 'blocked': Columns((Key, LibType.POSITION, ), True), 'travel': Columns((Key, Body, LibType.OFFSET, ), True)},
               {'cell': cell, 'dir': dir, 'blocked': blocked},
               ['travel'], sizes)
    return GravityRows(got['travel'])


class OrderFrameRows(NamedTuple):
    """The output relations of `OrderFrame` (programs/lib/cells.dl)."""

    nearer: Relation
    mem: Relation
    pos: Relation


def OrderFrame(Key: TypeArg, T: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, axis: Iterable[PyRow] | None = None, member: Iterable[PyRow] | None = None) -> OrderFrameRows:
    """Runs `OrderFrame` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('OrderFrame', [Key, T],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'axis': Columns((Key, LibType.AXIS, ), True), 'member': Columns((Key, T, LibType.POSITION, ), True), 'nearer': Columns((Key, LibType.DIR, T, T, ), True), 'mem': Columns((Key, T, ), True), 'pos': Columns((Key, T, LibType.POSITION, ), True)},
               {'axis': axis, 'member': member},
               ['nearer', 'mem', 'pos'], sizes)
    return OrderFrameRows(got['nearer'], got['mem'], got['pos'])


class LexOrderRows(NamedTuple):
    """The output relations of `LexOrder` (programs/lib/cells.dl)."""

    rank: Relation
    rank_desc: Relation
    first: Relation
    last: Relation
    next: Relation


def LexOrder(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, corner: Iterable[PyRow] | None = None, axis: Iterable[PyRow] | None = None, cell: Iterable[PyRow] | None = None, elem: Iterable[PyRow] | None = None, before: Iterable[PyRow] | None = None) -> LexOrderRows:
    """Runs `LexOrder` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('LexOrder', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'corner': Columns((Key, LibType.DIAG_DIR, ), True), 'axis': Columns((Key, LibType.AXIS, ), True), 'cell': Columns((Key, LibType.POSITION, ), True), 'elem': Columns((Key, LibType.POSITION, ), True), 'before': Columns((Key, LibType.POSITION, LibType.POSITION, ), True), 'rank': Columns((Key, LibType.POSITION, Primitive.NUMBER, ), True), 'rank_desc': Columns((Key, LibType.POSITION, Primitive.NUMBER, ), True), 'first': Columns((Key, LibType.POSITION, ), True), 'last': Columns((Key, LibType.POSITION, ), True), 'next': Columns((Key, LibType.POSITION, LibType.POSITION, ), True)},
               {'corner': corner, 'axis': axis, 'cell': cell, 'elem': elem, 'before': before},
               ['rank', 'rank_desc', 'first', 'last', 'next'], sizes)
    return LexOrderRows(got['rank'], got['rank_desc'], got['first'], got['last'], got['next'])


class BboxRows(NamedTuple):
    """The output relations of `Bbox` (programs/lib/cells.dl)."""

    box: Relation


def Bbox(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None) -> BboxRows:
    """Runs `Bbox` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Bbox', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.BOX, ), True), 'box': Columns((Key, LibType.BOX, ), True)},
               {'cell': cell},
               ['box'], sizes)
    return BboxRows(got['box'])


class OutlinesRows(NamedTuple):
    """The output relations of `Outlines` (programs/lib/cells.dl)."""

    box: Relation


def Outlines(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, node: Iterable[PyRow] | None = None) -> OutlinesRows:
    """Runs `Outlines` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Outlines', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'node': Columns((Key, LibType.POSITION, ), True), 'box': Columns((Key, LibType.BOX, ), True)},
               {'node': node},
               ['box'], sizes)
    return OutlinesRows(got['box'])


class ComponentsRows(NamedTuple):
    """The output relations of `Components` (programs/lib/cells.dl)."""

    label: Relation
    conn: Relation


def Components(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, node: Iterable[PyRow] | None = None, step: Iterable[PyRow] | None = None) -> ComponentsRows:
    """Runs `Components` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Components', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'node': Columns((Key, LibType.POSITION, ), True), 'step': Columns((LibType.OFFSET, ), False), 'label': Columns((Key, LibType.POSITION, LibType.IDENT, ), True), 'conn': Columns((Key, LibType.POSITION, LibType.POSITION, ), True)},
               {'node': node, 'step': step},
               ['label', 'conn'], sizes)
    return ComponentsRows(got['label'], got['conn'])


class Components8Rows(NamedTuple):
    """The output relations of `Components8` (programs/lib/cells.dl)."""

    label: Relation
    conn: Relation


def Components8(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, node: Iterable[PyRow] | None = None, step: Iterable[PyRow] | None = None) -> Components8Rows:
    """Runs `Components8` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Components8', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'node': Columns((Key, LibType.POSITION, ), True), 'step': Columns((LibType.OFFSET, ), False), 'label': Columns((Key, LibType.POSITION, LibType.IDENT, ), True), 'conn': Columns((Key, LibType.POSITION, LibType.POSITION, ), True)},
               {'node': node, 'step': step},
               ['label', 'conn'], sizes)
    return Components8Rows(got['label'], got['conn'])


class ReachRows(NamedTuple):
    """The output relations of `Reach` (programs/lib/cells.dl)."""

    reach: Relation
    label: Relation
    conn: Relation


def Reach(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, seed: Iterable[PyRow] | None = None, node: Iterable[PyRow] | None = None, step: Iterable[PyRow] | None = None) -> ReachRows:
    """Runs `Reach` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Reach', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'seed': Columns((Key, LibType.POSITION, ), True), 'reach': Columns((Key, LibType.POSITION, ), True), 'node': Columns((Key, LibType.POSITION, ), True), 'step': Columns((LibType.OFFSET, ), False), 'label': Columns((Key, LibType.POSITION, LibType.IDENT, ), True), 'conn': Columns((Key, LibType.POSITION, LibType.POSITION, ), True)},
               {'seed': seed, 'node': node, 'step': step},
               ['reach', 'label', 'conn'], sizes)
    return ReachRows(got['reach'], got['label'], got['conn'])


class RimRows(NamedTuple):
    """The output relations of `Rim` (programs/lib/cells.dl)."""

    rim_dir: Relation
    rim: Relation
    depth: Relation


def Rim(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None) -> RimRows:
    """Runs `Rim` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Rim', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, ), True), 'rim_dir': Columns((Key, LibType.POSITION, LibType.DIR8, ), True), 'rim': Columns((Key, LibType.POSITION, ), True), 'depth': Columns((Key, LibType.POSITION, Primitive.NUMBER, ), True)},
               {'cell': cell},
               ['rim_dir', 'rim', 'depth'], sizes)
    return RimRows(got['rim_dir'], got['rim'], got['depth'])


class Rim8Rows(NamedTuple):
    """The output relations of `Rim8` (programs/lib/cells.dl)."""

    rim_dir: Relation
    rim: Relation
    depth: Relation


def Rim8(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None) -> Rim8Rows:
    """Runs `Rim8` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Rim8', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, ), True), 'rim_dir': Columns((Key, LibType.POSITION, LibType.DIR8, ), True), 'rim': Columns((Key, LibType.POSITION, ), True), 'depth': Columns((Key, LibType.POSITION, Primitive.NUMBER, ), True)},
               {'cell': cell},
               ['rim_dir', 'rim', 'depth'], sizes)
    return Rim8Rows(got['rim_dir'], got['rim'], got['depth'])


class ClosedRows(NamedTuple):
    """The output relations of `Closed` (programs/lib/cells.dl)."""

    region: Relation


def Closed(Key: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None) -> ClosedRows:
    """Runs `Closed` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Closed', [Key],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, ), True), 'region': Columns((Key, LibType.POSITION, LibType.IDENT, ), True)},
               {'cell': cell},
               ['region'], sizes)
    return ClosedRows(got['region'])


class D4MapRows(NamedTuple):
    """The output relations of `D4Map` (programs/lib/cells.dl)."""

    mismatch: Relation
    map: Relation
    conflict: Relation
    compatible: Relation
    has_sym: Relation


def D4Map(Key: TypeArg, Val: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, src: Iterable[PyRow] | None = None, dst: Iterable[PyRow] | None = None) -> D4MapRows:
    """Runs `D4Map` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('D4Map', [Key, Val],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'src': Columns((Key, LibType.POSITION, Val, ), True), 'dst': Columns((Key, LibType.POSITION, Val, ), True), 'mismatch': Columns((Key, LibType.D4, ), True), 'map': Columns((Key, LibType.D4, ), True), 'conflict': Columns((Key, LibType.D4, ), True), 'compatible': Columns((Key, LibType.D4, ), True), 'has_sym': Columns((Key, ), True)},
               {'src': src, 'dst': dst},
               ['mismatch', 'map', 'conflict', 'compatible', 'has_sym'], sizes)
    return D4MapRows(got['mismatch'], got['map'], got['conflict'], got['compatible'], got['has_sym'])


class OffsetInvarianceRows(NamedTuple):
    """The output relations of `OffsetInvariance` (programs/lib/cells.dl)."""

    cand: Relation
    pair: Relation
    mismatch: Relation
    line_mismatch: Relation
    period: Relation
    min_period: Relation


def OffsetInvariance(Key: TypeArg, Val: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None) -> OffsetInvarianceRows:
    """Runs `OffsetInvariance` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('OffsetInvariance', [Key, Val],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, Val, ), True), 'cand': Columns((Key, LibType.AXIS, Primitive.NUMBER, LibType.OFFSET, ), True), 'pair': Columns((Key, LibType.AXIS, Primitive.NUMBER, LibType.POSITION, LibType.POSITION, ), True), 'mismatch': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'line_mismatch': Columns((Key, LibType.AXIS, Primitive.NUMBER, LibType.POSITION, LibType.POSITION, ), True), 'period': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'min_period': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True)},
               {'cell': cell},
               ['cand', 'pair', 'mismatch', 'line_mismatch', 'period', 'min_period'], sizes)
    return OffsetInvarianceRows(got['cand'], got['pair'], got['mismatch'], got['line_mismatch'], got['period'], got['min_period'])


class WallpaperRows(NamedTuple):
    """The output relations of `Wallpaper` (programs/lib/cells.dl)."""

    symmetry: Relation
    action: Relation


def Wallpaper(Key: TypeArg, Val: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, transform: Iterable[PyRow] | None = None, cell: Iterable[PyRow] | None = None, grid: Iterable[PyRow] | None = None, period: Iterable[PyRow] | None = None) -> WallpaperRows:
    """Runs `Wallpaper` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Wallpaper', [Key, Val],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'transform': Columns((LibType.D4, ), False), 'cell': Columns((Key, LibType.POSITION, Val, ), True), 'grid': Columns((Key, LibType.POSITION, ), True), 'period': Columns((Key, LibType.AXIS, Primitive.NUMBER, ), True), 'symmetry': Columns((Key, LibType.D4, LibType.OFFSET, ), True), 'action': Columns((Key, LibType.POSITION, LibType.POSITION, ), True)},
               {'transform': transform, 'cell': cell, 'grid': grid, 'period': period},
               ['symmetry', 'action'], sizes)
    return WallpaperRows(got['symmetry'], got['action'])


class OccurrencesRows(NamedTuple):
    """The output relations of `Occurrences` (programs/lib/cells.dl)."""

    placement: Relation
    mismatch: Relation
    occurrence: Relation


def Occurrences(Key: TypeArg, Val: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cell: Iterable[PyRow] | None = None, shape: Iterable[PyRow] | None = None) -> OccurrencesRows:
    """Runs `Occurrences` (programs/lib/cells.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('Occurrences', [Key, Val],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cell': Columns((Key, LibType.POSITION, Val, ), True), 'shape': Columns((Key, LibType.POSITION, Val, ), True), 'placement': Columns((Key, LibType.POSITION, ), True), 'mismatch': Columns((Key, LibType.POSITION, ), True), 'occurrence': Columns((Key, LibType.POSITION, ), True)},
               {'cell': cell, 'shape': shape},
               ['placement', 'mismatch', 'occurrence'], sizes)
    return OccurrencesRows(got['placement'], got['mismatch'], got['occurrence'])


class CoverForcingRows(NamedTuple):
    """The output relations of `CoverForcing` (programs/lib/constraints.dl)."""

    forced: Relation
    ruled_out: Relation


def CoverForcing(Key: TypeArg, Piece: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, covers: Iterable[PyRow] | None = None, conflict: Iterable[PyRow] | None = None) -> CoverForcingRows:
    """Runs `CoverForcing` (programs/lib/constraints.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('CoverForcing', [Key, Piece],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'covers': Columns((Key, Piece, LibType.POSITION, ), True), 'conflict': Columns((Key, Piece, Piece, ), True), 'forced': Columns((Key, Piece, ), True), 'ruled_out': Columns((Key, Piece, ), True)},
               {'covers': covers, 'conflict': conflict},
               ['forced', 'ruled_out'], sizes)
    return CoverForcingRows(got['forced'], got['ruled_out'])


class PlacementPruningRows(NamedTuple):
    """The output relations of `PlacementPruning` (programs/lib/constraints.dl)."""

    dead: Relation
    alive: Relation


def PlacementPruning(Key: TypeArg, Cand: TypeArg, Piece: TypeArg, *, sizes: Mapping[PyValue, Size] | None = None, cand: Iterable[PyRow] | None = None, conflict: Iterable[PyRow] | None = None) -> PlacementPruningRows:
    """Runs `PlacementPruning` (programs/lib/constraints.dl) over the rows given, a cell of each `Position` column in the grid of `sizes` for its key, or in the one grid of `sizes` where the relation has no key, and each `Offset` column as a (row, column) displacement."""
    got = call('PlacementPruning', [Key, Cand, Piece],
               GridTypes(LibType.POSITION, LibType.OFFSET),
               {'cand': Columns((Key, Cand, Piece, ), True), 'conflict': Columns((Key, Cand, Cand, ), True), 'dead': Columns((Key, Cand, ), True), 'alive': Columns((Key, Cand, Piece, ), True)},
               {'cand': cand, 'conflict': conflict},
               ['dead', 'alive'], sizes)
    return PlacementPruningRows(got['dead'], got['alive'])
