"""Check of the state search, an in-progress feature: what a run's files show against the contract (docs/state-search/state-search-spec.md). It gates nothing.

    PYTHONPATH=model/study/sampler:<engine path> <python> check_state_search.py out/NAME/TASK

Each case prints PASS or FAIL with what failed. The cases are what the run's caller sees: the bank file's visited set and the expansion records.
"""
import collections
import glob
import json
import pickle
import sys

OUTCOMES = {'new state', 'known state', 'no table', 'failed'}
FIELDS = {'v', 'n', 'seconds', 'state', 'score', 'query', 'kind', 'bits', 'outcome', 'child', 'new', 'flags'}


def main():
    w = sys.argv[1]
    bank = next(iter(glob.glob(w + '/work/*.out.jsonl.bank')), None)
    exp = next(iter(glob.glob(w + '/work/*.out.jsonl.expansions')), None)
    res = []

    def case(name, ok, why=''):
        res.append(ok)
        print('%s  %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else ': ' + why))
    case('bank file and expansion records exist', bool(bank and exp), 'bank %s, expansions %s' % (bank, exp))
    if not (bank and exp):
        return
    b = pickle.load(open(bank, 'rb'))
    queries, tables, x = b['forms'], b['nodes'], b.get('state_search')
    case('the bank holds the visited set', x is not None, 'no state_search entry')
    if x is None:
        return
    states = {r[0]: r for r in x['states']}
    raw = [json.loads(l) for l in open(exp)]
    last = {}
    for r in raw:  # a worker that restarts from the bank goes on from its expansion count; the later record of a count is the one the bank holds
        last[r['n']] = r
    recs = [last[n] for n in sorted(last) if n <= x['expanded']]
    print('info: %d record lines, %d replaced by a later process, %d past the bank (a worker that ended after its last save)' % (
        len(raw), len(raw) - len(last), sum(1 for n in last if n > x['expanded'])))
    bad = [r['n'] for r in recs if set(r) != FIELDS or r['outcome'] not in OUTCOMES or r['v'] != 4]
    case('each expansion record has the schema fields and a known outcome', not bad, '%d bad, first %s' % (len(bad), bad[:3]))
    ns = [r['n'] for r in recs]
    case('expansion counts are 1..N in order, one record each', ns == list(range(1, len(ns) + 1)), 'first gap near %s' % next((i + 1 for i, n in enumerate(ns) if n != i + 1), None))
    hashes = [q.query_hash for q in queries.values()]
    case('one query per QueryHash', len(hashes) == len(set(hashes)), '%d queries, %d hashes' % (len(hashes), len(set(hashes))))
    sets = [frozenset(r[1]) for r in states.values()]
    case('one state per query set', len(sets) == len(set(sets)), '%d states, %d sets' % (len(sets), len(set(sets))))
    unclosed = [sid for sid, r in states.items() if any(p not in r[1] for q in r[1] for p in queries[q].parents)]
    case('each state is closed under inputs', not unclosed, '%d unclosed, first %s' % (len(unclosed), unclosed[:3]))
    qid_of = {q.query_hash: i for i, q in queries.items()}
    wrong = []
    for r in recs:
        if r['child'] is None:
            continue
        got = frozenset(states[r['state']][1]) | {qid_of[r['query']]}
        if frozenset(states[r['child']][1]) != got:
            wrong.append(r['n'])
    case('the expansion records rebuild each state as parent plus one query', not wrong, '%d records disagree, first %s' % (len(wrong), wrong[:3]))
    children = collections.Counter(r['state'] for r in recs if r['outcome'] == 'new state')
    off = [sid for sid, r in states.items() if r[7] != children.get(sid, 0)]
    case("each state's children count equals its new-state records", not off, '%d differ, first %s' % (len(off), off[:3]))
    nohash = [t.id for t in tables.values() if t.hash is None or not isinstance(t.table, tuple) or not isinstance(t.at, tuple)]
    case('each table has a TableHash, a parameterized table (QueryHash, Name) and an assignment', not nohash, '%d without, first %s' % (len(nohash), nohash[:3]))
    novec = [t.id for t in tables.values() if t.features is None or len(t.features) == 0]
    case('each table has a TableVector', not novec, '%d without' % len(novec))
    norows = [t.id for t in tables.values() if t.rows]
    case('the search holds no rows', not norows, '%d tables with rows' % len(norows))
    keys = [(*t.table, t.at) for t in tables.values()]
    case('one table per parameterized table (QueryHash, Name) and assignment', len(keys) == len(set(keys)), '%d records, %d keys' % (len(keys), len(set(keys))))
    print('info: %d expansions, %d queries, %d tables, %d states, generation %d, %d processes, outcomes %s' % (
        len(recs), len(queries), len(tables), len(states), b.get('generation', 0), len(b.get('lineage', [])), dict(collections.Counter(r['outcome'] for r in recs))))
    print('summary: %d of %d cases pass' % (sum(res), len(res)))


if __name__ == '__main__':
    main()
