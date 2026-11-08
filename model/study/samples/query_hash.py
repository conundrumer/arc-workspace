"""The QueryHash of a query, behind one function: the engine's `query_hash` (the hash of the resolver's content of the query, free of the names that the scope gives its tables; the same under relabelling, atom order and OR branch order).

`query_hash` is a method of a program that holds the query and the queries it uses, closed by an OUT. The engine's wheel is on PYTHONPATH (its site folder, such as `site-exp10`) with ARCLOG_IDENT_SOURCE=value; `VERSION` is the folder's name and `query_hash`.
"""
import os
from pathlib import Path

import arclog  # pyright: ignore[reportMissingImports]

VERSION = Path(str(arclog.__file__)).resolve().parent.parent.name + '+query_hash'
READER_OUT = '(OUT (input ^P ^Col))'  # the reader takes whole programs; this closes a scope's text


def query_hash(scope: list[str], text: str) -> str:
    """The hash of the query `text` over the lines of `scope`, which hold every query that `text` uses and whose labels `text` names; 32 hex digits. Raises arclog.Refusal where the engine refuses the program."""
    if os.environ.get('ARCLOG_IDENT_SOURCE') != 'value':
        raise RuntimeError('QueryHash needs ARCLOG_IDENT_SOURCE=value')
    program = arclog.StudyProgram.from_sexp('\n'.join([*scope, text, READER_OUT]))
    return format(program.query_hash(len(scope)), '032x')
