"""The columns of a whole atom over a full candidate set, from its tokens by name. Training rows and a worker share them."""
import re

import numpy as np

CMP = {'=', '!=', '<', '<=', '>', '>='}
GROUP = {'OR', 'ALL', 'IF', 'ALSO'}
STRUCT = ['n_tokens', 'n_columns', 'n_fresh', 'n_key', 'n_join', 'n_zero', 'negated', 'is_end', 'is_group', 'is_comparison', 'n_labels', 'last_column', 'record']
CAND = ['atom:' + x for x in STRUCT] + ['atom:defined', 'atom:first_bits', 'atom:first_gap', 'atom:first_rank', 'atom:same_first', 'atom:set_size']
_COLUMN = re.compile(r':\d+')
_LABEL = re.compile(r'L\d+')


def structure(names):
    """The STRUCT columns of an atom's tokens, by name."""
    column = [i for i, x in enumerate(names) if _COLUMN.fullmatch(x)]
    labels = {x for x in names if _LABEL.fullmatch(x)}
    first = names[0]
    is_column = [bool(_COLUMN.fullmatch(x)) for x in names]
    return [len(names), len(column), names.count('*'), names.count('^'), sum(bool(_LABEL.fullmatch(x)) for x in names), names.count('0'), float(first == 'NOT'), float(first == 'END'), float(first in GROUP), float(first in CMP or (first == 'NOT' and len(names) > 1 and names[1] in CMP)), len(labels), float(names[column[-1]][1:]) if column else -1.0, float(any(a and b for a, b in zip(is_column, is_column[1:])))]


def cand_rows(structures, first_of, first_bits, has_table):
    """The candidate block of a decision, n x len(CAND): structures, n x len(STRUCT); first_of, each candidate's place in first_bits; has_table, whether the engine gives it a table."""
    S = np.asarray(structures, np.float32)
    n = len(S)
    first_of = np.asarray(first_of)
    bits = np.asarray(first_bits, np.float32)
    rank = np.argsort(np.argsort(bits, kind='stable'), kind='stable')
    same = np.bincount(first_of, minlength=len(bits))
    return np.concatenate([S, np.asarray(has_table, np.float32)[:, None], bits[first_of][:, None], (bits[first_of] - bits.min())[:, None], rank[first_of][:, None].astype(np.float32), same[first_of][:, None].astype(np.float32), np.full((n, 1), n, np.float32)], 1)
