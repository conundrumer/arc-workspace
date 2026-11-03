"""Records the sha256 of the frozen files of the kind read in manifest.json of the record, under `kind_frozen`. Run it after fit-read.py has written frozen-fit.json and cover-read.py has written frozen-size-fit.json, and before any held read: fit-read.py, cover-read.py and read-map.py stop unless these hashes equal the files.

  python3 -I kind/record-frozen.py        (any python)

A file that is not there yet is left out. The manifest is rewritten whole, with the other keys as they stand.
"""
import hashlib
import json
import os

H = os.path.dirname(os.path.abspath(__file__)) + '/'
M = H.rsplit('/kind/', 1)[0] + '/manifest.json'
FILES = ('frozen-fit.json', 'frozen-size-fit.json', 'scope_facts.py', 'build-gold-rows.py')

m = json.load(open(M))
m['kind_frozen'] = {f: hashlib.sha256(open(H + f, 'rb').read()).hexdigest() for f in FILES if os.path.exists(H + f)}
tmp = M + '.tmp'
json.dump(m, open(tmp, 'w'), indent=1)
os.replace(tmp, M)
print(json.dumps(m['kind_frozen'], indent=1))
