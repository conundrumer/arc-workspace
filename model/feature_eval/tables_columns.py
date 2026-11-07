"""A table's rows as column arrays, and the framed binary stream that carries them to the encoder.

A `Block` holds the rows of one TableRows as a numpy array of 32-bit integers, one row per line, with a Position, a
Box or an Offset as four consecutive numbers and any other cell as one. `write_stream` prints the tables of a
task as `tables_stream.rs` in the encoder reads them: a head, then each table of the state, then each item with its
tables, and an end. The layout of the stream is in the header of that file.
"""
import json
import os
import struct
import sys

import numpy as np

BOX_TYPES = ('Position', 'Box', 'Offset')
# The types whose numbers are not orientation constants.
PLAIN_TYPES = ('Number', 'Nat', 'Int', 'Color', 'Example', 'Ident')
MAGIC = b'ARCTBL1\n'


def kind_of(ty):
    return 'box' if ty in BOX_TYPES else 'plain' if ty in PLAIN_TYPES else 'orient'


class Layout:
    """The columns of a table's rows: their types, how many numbers each takes, and the names of orientation constants."""

    def __init__(self, types, orient):
        self.types = list(types)
        self.kinds = [kind_of(ty) for ty in self.types]
        self.widths = [4 if kind == 'box' else 1 for kind in self.kinds]
        self.orient = orient


class Block:
    """The rows of one TableRows, which are compared and listed as a sorted list of rows is."""
    __slots__ = ('layout', 'cells', 'sorted')

    def __init__(self, layout, cells):
        self.layout = layout
        self.cells = cells
        self.sorted = None

    def __len__(self):
        return self.cells.shape[0]

    def canonical(self):
        """The rows in the order of their numbers, column by column."""
        if self.sorted is None:
            cells = self.cells
            if cells.shape[0] > 1 and cells.shape[1] > 0:
                cells = cells[np.lexsort(cells.T[::-1])]
            self.sorted = cells
        return self.sorted

    def __eq__(self, other):
        if not isinstance(other, Block):
            return NotImplemented
        return self.layout.kinds == other.layout.kinds and self.cells.shape == other.cells.shape and np.array_equal(self.canonical(), other.canonical())

    __hash__ = None

    def listed(self):
        """The rows as lists, in the order of their numbers: a box as its four margins, an orientation constant as its name."""
        cells = self.canonical()
        columns = []
        start = 0
        for kind, width in zip(self.layout.kinds, self.layout.widths):
            part = cells[:, start:start + width]
            start += width
            if kind == 'box':
                columns.append(part.tolist())
            else:
                column = part[:, 0].tolist()
                if kind == 'orient':
                    orient = self.layout.orient
                    column = [orient.get(value, value) for value in column]
                columns.append(column)
        if not columns:
            return [[] for _ in range(len(self))]
        return [list(row) for row in zip(*columns)]


def json_default(value):
    """For `json.dumps`: the rows of a Block as lists."""
    if isinstance(value, Block):
        return value.listed()
    raise TypeError(f'{type(value).__name__} is not JSON serializable')


def widths_of(types):
    return [4 if kind_of(ty.split('@')[0]) == 'box' else 1 for ty in types]


def models_of(table):
    """The key and the TableRows of each example of a table that has its rows."""
    return [(key, [block]) for key, block in table['rows'].items()] + list(table['models'].items())


def table_header_body(table):
    """A table's header, which holds its fields but its rows, and its body, as a list of byte strings."""
    header = {key: value for key, value in table.items() if key not in ('rows', 'models')}
    held = models_of(table)
    header['widths'] = widths_of(table['types'])
    header['layout'] = [[key, [len(block) for block in blocks]] for key, blocks in held]
    names = {}
    parts = []
    for _, blocks in held:
        for block in blocks:
            start = 0
            for kind, width in zip(block.layout.kinds, block.layout.widths):
                column = block.cells[:, start:start + width]
                if kind == 'orient':
                    for value in np.unique(column).tolist():
                        if value in block.layout.orient:
                            names[str(value)] = block.layout.orient[value]
                parts.append(np.ascontiguousarray(column, dtype='<i4').tobytes())
                start += width
    header['orient'] = names
    return header, parts


def frame(out, tag, header, parts=()):
    text = json.dumps(header, separators=(',', ':')).encode()
    out.write(tag + struct.pack('<I', len(text)) + text + struct.pack('<Q', sum(len(part) for part in parts)))
    for part in parts:
        out.write(part)


def write_stream(full, out=None):
    """Prints a task's tables: `full` holds the fields of a tables file, with each table's rows as Blocks. A reader that sets `TABLES_STREAM=1` takes the framed
    stream, and any other reader takes the tables as JSON text."""
    if out is None and os.environ.get('TABLES_STREAM') != '1':
        json.dump(full, sys.stdout, default=json_default)
        sys.stdout.flush()
        return
    own = out is None
    if own:
        out = os.fdopen(1, 'wb', buffering=1 << 20, closefd=False)
    out.write(MAGIC)
    frame(out, b'H', {key: value for key, value in full.items() if key not in ('items', 'prefix')})
    # In the order of their names, as a reader of a tables file takes them, so tables are made in one order.
    for name, table in sorted(full['prefix'].items()):
        if table is None:
            continue
        header, parts = table_header_body(table)
        frame(out, b'P', dict(header, name=name), parts)
    for item in full['items']:
        meta = {key: value for key, value in item.items() if key not in ('gold', 'mutants')}
        meta['mutants'] = [{key: value for key, value in mutant.items() if key != 'table'} for mutant in item['mutants']]
        frame(out, b'I', meta)
        for table in [item['gold']] + [mutant['table'] for mutant in item['mutants']]:
            header, parts = table_header_body(table)
            frame(out, b'T', header, parts)
    frame(out, b'E', {})
    out.flush()
