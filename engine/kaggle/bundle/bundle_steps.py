#!/usr/bin/env python3
"""Builds a kernel bundle and its soak kit from a config file. It stops at the first failed pass condition, prints one line for each step, and forces nothing.

  bundle_steps.py <config.json> [steps]

`steps` is a comma list of step numbers (1 to 8), or `N:name` for one quick check of step 6. The default is all of them. A step reads its inputs from the
disk and the git worktree, so each step can run on its own after the ones before it. The config fields are described in config-example.json.

Steps: 1 inputs, 2 merge, 3 freeze, 4 build, 5 scratch, 6 checks, 7 kit, 8 next commands.
"""
import ast
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pass_conditions  # noqa: E402

REPO = '/Users/davidlu/code/arc-workspace'
SETTING_CONSTANTS = {'ONE_REPAIR': 'ONE_REPAIR_SECONDS', 'P_DAG': 'P_DAG_SETTING', 'ORDER_FREE': 'ORDER_FREE_SETTING', 'ARCLOG_IDENT_SOURCE': 'IDENT_SOURCE_SETTING'}
SCRATCH_SKIP = ('check-*', '*.out', 'times.txt', 'checks.json', 'kit-start*text.txt', '__pycache__', 'make-kit.py', 'make-manifest.py', 'build-params.json', 'pass-bar-time.txt')
SCRATCH_SKIP_PATHS = ('kit-files/run.sh', 'kit-files/last-ramp.json')
TEXT_SUFFIXES = ('.sh', '.py')
GENERIC_SCRIPTS = ('make-kit.py', 'make-manifest.py', 'write-records.py', 'pass_conditions.py')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731


class Stop(Exception):
    pass


def say(step, name, text):
    print('step %s %s: %s' % (step, name, text), flush=True)


def run(cmd, cwd=None, timeout=None, env=None, check=True):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise Stop('command failed (exit %d): %s\n%s' % (r.returncode, ' '.join(str(c) for c in cmd), (r.stdout + r.stderr).strip()[-1500:]))
    return r


class Ctx:
    def __init__(self, path):
        self.cfg = cfg = json.load(open(path))
        self.config_path = str(Path(path).resolve())
        self.repo = cfg.get('repo', REPO)
        self.out = Path(cfg.get('out_root', self.repo + '/work/synth-kaggle'))
        self.wt = cfg['worktree']
        self.base = Path(cfg['base_bundle'])
        if not self.base.is_absolute():
            self.base = self.out / self.base
        self.basec = self.base.name[len('kernel-bundle-'):]
        self.prev_soak = Path(cfg.get('prev_soak', self.base.parent / ('kernel-soak-%s-linux-ramp59-2400s' % self.basec)))
        self.check_root = cfg.get('check_root')
        self.py = cfg.get('python', self.repo + '/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python')
        self.policy = Path(cfg.get('policy_dir', self.repo + '/work/synth-kaggle/policy1'))
        self.wheel = Path(cfg['wheel']['path'])
        self.mac = cfg['mac']
        self.site = Path(self.mac['site'])
        self.quick_timeout = cfg.get('quick_timeout', 60)

    def git(self, *args, check=True):
        return run(['git', '-C', self.wt, *args], check=check)

    @property
    def head(self):
        return self.git('rev-parse', 'HEAD').stdout.strip()

    @property
    def c(self):
        return self.head[:9]

    @property
    def bundle(self):
        return self.out / ('kernel-bundle-' + self.c)

    @property
    def scratch(self):
        return self.bundle / 'scratch'

    @property
    def so_sha(self):
        return sha(self.site / 'arclog/arclog.abi3.so')

    def freeze_dir(self):
        fz = self.cfg['freeze']
        if fz.get('reuse'):
            return Path(fz['reuse'])
        return self.out / ('kernel-freeze-%s-%s' % (fz['name'], self.c))


def need(cond, text):
    if not cond:
        raise Stop(text)


def finished(x):
    need(not (x.bundle / 'manifest.json').exists(), '%s has a manifest.json: it is a finished bundle, and this script does not write into it' % x.bundle)


# ---- step 1
def step1(x):
    cfg = x.cfg
    for k in ('worktree', 'base_bundle', 'models', 'wheel', 'mac', 'freeze', 'manifest'):
        need(k in cfg, 'config has no field %s' % k)
    need(cfg['manifest'].get('commit'), 'config manifest.commit is empty')
    models = Path(cfg['models']['dir'])
    for name, want in cfg['models']['files'].items():
        got = sha(models / name)
        need(got.startswith(want) and len(want) >= 16, 'model %s sha256 %s does not start with %s' % (name, got[:16], want))
    got = sha(x.wheel)
    need(got.startswith(cfg['wheel']['sha256']) and len(cfg['wheel']['sha256']) >= 16, 'wheel sha256 %s, config says %s' % (got, cfg['wheel']['sha256']))
    need((x.site / 'arclog/arclog.abi3.so').exists(), 'no Mac site at %s' % x.site)
    if cfg['mac'].get('so_sha256'):
        need(x.so_sha.startswith(cfg['mac']['so_sha256']), 'Mac site .so %s, config says %s' % (x.so_sha, cfg['mac']['so_sha256']))
    if cfg['mac'].get('wheel'):
        need(Path(cfg['mac']['wheel']).exists(), 'no Mac wheel at %s' % cfg['mac']['wheel'])
        if cfg['mac'].get('wheel_sha256'):
            need(sha(cfg['mac']['wheel']).startswith(cfg['mac']['wheel_sha256']), 'Mac wheel sha256 differs from config')
    need((x.policy / 'policy_model.pkl').exists(), 'no policy_model.pkl in %s' % x.policy)
    for rel in ('dataset/code.bin', 'dataset/dataset-metadata.json', 'kernel/kernel-metadata.json', 'kernel/notebook.ipynb', 'run-config-without-seconds.json', 'manifest.json', 'scratch/common.sh'):
        need((x.base / rel).exists(), 'base bundle has no %s' % rel)
    for rel in ('soak-read.json', 'rss-peak.out', 'manifest.json', 'run.sh', 'dag-read.json', 'peak-read.out', 'cpu.txt'):
        need((x.prev_soak / rel).exists(), 'previous soak %s has no %s' % (x.prev_soak.name, rel))
    need(not run(['git', '-C', x.wt, 'rev-parse', '-q', '--verify', 'MERGE_HEAD'], check=False).stdout.strip(), 'a merge is in progress in %s: resolve it and commit, or run git merge --abort, then run again' % x.wt)
    status = x.git('status', '--porcelain').stdout.strip()
    need(not status, 'the worktree %s is not clean:\n%s' % (x.wt, status))
    head = x.head
    allowed = [v for v in (cfg.get('head_before'), cfg.get('expected_head')) if v]
    need(allowed, 'config has neither head_before nor expected_head')
    after_before = cfg.get('head_before') and run(['git', '-C', x.wt, 'merge-base', '--is-ancestor', cfg['head_before'], 'HEAD'], check=False).returncode == 0
    need(any(head.startswith(a) for a in allowed) or after_before, 'HEAD of %s is %s, config allows %s, or a commit after head_before' % (x.wt, head[:9], allowed))
    state = 'before the merge' if cfg.get('head_before') and head.startswith(cfg['head_before']) else 'after the merge'
    if state == 'after the merge':
        finished(x)
    say(1, 'inputs', 'ok: %d model hashes, wheel %s, Mac .so %s, worktree clean, HEAD %s (%s)' % (len(cfg['models']['files']), got[:16], x.so_sha[:16], head[:9], state))


# ---- step 2
def blob_at(x, rev, path):
    r = run(['git', '-C', x.wt, 'rev-parse', '%s:%s' % (rev, path)], check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def step2(x):
    cfg = x.cfg
    mg = cfg.get('merge') or {'mode': 'none'}
    mode = mg.get('mode', 'none')
    if mode == 'merge':
        rev = x.git('rev-parse', mg['ref'] + '^{commit}').stdout.strip()
        if run(['git', '-C', x.wt, 'merge-base', '--is-ancestor', rev, 'HEAD'], check=False).returncode == 0:
            say(2, 'merge', '%s is already in HEAD' % rev[:9])
        else:
            r = x.git('merge', '--no-ff', '--no-edit', rev, check=False)
            if r.returncode != 0:
                conflicts = sorted(x.git('diff', '--name-only', '--diff-filter=U').stdout.split())
                need(conflicts, 'git merge failed with no conflict list:\n' + (r.stdout + r.stderr)[-1500:])
                res = mg.get('resolutions') or {}
                if set(conflicts) != set(res):
                    raise Stop('merge of %s conflicts in %d file(s): %s\nThe merge is left in progress in %s. Resolve it and commit, or run git -C %s merge --abort. Then run this again. '
                               'A conflict file can go in config merge.resolutions as {path: {file, blob}} once its resolved text is known.' % (rev[:9], len(conflicts), ', '.join(conflicts), x.wt, x.wt))
                for path in conflicts:
                    src = Path(res[path]['file'])
                    blob = run(['git', '-C', x.wt, 'hash-object', src]).stdout.strip()
                    need(blob == res[path]['blob'], 'resolution file %s has git blob %s, config says %s. The merge is left in progress in %s.' % (src, blob, res[path]['blob'], x.wt))
                for path in conflicts:
                    shutil.copyfile(res[path]['file'], Path(x.wt) / path)
                    x.git('add', path)
                x.git('commit', '--no-edit')
            say(2, 'merge', 'merged %s, HEAD %s' % (rev[:9], x.head[:9]))
        tree = x.git('rev-parse', 'HEAD^{tree}').stdout.strip()
        parents = x.git('rev-list', '--parents', '-n', '1', 'HEAD').stdout.split()[1:]
        if mg.get('expected_tree') and rev in parents:
            need(tree.startswith(mg['expected_tree']), 'tree after the merge is %s, config says %s. HEAD is %s; nothing is undone.' % (tree, mg['expected_tree'], x.head[:9]))
        elif mg.get('expected_tree'):
            say(2, 'merge', 'HEAD is not the merge commit, so merge.expected_tree is not checked; expected_tree is checked below')
    elif mode == 'files':
        frm = x.git('rev-parse', mg['from'] + '^{commit}').stdout.strip()
        paths = mg['paths']
        for p in paths:
            need(blob_at(x, frm, p), '%s has no file %s' % (frm[:9], p))
        if all(blob_at(x, 'HEAD', p) == blob_at(x, frm, p) for p in paths):
            say(2, 'files', 'the %d file(s) of %s are already in HEAD' % (len(paths), frm[:9]))
        else:
            x.git('checkout', frm, '--', *paths)
            x.git('commit', '-m', mg.get('message') or 'Take %d file(s) from %s' % (len(paths), frm[:9]))
            say(2, 'files', 'took %d file(s) from %s, HEAD %s' % (len(paths), frm[:9], x.head[:9]))
        tree = x.git('rev-parse', 'HEAD^{tree}').stdout.strip()
        if mg.get('expected_tree') and not x.cfg.get('worker_settings'):
            need(tree.startswith(mg['expected_tree']), 'tree after the files is %s, config says %s. HEAD is %s; nothing is undone.' % (tree, mg['expected_tree'], x.head[:9]))
    else:
        say(2, 'merge', 'none asked')
    settings_step(x)
    tree = x.git('rev-parse', 'HEAD^{tree}').stdout.strip()
    if cfg.get('expected_head'):
        need(x.head.startswith(cfg['expected_head']), 'HEAD is %s, config expected_head says %s' % (x.head[:9], cfg['expected_head']))
    if cfg.get('expected_tree'):
        need(tree.startswith(cfg['expected_tree']), 'tree is %s, config expected_tree says %s' % (tree, cfg['expected_tree']))
    need(not x.git('status', '--porcelain').stdout.strip(), 'the worktree is not clean after step 2')
    say(2, 'commit', 'ok: C = %s, tree %s' % (x.c, tree[:12]))


def settings_step(x):
    ws = x.cfg.get('worker_settings') or {}
    if not ws:
        return
    rel = 'model/study/sampler/kaggle_worker.py'
    path = Path(x.wt) / rel
    text = path.read_text()
    need('def settings():' in text, 'kaggle_worker.py has no settings(): the code change that adds it is a person\'s')
    done, changed = [], []
    for name, value in ws.items():
        const = SETTING_CONSTANTS.get(name, name + '_SETTING')
        m = list(re.finditer(r"^%s = '([^']*)'" % re.escape(const), text, re.M))
        need(len(m) == 1, 'kaggle_worker.py has %d lines "%s = \'...\'"' % (len(m), const))
        need("('%s', %s)" % (name, const) in text, "settings() of kaggle_worker.py does not set %s from %s" % (name, const))
        if m[0][1] == value:
            done.append(name)
            continue
        text = text[:m[0].start(1)] + value + text[m[0].end(1):]
        changed.append('%s %s -> %s' % (name, m[0][1], value))
    if not changed:
        say(2, 'settings', 'already set: %s' % ', '.join(done))
        return
    path.write_text(text)
    compile(text, str(path), 'exec')
    x.git('add', rel)
    msg = x.cfg.get('worker_settings_message') or 'Kaggle kit: the worker sets ' + ', '.join('%s %s' % (k, v) for k, v in ws.items())
    x.git('commit', '-m', msg)
    stat = x.git('diff', '--name-only', 'HEAD~1', 'HEAD').stdout.split()
    need(stat == [rel], 'the settings commit changes %s, not %s alone' % (stat, rel))
    say(2, 'settings', 'committed %s: %s' % (x.head[:9], '; '.join(changed)))


# ---- step 3
def step3(x):
    cfg, fz = x.cfg, x.cfg['freeze']
    folder = x.freeze_dir()
    models = Path(cfg['models']['dir'])
    files = cfg['models']['files']
    if fz.get('reuse'):
        for name, want in files.items():
            need(sha(folder / name).startswith(want), 'reused freeze %s: %s differs' % (folder, name))
        say(3, 'freeze', 'reuse %s: %d hashes match' % (folder.name, len(files)))
        return
    if folder.exists():
        for name, want in files.items():
            need((folder / name).exists() and sha(folder / name).startswith(want), '%s exists and %s differs: remove it if it is a partial copy' % (folder, name))
    folder.mkdir(parents=True, exist_ok=True)
    for name, want in files.items():
        shutil.copy2(models / name, folder / name)
        need(sha(folder / name).startswith(want), 'copy of %s differs' % name)
    m = {}
    if fz.get('template'):
        t = Path(fz['template'])
        m = json.load(open(t / 'manifest.json' if t.is_dir() else t))
        old_used = m.get('used_by')
        if old_used:
            m = json.loads(json.dumps(m).replace(old_used, 'kernel-bundle-' + x.c))
    m.update(fz.get('manifest') or {})
    m.setdefault('commit', '%s on branch kernel-next. The models come from %s.' % (x.c, models))
    m['files'] = {n: sha(folder / n)[:16] for n in files}
    m['used_by'] = 'kernel-bundle-' + x.c
    with open(folder / 'manifest.json', 'w') as f:
        json.dump(m, f, indent=1)
    say(3, 'freeze', '%s: %d files, hashes match, manifest.json with %d fields' % (folder.name, len(files), len(m)))


# ---- step 4
def tar_diff(a, b):
    """Names of the members that differ in content, mode or presence between two tar files."""
    ta, tb = tarfile.open(a), tarfile.open(b)
    ma, mb = {m.name: m for m in ta.getmembers()}, {m.name: m for m in tb.getmembers()}
    out = []
    for n in sorted(set(ma) | set(mb)):
        if n not in ma or n not in mb:
            out.append(n)
        else:
            x, y = ma[n], mb[n]
            if (x.type, x.size, x.mode) != (y.type, y.size, y.mode) or (x.isfile() and ta.extractfile(x).read() != tb.extractfile(y).read()):
                out.append(n)
    return out


def dir_differ(a, b):
    a, b = Path(a), Path(b)
    names = sorted({p.name for p in a.iterdir()} | {p.name for p in b.iterdir()})
    return [n for n in names if not ((a / n).exists() and (b / n).exists() and sha(a / n) == sha(b / n))]


def step4(x):
    cfg = x.cfg
    finished(x)
    B = x.bundle
    (B / 'kernel').mkdir(parents=True, exist_ok=True)
    wt = Path(x.wt)
    freeze = x.freeze_dir()
    run(['python3', wt / 'engine/kaggle/synth/build_bundle.py', x.wheel, freeze, x.policy, B / 'dataset'])
    run(['python3', wt / 'engine/kaggle/synth/make_notebook.py', B / 'kernel/notebook.ipynb'])
    shutil.copy2(x.base / 'dataset/dataset-metadata.json', B / 'dataset/')
    shutil.copy2(x.base / 'kernel/kernel-metadata.json', B / 'kernel/')
    shutil.copy2(x.base / 'run-config-without-seconds.json', B)
    differ = dir_differ(x.base / 'dataset', B / 'dataset')
    nb_equal = sha(x.base / 'kernel/notebook.ipynb') == sha(B / 'kernel/notebook.ipynb')
    line = 'dataset differs from %s in %s; notebook %s' % (x.base.name, differ, 'equal' if nb_equal else 'DIFFERS')
    if 'code.bin' in differ:
        members = tar_diff(x.base / 'dataset/code.bin', B / 'dataset/code.bin')
        line += '; code.bin members that differ: %d%s' % (len(members), (' (' + ', '.join(members[:8]) + (', ...' if len(members) > 8 else '') + ')') if members else '')
    if 'expect_dataset_differ' in cfg:
        need(differ == sorted(cfg['expect_dataset_differ']), line + '\nconfig expect_dataset_differ says %s' % sorted(cfg['expect_dataset_differ']))
    if cfg.get('expect_notebook_equal', True):
        need(nb_equal, line + '\nthe notebook should equal the base notebook (config expect_notebook_equal)')
    ref = cfg.get('reference_bundle')
    if ref:
        ref = Path(ref)
        bad = []
        for n in sorted(p.name for p in (ref / 'dataset').iterdir()):
            if n == 'code.bin':
                d = tar_diff(ref / 'dataset/code.bin', B / 'dataset/code.bin')
                if d:
                    bad.append('code.bin members ' + ', '.join(d[:5]))
            elif not (B / 'dataset' / n).exists() or sha(ref / 'dataset' / n) != sha(B / 'dataset' / n):
                bad.append(n)
        extra = sorted(p.name for p in (B / 'dataset').iterdir() if not (ref / 'dataset' / p.name).exists())
        bad += ['extra ' + n for n in extra]
        for rel in ('kernel/notebook.ipynb', 'kernel/kernel-metadata.json', 'run-config-without-seconds.json'):
            if sha(ref / rel) != sha(B / rel):
                bad.append(rel)
        need(not bad, line + '\nreference bundle %s differs in: %s' % (ref.name, bad))
        same = sha(ref / 'dataset/code.bin') == sha(B / 'dataset/code.bin')
        line += '; equals reference %s (code.bin by members; byte-equal: %s)' % (ref.name, same)
    say(4, 'bundle', line)


# ---- step 5
def kaggle_worker_constants(text):
    return dict(re.findall(r"^(\w+_SETTING|ONE_REPAIR_SECONDS) = '([^']*)'", text, re.M))


def source_segments(text, names):
    tree = ast.parse(text)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            out[node.targets[0].id] = node
    return out


def adapt_code_vs_kit(x, path):
    cv = x.cfg.get('code_vs_kit') or {}
    text = path.read_text()
    nodes = source_segments(text, {'B', 'KIT', 'DIFFER', 'NO_KIT_FILE'})
    need({'B', 'DIFFER', 'NO_KIT_FILE'} <= set(nodes), 'code-vs-kit.py of the base has not the assignments B, DIFFER, NO_KIT_FILE')
    need('KIT' in nodes or not cv.get('kit'), 'code-vs-kit.py of the base has no assignment KIT, and config code_vs_kit.kit is set')

    def lst(name):
        return sorted(eval(compile(ast.Expression(nodes[name].value), 'x', 'eval'), {'__builtins__': {}, 'sorted': sorted}))
    differ = lst('DIFFER')
    no_file = lst('NO_KIT_FILE')
    cut = lambda ps: [p[len('model/study/'):] for p in ps]  # noqa: E731
    differ = cut(differ) if cv.get('differ') is None else cv['differ']
    differ = sorted((set(differ) | set(cv.get('differ_add', []))) - set(cv.get('differ_remove', [])))
    no_file = cut(no_file) if cv.get('no_kit_file') is None else cv['no_kit_file']
    no_file = sorted((set(no_file) | set(cv.get('no_kit_file_add', []))) - set(cv.get('no_kit_file_remove', [])))
    new = {
        'B': "B = '%s/'" % (x.bundle / 'dataset'),
        'KIT': "KIT = '%s/'" % cv['kit'].rstrip('/') if cv.get('kit') else None,
        'DIFFER': 'DIFFER = sorted(\'model/study/\' + n for n in [\n    %s])' % ', '.join(repr(n) for n in differ),
        'NO_KIT_FILE': 'NO_KIT_FILE = sorted(\'model/study/\' + n for n in [%s])' % ', '.join(repr(n) for n in no_file)}
    lines = text.split('\n')
    for name in sorted(nodes, key=lambda n: -nodes[n].lineno):
        if new.get(name) is None:
            continue
        lines[nodes[name].lineno - 1:nodes[name].end_lineno] = new[name].split('\n')
    text = '\n'.join(lines)
    if cv.get('kit'):
        text = text.replace('tested kit sampler-pool-dag-both-final-8be414670', 'tested kit ' + Path(cv['kit'].rstrip('/')).name)
    if cv.get('models_subdir'):
        text = re.sub(r"'models-[\w-]+/'", "'%s/'" % cv['models_subdir'].strip('/'), text)
        text = text.replace('equals models-final', 'equals ' + cv['models_subdir'].strip('/'))
    if cv.get('wheel_equals_kit'):
        extra = ("import glob\nwhl = [os.path.basename(p) for p in glob.glob(B + 'arclog-*.whl')]\nassert len(whl) == 1, whl\n"
                 "a, b = sha(open(B + whl[0], 'rb').read()), sha(open(KIT + whl[0], 'rb').read())\nassert a == b, 'wheel'\nprint('wheel', a[:16], 'equals the kit')\n")
        text = text.replace("print('code-vs-kit passed')", extra + "print('code-vs-kit passed')")
    path.write_text(text)
    return differ, no_file


def step5(x):
    cfg = x.cfg
    src, dst = x.base / 'scratch', x.scratch
    need(x.bundle.exists() and (x.bundle / 'dataset').exists(), 'run step 4 first: %s has no dataset' % x.bundle)
    finished(x)
    need(not (dst / 'times.txt').exists(), '%s holds check results (times.txt): move that folder aside first, since step 5 would replace it' % dst)
    if dst.exists():
        shutil.rmtree(dst)
    n = 0
    for p in sorted(src.rglob('*')):
        rel = p.relative_to(src)
        if rel.as_posix() in SCRATCH_SKIP_PATHS or any(fnmatch.fnmatch(part, pat) for part in rel.parts for pat in SCRATCH_SKIP):
            continue
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel)
            n += 1
    for g in GENERIC_SCRIPTS:
        shutil.copy2(HERE / g, dst / g)
    # derived substitutions
    subs = [(x.basec, x.c)]
    texts = {p: p.read_text() for p in dst.rglob('*') if p.is_file() and p.suffix in TEXT_SUFFIXES and p.name not in GENERIC_SCRIPTS}
    blob = '\n'.join(texts.values())
    site_new = x.site.name
    for old in sorted(set(re.findall(r'\bmacsite\d+\b', blob))):
        subs.append((old, site_new))
    wheel_linux, wheel_mac = x.wheel.parent.name, Path(x.mac['wheel']).parent.name if x.mac.get('wheel') else None
    for old in sorted(set(re.findall(r'\bwheel\d+(?:-mac)?\b', blob))):
        new = wheel_mac if old.endswith('-mac') else wheel_linux
        if new:
            subs.append((old, new))
    old_sos = sorted(set(re.findall(r'\b[0-9a-f]{64}\b', (dst / 'common.sh').read_text())))
    for old in old_sos:
        if old != x.so_sha:
            subs.append((old, x.so_sha))
    old_wheel = sha(next((x.base / 'dataset').glob('arclog-*.whl')))
    new_wheel = sha(x.wheel)
    if old_wheel != new_wheel:
        subs += [(old_wheel, new_wheel), (old_wheel[:16], new_wheel[:16])]
    for name in cfg['models']['files']:
        if (x.base / 'dataset' / name).exists() and sha(x.base / 'dataset' / name) != sha(x.bundle / 'dataset' / name):
            subs.append((sha(x.base / 'dataset' / name)[:16], sha(x.bundle / 'dataset' / name)[:16]))
    # worker settings that differ between the base code.bin and the worktree
    base_kw = tarfile.open(x.base / 'dataset/code.bin').extractfile('model/study/sampler/kaggle_worker.py').read().decode()
    new_kw = (Path(x.wt) / 'model/study/sampler/kaggle_worker.py').read_text()
    old_c, new_c = kaggle_worker_constants(base_kw), kaggle_worker_constants(new_kw)
    set_changes = {k: (old_c.get(k), v) for k, v in new_c.items() if old_c.get(k) != v}
    for k, (o, v) in set_changes.items():
        if o is not None:
            subs.append(("%s = '%s'" % (k, o), "%s = '%s'" % (k, v)))
    # out_root and check_root, where they differ from the repository's
    default_out = x.repo + '/work/synth-kaggle'
    path_subs = []
    if str(x.out) != default_out:
        path_subs += [('$R/work/synth-kaggle/kernel-bundle-', str(x.out) + '/kernel-bundle-'), ('$R/work/synth-kaggle/kernel-soak-', str(x.out) + '/kernel-soak-')]
    path_subs.append(('$R/work/synth-kaggle/' + site_new, str(x.site)))
    subs = [subs[0]] + sorted(subs[1:], key=lambda s: -len(s[0]))
    hits = {}
    for p, t in texts.items():
        t2 = t
        for old, new in subs + path_subs:
            if old != new and old in t2:
                hits[old] = hits.get(old, 0) + t2.count(old)
                t2 = t2.replace(old, new)
        if x.check_root:
            t2 = re.sub(r'^X=\$SP/check-\$C', 'X=%s/check-$C' % x.check_root, t2, flags=re.M)
            t2 = re.sub(r'^SP=.*/ramp59-%s$' % re.escape(x.c), 'SP=%s/ramp59-%s' % (x.check_root, x.c), t2, flags=re.M)
        if cfg.get('sp'):
            t2 = re.sub(r'^SP=/private/tmp\S*scratchpad$', 'SP=' + cfg['sp'], t2, flags=re.M)
        if t2 != t:
            p.write_text(t2)
    # sampler line and the expected line of the dag read
    expect_path = dst / 'kit-files/kernel-soak-dag-read.py'
    expect_note = ''
    if expect_path.exists():
        t = expect_path.read_text()
        t0 = t
        for name, (o, v) in ((k, v) for k, v in set_changes.items() if v[0] is not None):
            if name == 'ORDER_FREE_SETTING':
                t = re.sub(r'(order_free )(\S+?)(, ident)', lambda m: m[1] + (','.join(sorted(set(v.split(',')) - {''})) or '-') + m[3], t)
            elif name == 'IDENT_SOURCE_SETTING':
                t = re.sub(r'(ident )(\S+)( True| False)', lambda m: m[1] + (v or '-') + (' True' if v not in ('', '0') else ' False'), t)
            elif name == 'P_DAG_SETTING':
                t = re.sub(r'P_DAG (True|False)', 'P_DAG ' + str(v == '1'), t)
        if t != t0:
            expect_path.write_text(t)
            expect_note = '; EXPECT line of kernel-soak-dag-read.py changed'
    # code-vs-kit.py
    differ, no_file = adapt_code_vs_kit(x, dst / 'code-vs-kit.py')
    # config: add files, remove files, edits
    sc = cfg.get('scratch') or {}
    for rel in sc.get('remove', []):
        target = dst / rel
        need(target.exists(), 'scratch.remove: no %s' % rel)
        shutil.rmtree(target) if target.is_dir() else target.unlink()
    for rel, srcp in (sc.get('add_files') or {}).items():
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(srcp, dst / rel)
    for e in sc.get('edits', []):
        p = dst / e['file']
        t = p.read_text()
        want = e.get('count', 1)
        need(t.count(e['old']) == want, 'scratch.edits: %s has %d of the text %r, config says %d' % (e['file'], t.count(e['old']), e['old'][:60], want))
        p.write_text(t.replace(e['old'], e['new']))
    # no old name left
    left = []
    olds = [o for o, n2 in subs if o != n2 and (o == x.basec or o.startswith('macsite') or re.fullmatch(r'wheel\d+(-mac)?', o) or re.fullmatch(r'[0-9a-f]{64}', o))]
    for p in sorted(dst.rglob('*')):
        if p.is_file() and p.suffix in TEXT_SUFFIXES and p.name not in GENERIC_SCRIPTS:
            t = p.read_text()
            left += ['%s in %s' % (o, p.relative_to(dst)) for o in olds if o in t]
    need(not left, 'old names remain in the copied scratch: %s' % left)
    stale = []
    for k, (o, v) in set_changes.items():
        if o:
            for p in sorted(dst.rglob('*')):
                if p.is_file() and p.suffix in TEXT_SUFFIXES and p.name not in GENERIC_SCRIPTS and ("'%s'" % o) in p.read_text() and o != v:
                    stale.append('%s: old value %r in %s' % (k, o, p.relative_to(dst)))
    params = dict(config=cfg, config_path=x.config_path, repo=x.repo, out=str(x.out), c=x.c, basec=x.basec, base=str(x.base), prev_soak=str(x.prev_soak), bundle=str(x.bundle), freeze=str(x.freeze_dir()),
                  wheel=str(x.wheel), wheel_name=x.wheel.name, mac_site=str(x.site), mac_wheel=x.mac.get('wheel'), so_sha=x.so_sha, check_root=x.check_root, python=x.py, worktree=x.wt,
                  set_changes={k: list(v) for k, v in set_changes.items()}, code_vs_kit_differ=differ, code_vs_kit_no_file=no_file)
    (dst / 'build-params.json').write_text(json.dumps(params, indent=1))
    msg = 'copied %d files from %s; %d substitution pairs hit %d times; code-vs-kit lists %d differ, %d no kit file%s' % (n, x.base.name, len([1 for o, n2 in subs if o != n2]), sum(hits.values()), len(differ), len(no_file), expect_note)
    say(5, 'scratch', msg)
    if stale:
        say(5, 'scratch', 'WARN a changed setting value still appears in a copied file; the checks decide if it matters: ' + '; '.join(stale))


# ---- step 6
def quick_checks(x):
    h = '$H'
    names = list(pass_conditions.QUICK)
    cmds = {'code-read': ['python3', '$H/code-read.py', '%s/dataset/code.bin' % x.bundle, x.wt, '%s/dataset/supervisor.py' % x.bundle, '%s/kernel/notebook.ipynb' % x.bundle],
            'code-vs-kit': ['python3', '$H/code-vs-kit.py'], 'kinds': ['$H/kinds-check.sh'], 'stack-kill': ['$H/stack-kill.sh']}
    for name, cmd in (x.cfg.get('extra_quick_checks') or {}).items():
        names.append(name)
        cmds[name] = cmd
    return names, cmds


def expect_line(x):
    p = x.scratch / 'kit-files/kernel-soak-dag-read.py'
    m = re.search(r"^EXPECT = '([^']*)'", p.read_text(), re.M) if p.exists() else None
    return m[1] if m else None


def step6(x, only=None):
    H = x.scratch
    need(H.exists(), 'run step 5 first')
    names, cmds = quick_checks(x)
    extra = x.cfg.get('pass_extra')
    for name in names:
        if only and name != only:
            continue
        cmd = [c.replace('$H', str(H)) for c in cmds[name]]
        t0 = time.time()
        try:
            r = run([H / 'run-check.sh', name, *cmd], timeout=x.quick_timeout, check=False)
        except subprocess.TimeoutExpired:
            raise Stop('check %s took over %d s: run %s/run-check.sh %s %s yourself' % (name, x.quick_timeout, H, name, ' '.join(cmd)))
        text = (H / ('check-%s.txt' % name)).read_text(errors='replace')
        bad = pass_conditions.failures(name, text, x.c, extra, expect_line(x), x.cfg.get('session_mib'))
        if r.returncode != 0 or bad:
            hint = ''
            if name == 'code-vs-kit':
                hint = '\nIf the difference is expected, add it to code_vs_kit.differ_add, differ_remove, no_kit_file_add or no_kit_file_remove in the config.'
            raise Stop('check %s failed (exit %d, conditions not met: %s). Output:\n%s%s' % (name, r.returncode, bad, text[-1800:], hint))
        say(6, name, 'ok in %d s' % round(time.time() - t0))


# ---- step 7
def step7(x):
    H = x.scratch
    need((H / 'build-params.json').exists(), 'run step 5 first')
    params = json.loads((H / 'build-params.json').read_text())
    params['config'], params['config_path'] = x.cfg, x.config_path
    (H / 'build-params.json').write_text(json.dumps(params, indent=1))
    stamp = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    (H / 'pass-bar-time.txt').write_text(stamp + '\n')
    r = run(['python3', H / 'make-kit.py', stamp], timeout=120)
    say(7, 'kit', r.stdout.strip().splitlines()[-1])


# ---- step 8
def parse_etas(x):
    times = {}
    t = x.base / 'scratch/times.txt'
    if t.exists():
        for line in t.read_text().splitlines():
            m = re.match(r'(\S+) (\d+) s, exit (\d+)', line)
            if m:
                times[m[1]] = int(m[2])
    names = re.findall(r'run-check\.sh (\S+)', (x.scratch / 'run-rest.sh').read_text())
    return names, [times.get(n) for n in names]


def step8(x):
    H = x.scratch
    names, secs = parse_etas(x)
    known = [s for s in secs if s]
    eta = 'about %.1f min on the base run (%d checks, %d with a time)' % (sum(known) / 60, len(names), len(known))
    say(8, 'next', 'run nothing in parallel with run-rest.sh. Commands to run next, each over 20 s:')
    print('  1. %s/run-rest.sh        ETA %s' % (H, eta), flush=True)
    print('     if gate-80a900e0 shows no fill line at 55 s, run it again at 110 s: %s/run-check.sh gate-80a900e0 %s/gate-check.sh 80a900e0 110   ETA 2 min' % (H, H), flush=True)
    print('  2. python3 %s/write-records.py        ETA under 30 s (checks.json, make-kit.py repack, make-manifest.py)' % H, flush=True)
    print('  then report the kit .tar.gz path and sha256 that write-records.py prints, and stop.', flush=True)


STEPS = [(1, step1), (2, step2), (3, step3), (4, step4), (5, step5), (6, step6), (7, step7), (8, step8)]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    try:
        x = Ctx(sys.argv[1])
    except (KeyError, OSError, ValueError) as e:
        print('STOP config: %s %s' % (type(e).__name__, e), flush=True)
        return 1
    n = 0
    spec = sys.argv[2] if len(sys.argv) > 2 else ''
    wanted = {}
    for part in filter(None, spec.split(',')):
        n, _, only = part.partition(':')
        wanted[int(n)] = only or None
    try:
        for n, fn in STEPS:
            if wanted and n not in wanted:
                continue
            if n == 6:
                fn(x, wanted.get(6))
            else:
                fn(x)
    except Stop as e:
        print('STOP step %s: %s' % (n, e), flush=True)
        return 1
    except subprocess.TimeoutExpired as e:
        print('STOP step %s: command over its time limit: %s' % (n, e), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
