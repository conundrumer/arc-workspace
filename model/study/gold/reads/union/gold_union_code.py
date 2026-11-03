"""The code stamp of the union outputs: the sha of HEAD, and whether the code differs from it.

  stamp() -> {"sha": <40 hex digits of HEAD>, "dirty": <bool>, "engine": <the folder of the arclog package, as site-exp46, or null where arclog isn't importable>}    dirty is true when any file under model/study/gold/reads/union or src/arclog_convert differs from HEAD: modified, staged, deleted or untracked (ignored files don't count). Read once for each process.
  header(), write_sidecar(output), concat_sidecar(output, shards)

An output records the stamp as follows.
- fits-SET.jsonl: its first line is {"t": "header", "code": <stamp>}. A reader of the file skips that line.
- union-SET.manifest.json: the key `code`.
- Any other output: the file <output>.code.json holding {"code": <stamp>}.

  python gold_union_code.py                      prints the stamp
  python gold_union_code.py concat OUT SHARD...  writes OUT.code.json from the SHARD.code.json files (the one stamp they share; else "code" is null and "mixed" lists the stamps), for an output made by concatenating shard outputs
"""
import functools, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PATHS = ['model/study/gold/reads/union', 'src/arclog_convert']


@functools.cache
def stamp():
    """{"sha", "dirty"} of the code now."""
    git = ['git', '-C', str(ROOT)]
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')  # a read must not take the index lock
    sha = subprocess.run(git + ['rev-parse', 'HEAD'], capture_output=True, text=True, check=True, env=env).stdout.strip()
    changed = subprocess.run(git + ['status', '--porcelain', '--untracked-files=all', '--'] + PATHS, capture_output=True, text=True, check=True, env=env).stdout
    try:
        import arclog
        engine = Path(arclog.__file__).resolve().parents[1].name
    except ImportError:
        engine = None
    return dict(sha=sha, dirty=bool(changed.strip()), engine=engine)


def header():
    """The first line of a merged fits file, with its newline."""
    return json.dumps(dict(t='header', code=stamp())) + '\n'


def write_sidecar(output):
    """Writes <output>.code.json."""
    with open(str(output) + '.code.json', 'w') as f:
        f.write(json.dumps(dict(code=stamp())) + '\n')


def concat_sidecar(output, shards):
    """Writes <output>.code.json for an output made from the shard outputs."""
    codes = []
    for s in shards:
        c = json.load(open(str(s) + '.code.json'))['code']
        if c not in codes:
            codes.append(c)
    with open(str(output) + '.code.json', 'w') as f:
        f.write(json.dumps(dict(code=codes[0]) if len(codes) == 1 else dict(code=None, mixed=codes)) + '\n')


if __name__ == '__main__':
    if sys.argv[1:2] == ['concat']:
        concat_sidecar(sys.argv[2], sys.argv[3:])
    else:
        print(json.dumps(stamp()))
