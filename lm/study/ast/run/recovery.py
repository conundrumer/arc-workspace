"""Exact finite equality-selection/projection witnesses over full train rows.

A witness uses one fixed projection and a conjunction (possibly empty) of
column=literal and column=column predicates, shared by every train input.
Constants are typed, complete column values, including four-margin Boxes.
It proves row recoverability on the train inputs, not program correctness.
"""
from functools import lru_cache
import hashlib
import json

VERSION=1


def canonical(ty):return 'Box' if ty=='Position' else 'Number' if ty=='number' else ty


def pack(table,n_train):
    if table['inputs'] is None:return None
    widths=[4 if t in ('Box','Position','Offset') else 1 for t in table['types']]
    result=[]
    for train in range(1,n_train+1):
        inp=next((x for x in table['inputs'] if x['train']==train),None)
        if inp is None or 'full_rows' not in inp:return None
        logical=[]
        for row in inp['full_rows']:
            at=0;cells=[]
            for width in widths:cells.append(tuple(row[at:at+width]));at+=width
            if at!=len(row):raise ValueError('physical row does not match schema')
            logical.append(tuple(cells))
        result.append(tuple(sorted(set(logical))))
    return tuple(canonical(t) for t in table['types']),tuple(result)


def _selection(gold,mutant,projection,types,domains):
    """Exact set-cover search, preserving >=1 witness of every gold row."""
    flat=[];targets=[];bad=0;allmask=0
    for gs,ms in zip(gold,mutant):
        groups={g:0 for g in gs}
        for row in ms:
            i=len(flat);flat.append(row);bit=1<<i;allmask|=bit
            projected=tuple(row[c] for c in projection)
            if projected in groups:groups[projected]|=bit
            else:bad|=bit
        if any(not mask for mask in groups.values()):return None
        targets.extend(groups.values())
    if not bad:return []
    if not targets:
        # A contradictory pair of well-typed constants selects no rows. The
        # constants need not occur in the mutant; no nonempty gold target can
        # ever use such a constant, which is why the general search below only
        # needs observed values.
        for col,ty in enumerate(types):
            if ty in ('Box','Position'):values=[(0,0,0,0),(1,0,0,0)]
            elif ty=='Offset':values=[(0,0,0,0),(1,-1,0,0)]
            elif ty in ('Color','Number','Ident','Example'):values=[(0,),(1,)]
            else:values=[(v,) for v in domains.get(ty,[])[:2]]
            if len(values)>=2:return [dict(kind='column_constant',column=col,value=list(v)) for v in values]
        return None
    # Any usable equality must individually retain a witness of every target.
    # Hence a constant must occur in every target's preimage. This finite
    # intersection is complete, including constants absent from some examples
    # where gold is empty; constants outside it cannot be valid witnesses.
    width=len(flat[0]) if flat else 0
    atoms=[]
    def add(atom,predicate):
        mask=sum(1<<i for i,row in enumerate(flat) if predicate(row))
        if bad&~mask and all(mask&t for t in targets):atoms.append((atom,mask))
    for col in range(width):
        values=None
        for group in targets:
            here=set();bits=group
            while bits:
                bit=bits&-bits;bits-=bit;here.add(flat[bit.bit_length()-1][col])
            values=here if values is None else values&here
            if not values:break
        for value in sorted(values or []):
            add(dict(kind='column_constant',column=col,value=list(value)),lambda row,c=col,v=value:row[c]==v)
    for left in range(width):
        for right in range(left+1,width):
            # Caller validates type compatibility; equal raw values of unlike
            # logical types never constitute an equality predicate.
            if types[left]==types[right]:
                add(dict(kind='columns_equal',left=left,right=right),lambda row,a=left,b=right:row[a]==row[b])
    # Predicates with the same retained rows are interchangeable.
    unique={}
    for atom,mask in atoms:unique.setdefault(mask,atom)
    atoms=[(atom,mask) for mask,atom in unique.items()]
    if bad & ~sum_mask_complement(atoms,allmask):return None
    seen=set()
    def search(allowed):
        remaining=bad&allowed
        if not remaining:return []
        if allowed in seen:return None
        seen.add(allowed)
        bit=remaining&-remaining
        choices=[(a,m) for a,m in atoms if not m&bit and all(allowed&m&t for t in targets)]
        choices.sort(key=lambda x:(remaining&x[1]).bit_count())
        for atom,mask in choices:
            rest=search(allowed&mask)
            if rest is not None:return [atom]+rest
        return None
    return search(allmask)


def sum_mask_complement(atoms,allmask):
    result=0
    for _,mask in atoms:result|=allmask&~mask
    return result


@lru_cache(maxsize=512)
def table_witness(gpacked,mpacked,domains=()):
    if gpacked is None or mpacked is None:return dict(status='unknown',reason='unseen or incomplete full rows')
    gt,gr=gpacked;mt,mr=mpacked
    candidates=[]
    for c,ty in enumerate(gt):
        needed=[{row[c] for row in rows} for rows in gr];choices=[];seen=set()
        for j,mty in enumerate(mt):
            if ty!=mty:continue
            column=tuple(tuple(row[j] for row in rows) for rows in mr)
            if column in seen:continue
            seen.add(column)
            if all(values<={row[j] for row in rows} for values,rows in zip(needed,mr)):choices.append(j)
        if not choices:return dict(status='determined',recoverable=False)
        candidates.append(choices)
    # Branch first on the most constrained gold columns. A partial projection
    # must cover every partial gold row, an exact necessary pruning rule.
    order=sorted(range(len(gt)),key=lambda i:len(candidates[i]));mapping=[None]*len(gt)
    def visit(depth):
        if depth==len(gt):
            selected=_selection(gr,mr,mapping,mt,dict(domains))
            if selected is not None:return dict(status='determined',recoverable=True,projection=list(mapping),selection=selected)
            return None
        col=order[depth]
        for mcol in candidates[col]:
            mapping[col]=mcol
            cols=order[:depth+1]
            if all({tuple(row[c] for c in cols) for row in grows}<={tuple(row[mapping[c]] for c in cols) for row in mrows}
                   for grows,mrows in zip(gr,mr)):
                witness=visit(depth+1)
                if witness:return witness
        mapping[col]=None
        return None
    return visit(0) or dict(status='determined',recoverable=False)


def verify_witness(gpacked,mpacked,witness):
    if not witness.get('recoverable'):return False
    _,gold=gpacked;_,mutant=mpacked
    def holds(row):
        return all(row[p['column']]==tuple(p['value']) if p['kind']=='column_constant' else row[p['left']]==row[p['right']]
                   for p in witness['selection'])
    return all(set(g)=={tuple(row[c] for c in witness['projection']) for row in m if holds(row)} for g,m in zip(gold,mutant))

