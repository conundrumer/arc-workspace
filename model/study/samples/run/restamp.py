"""Restamps row stores built on one engine site as built on another, for tasks whose stores the two engines give alike.

An engine release that changes the tables of some tasks only (its own list of affected tasks) leaves the other tasks' stores as they are. Their headers
still name the old site, and the stages refuse a task whose stages name two query_hash_versions. This rewrites the header's hash_version and
query_hash_version of each store that names OLD, except the tasks in --skip, to a temp file and then a rename.

  python3 restamp.py ROWS_DIR OLD NEW [--skip id,id,...]      OLD and NEW are site folder names, such as site-exp50 and site-exp59
"""
import argparse
import gzip
import json
import os
import tempfile
from pathlib import Path

ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
ap.add_argument('rows', type=Path)
ap.add_argument('old')
ap.add_argument('new')
ap.add_argument('--skip', default='', help='id,id: the tasks the new engine changes, which are built again instead')
a = ap.parse_args()
skip = set(filter(None, a.skip.split(',')))
done = kept = 0
for p in sorted(a.rows.glob('*.jsonl.gz')):
    task = p.name.removesuffix('.jsonl.gz')
    with gzip.open(p, 'rt') as f:
        head = json.loads(f.readline())
    if task in skip or head.get('hash_version') != 'engine@' + a.old:
        kept += 1
        continue
    with gzip.open(p, 'rt') as f:
        lines = f.read().splitlines()
    head = json.loads(lines[0])
    head['hash_version'] = 'engine@' + a.new
    head['query_hash_version'] = head['query_hash_version'].replace(a.old, a.new)
    lines[0] = json.dumps(head)
    fd, tmp = tempfile.mkstemp(dir=a.rows, suffix='.restamp')
    os.close(fd)
    with gzip.open(tmp, 'wt') as f:
        f.write('\n'.join(lines) + '\n')
    os.replace(tmp, p)
    done += 1
print(f'{a.rows}: {done} restamped from {a.old} to {a.new}, {kept} left as they are')
