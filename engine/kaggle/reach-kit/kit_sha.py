#!/usr/bin/env python3
"""The kit's sha256: over its files in path order, less out/ and __pycache__, each as its path, a NUL, the file's sha256 and a newline.

  python3 kit_sha.py [KIT]
"""
import hashlib, os, sys

kit = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('UNION_REACH_OUT', '/Users/davidlu/code/arc-workspace/work/synth-kaggle/kit-union-read'), 'kit-union-read-79af0a4f2')
h, n = hashlib.sha256(), 0
for root, dirs, files in os.walk(kit):
    dirs[:] = sorted(d for d in dirs if d != '__pycache__' and not (root == kit and d == 'out'))
    for f in sorted(files):
        p = os.path.join(root, f)
        h.update(os.path.relpath(p, kit).encode() + b'\0' + hashlib.sha256(open(p, 'rb').read()).hexdigest().encode() + b'\n')
        n += 1
print(h.hexdigest(), n, 'files')
