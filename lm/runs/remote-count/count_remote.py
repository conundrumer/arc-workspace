"""Counts the remote fields of a tables export: fields whose column's sources are all in other derived tables.

    python count_remote.py <tables dir> <cache pickle> [max rows, default 4000]

ALLOW_CHECK_VIOLATIONS=1 in the environment builds the cache through a violation of the export's checks.txt.

For each remote column of each derived table (tables over the row cap left out, as the run leaves them unseen):
the key group of a row is the rows of the same entry that agree with it on every other column that shares a
source table with the column. Per value type and per source-table size: the fields; the fields whose value a
visible row of the same group also holds (the leak a field mask leaves open); and, for pointer types, the fields
whose value a row outside the group holds (a target that remains once the group is hidden)."""
import os, sys, time, collections
import numpy as np
sys.path.insert(0, "lm")
import encoder as E

tables_dir, cache = sys.argv[1], sys.argv[2]
max_rows = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
t0 = time.time()
tables, skipped, _ = E.load_tables(tables_dir, cache, allow_violations=bool(os.environ.get("ALLOW_CHECK_VIOLATIONS")))
print(f"{len(tables)} programs loaded in {time.time() - t0:.0f} s; {len(skipped)} skipped", flush=True)

BUCKETS = [(0, "no table source"), (50, "1-50"), (200, "51-200"), (1000, "201-1000"), (max_rows, f"1001-{max_rows}"),
           (10 ** 9, f"over {max_rows} (unseen)")]
def bucket(n):
    for hi, name in BUCKETS:
        if n <= hi:
            return name

def codes(a):
    """One int per row of a 2-d array, equal for equal rows."""
    return np.unique(a, axis=0, return_inverse=True)[1].reshape(-1)

C = collections.Counter    # keys: (type, bucket, measure)
stat, groups, columns = C(), [], C()
no_prov = 0
for p, (key, ts) in enumerate(tables.items()):
    if not E.provenance(ts):
        no_prov += 1; continue
    src = E.column_sources(ts)
    for j, t in enumerate(ts):
        if t.evidence or t.flows is None or not t.n or t.n > max_rows:
            continue
        lab = E.column_labels(ts, j)
        off = np.cumsum([0] + [E.width(ty) for ty in t.types])
        for c in np.flatnonzero(lab == E.REMOTE):
            ty = t.types[c]
            st = {i for i, _ in src[j][c]}
            size = max((ts[i].n for i in st), default=0)
            b = bucket(size) if st else "no table source"
            if st and any(ts[i].n > max_rows for i in st):
                b = BUCKETS[-1][1]
            pres = t.present[:, c] & ~t.marker
            if not pres.any():
                continue
            keycols = [k for k in range(len(t.types)) if k != c and any(i in st for i, _ in src[j][k])]
            parts = [t.entry[:, None]] + [np.concatenate([t.present[:, k:k + 1], t.cells[:, off[k]:off[k + 1]]], 1)
                                         for k in keycols]
            g = codes(np.concatenate(parts, 1).astype(np.int64))[pres]
            v = codes(t.cells[:, off[c]:off[c + 1]].astype(np.int64))[pres]
            n = int(pres.sum())
            # per field: another visible row of the same group with the same value (leak); a row of another group
            # with the same value (target); any other row with the same value
            gv = g.astype(np.int64) * (v.max() + 1) + v
            _, inv, cnt = np.unique(gv, return_inverse=True, return_counts=True)
            leak = cnt[inv.reshape(-1)] > 1
            _, vi, vcnt = np.unique(v, return_inverse=True, return_counts=True)
            anywhere = vcnt[vi.reshape(-1)] > 1
            pairs = np.unique(np.stack([v, g], 1), axis=0)
            _, pv, gcnt = np.unique(pairs[:, 0], return_inverse=True, return_counts=True)
            groups_per_value = dict(zip(pairs[:, 0][np.unique(pv, return_index=True)[1]], gcnt))
            target = np.array([groups_per_value[x] > 1 for x in v], bool)
            stat[(ty, b, "fields")] += n
            stat[(ty, b, "leak")] += int(leak.sum())
            stat[(ty, b, "target")] += int(target.sum())
            stat[(ty, b, "anywhere")] += int(anywhere.sum())
            columns[(ty, len(st))] += 1
            groups.append(n / len(np.unique(g)))
    if (p + 1) % 500 == 0:
        print(f"  {p + 1} programs, {time.time() - t0:.0f} s", flush=True)

print(f"\n{no_prov} programs without provenance left out")
print(f"remote columns by (type, source tables): {sorted(columns.items())}")
print(f"mean rows per key group: {np.mean(groups):.1f} (median {np.median(groups):.1f})\n")
types = sorted({k[0] for k in stat}); buckets = [b for _, b in BUCKETS]
print(f"{'type':10} {'source size':20} {'fields':>9} {'leak':>7} {'target':>7} {'anywhere':>9}")
for ty in types:
    for b in buckets:
        n = stat[(ty, b, "fields")]
        if not n:
            continue
        f = lambda m: f"{stat[(ty, b, m)] / n:7.2f}"
        print(f"{ty:10} {b:20} {n:9d} {f('leak')} {f('target')} {f('anywhere')}")
    n = sum(stat[(ty, b, "fields")] for b in buckets)
    print(f"{ty:10} {'all':20} {n:9d}")
