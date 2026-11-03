"""The written order, restored on purpose, to price it. Nothing here enters a clean model: FL.check refuses these names.

An arm is a function of a row: the facts it adds and the context it keeps.

  set+order        the clean facts of the other atoms, plus the left-out atom's index, the head written just before it, and the heads written before it
  prefix           only the atoms written before the left-out atom are kept, with no index and no last head
  prefix+order     the same, plus the index and the last head
  subset           a random subset of the other atoms, of a size drawn uniformly. Over a body's atoms, prefix sizes are uniform too, so the two arms have the same sizes, and here the size says nothing of position
"""
import random
import zlib

import features_ofree_facts as FL

ORDER_FAMILIES = {
    'k': "the left-out atom's written index",
    'last': 'the head written just before the left-out atom',
    'before': 'a head written before the left-out atom',
}


def written_facts(r):
    w = r['written']
    out = ['k:%d' % min(w['k'], 8)]
    c = r['ctx']
    if w['last'] >= 0:
        out.append('last:' + str(c[w['last']]['t']))
    else:
        out.append('last:none')
    out += ['before:' + str(c[i]['t']) for i in w['before']]
    return out


def checked_order(names):
    for n in names:
        if n.partition(':')[0] not in ORDER_FAMILIES:
            raise FL.BannedFact(n)
    return names


def subset_keep(r, rec, seed=0):
    who = sorted(str(c['t']) + c['w'] for c in r['ctx'])
    rng = random.Random(zlib.crc32(('%s %s %s %d' % (rec['task'], rec['line'], who, seed)).encode()))
    return sorted(rng.sample(range(len(r['ctx'])), rng.randint(0, len(r['ctx']))))


def arm(name, tier):
    """(facts of a row, facts of an option at a row) of an arm, at a clean tier."""
    if name == 'clean':
        return (lambda r, rec: FL.row_facts(r, rec, tier)), (lambda o, r, rec: FL.option_facts(o, r, rec, tier))
    if name == 'set+order':
        return (lambda r, rec: list(FL.row_facts(r, rec, tier)) + checked_order(written_facts(r))), (lambda o, r, rec: FL.option_facts(o, r, rec, tier))
    if name == 'prefix':
        return (lambda r, rec: FL.row_facts(r, rec, tier, keep=r['written']['before'])), (lambda o, r, rec: FL.option_facts(o, r, rec, tier, keep=r['written']['before']))
    if name == 'prefix+order':
        return (lambda r, rec: list(FL.row_facts(r, rec, tier, keep=r['written']['before'])) + checked_order(['k:%d' % min(r['written']['k'], 8), 'last:' + (str(r['ctx'][r['written']['last']]['t']) if r['written']['last'] >= 0 else 'none')])), (lambda o, r, rec: FL.option_facts(o, r, rec, tier, keep=r['written']['before']))
    if name == 'subset':
        return (lambda r, rec: FL.row_facts(r, rec, tier, keep=subset_keep(r, rec))), (lambda o, r, rec: FL.option_facts(o, r, rec, tier, keep=subset_keep(r, rec)))
    raise KeyError(name)
