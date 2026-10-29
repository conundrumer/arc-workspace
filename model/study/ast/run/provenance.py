"""Validate a supplied build receipt against the wheel and installed extension."""
import hashlib
import json
from pathlib import Path
import re
import sys
import threading
import zipfile


def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as src:
        for block in iter(lambda:src.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def load_build(arclog,args):
    receipt={};base=Path.cwd()
    if args.build_receipt:
        base=args.build_receipt.resolve().parent;receipt=json.loads(args.build_receipt.read_text())
    commit=args.engine_commit or receipt.get('engine_commit')
    wheel=args.wheel or receipt.get('wheel_path') or receipt.get('wheel')
    if not commit or not re.fullmatch('[0-9a-fA-F]{40}',commit):
        raise ValueError('provide the built engine full commit via --engine-commit or --build-receipt')
    if not wheel:raise ValueError('provide the exact built wheel via --wheel or --build-receipt')
    wheel=Path(wheel);wheel=wheel if wheel.is_absolute() else base/wheel
    digest=sha256_file(wheel)
    if receipt.get('wheel_sha256') and receipt['wheel_sha256']!=digest:raise ValueError('wheel digest differs from build receipt')
    package=Path(arclog.__file__).resolve().parent
    binaries={}
    with zipfile.ZipFile(wheel) as archive:
        members=[name for name in archive.namelist() if name.endswith(('.so','.pyd'))]
        if not members:raise ValueError('wheel has no native extension')
        for name in members:
            installed=package/Path(name).name
            binary_digest=hashlib.sha256(archive.read(name)).hexdigest()
            if not installed.exists() or sha256_file(installed)!=binary_digest:
                raise ValueError('installed extension does not match supplied wheel: '+str(installed))
            binaries[installed.name]=binary_digest
    if receipt.get('native_binary_sha256') and receipt['native_binary_sha256']!=binaries:
        raise ValueError('native binary digest differs from receipt')
    return dict(engine_commit=commit.lower(),wheel_sha256=digest,native_binary_sha256=binaries,
                wheel_path=str(wheel.resolve()),python=str(Path(sys.executable).absolute()),
                build_receipt=str(args.build_receipt.resolve()) if args.build_receipt else None)


# Successful authentication is local to this process. Inherited receipts select
# a build but never populate this cache or replace load_build verification.
_AUTHENTICATED = {}
_AUTH_LOCK = threading.RLock()
_SELECTION_ENV = 'ARC_STUDY_RUNTIME_SELECTION'


def _selector(current, runtime_manifest):
    return dict(path=str(Path(runtime_manifest if runtime_manifest is not None else current).resolve()),
                candidate=runtime_manifest is not None)


def _frozen_selection(selector):
    import os
    frozen = json.loads(os.environ[_SELECTION_ENV]) if _SELECTION_ENV in os.environ else None
    if frozen is not None:
        if frozen.get('schema') != 'arclog-runtime-selection-v1' or frozen.get('selector') != selector:
            raise ValueError('inherited runtime selection differs from requested selector')
    return frozen


def _copy_json(value):
    return json.loads(json.dumps(value))


def resolve_runtime(current, runtime_manifest=None, *, waiting=False):
    """Resolve immutable runtime metadata without exec, imports or authentication.

    CURRENT-shaped selections and explicit ready.json receipts are supported.
    Returns manifest, ready, build=None, runtime/python Paths,
    authenticated=False, waiting_reason and selector. Whole ready metadata,
    including execution_evidence, is retained. The Python entry path is never
    dereferenced to its system symlink target.

    waiting=True permits only an absent selection, explicit pending selection,
    or missing ready.json. Invalid/conflicting receipts always raise. A waiting
    result has a reason and ready=None. Frozen worker selection ignores a moved
    CURRENT, but still compares the complete immutable ready receipt.
    """
    selector = _selector(current, runtime_manifest)
    selected = Path(selector['path'])
    frozen = _frozen_selection(selector)
    result = dict(manifest=None, ready=None, build=None, runtime=None, python=None,
                  authenticated=False, waiting_reason=None, selector=selector)

    def unavailable(reason):
        if not waiting:
            raise FileNotFoundError(reason)
        result['waiting_reason'] = reason
        return result

    if frozen is not None:
        manifest = _copy_json(frozen['manifest'])
    else:
        try:
            source = json.loads(selected.read_text())
        except FileNotFoundError:
            return unavailable('waiting for ' + str(selected))
        if not isinstance(source, dict):
            raise ValueError('runtime selection must be a JSON object')
        # An explicit pending marker is not a malformed or shortened revision.
        # If a pending receipt also has a revision, validate all its metadata
        # before returning waiting, so pending cannot hide a conflict.
        pending = source.get('pending') is True or source.get('status') == 'pending' or source.get('commit') == 'pending'
        if pending and source.get('commit') in (None, 'pending') and 'revision' not in source:
            result['manifest'] = source
            return unavailable('waiting for committed runtime in ' + str(selected))
        if 'commit' in source and 'runtime' in source and 'python' in source:
            manifest = dict(source)
        elif 'revision' in source and 'wheel' in source and 'python' in source and selected.name == 'ready.json':
            manifest = dict(commit=source['revision'], runtime=str(selected.parent),
                            python=source['python'], wheel=source['wheel'])
        else:
            raise ValueError('runtime manifest must be a full selection manifest or an immutable ready.json')
    commit = manifest.get('commit')
    if not isinstance(commit, str) or re.fullmatch('[0-9a-f]{40}', commit) is None:
        raise ValueError('runtime selection requires an exact full revision, not pending or a prefix')
    runtime = Path(manifest['runtime'])
    python = Path(manifest['python'])
    if not runtime.is_absolute() or not python.is_absolute():
        raise ValueError('runtime and python selection paths must be absolute')
    runtime = runtime.resolve()
    result.update(manifest=manifest, runtime=runtime, python=python)
    if python != runtime / 'venv/bin/python':
        raise ValueError('selected python differs from exact runtime/venv interpreter')
    ready_path = runtime / 'ready.json'
    try:
        ready = json.loads(ready_path.read_text())
    except FileNotFoundError:
        # A vanished previously frozen receipt is a broken immutable selection.
        if frozen is not None:
            raise ValueError('immutable ready receipt disappeared after selection')
        return unavailable('waiting for ' + str(ready_path))
    if not isinstance(ready, dict):
        raise ValueError('runtime ready receipt must be a JSON object')
    if ready.get('revision') != commit:
        raise ValueError('selected full revision differs from ready revision')
    if str(python) != ready.get('python'):
        raise ValueError('selected python differs from exact ready runtime/venv interpreter')
    if not python.is_file():
        raise ValueError('selected ready interpreter does not exist')
    wheel = Path(ready['wheel'])
    if not wheel.is_absolute() or not wheel.resolve().is_relative_to(runtime):
        raise ValueError('ready wheel is not inside the selected immutable runtime')
    if not wheel.is_file():
        raise ValueError('selected ready wheel does not exist')
    if manifest.get('wheel') and Path(manifest['wheel']) != wheel:
        raise ValueError('selected wheel differs from ready wheel')
    for key in ('wheel_sha256', 'native_binary_sha256'):
        if manifest.get(key) is not None and ready.get(key) is not None and manifest[key] != ready[key]:
            raise ValueError('selected manifest differs from ready receipt: ' + key)
    if frozen is not None and frozen['ready'] != ready:
        raise ValueError('immutable ready receipt changed after selection')
    if frozen is None and (manifest.get('pending') is True or manifest.get('status') == 'pending'
                           or ready.get('pending') is True or ready.get('status') == 'pending'):
        return unavailable('waiting for completed runtime in ' + str(selected))
    result['ready'] = ready
    return result


def _artifact_state(paths):
    # Invalidation only: changed files must pass load_build again. These stamps
    # are not used as an alternative proof of wheel/extension authenticity.
    return tuple((str(path), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
                 for path in paths for st in (path.stat(),))


def select_runtime(current, runtime_manifest=None):
    """Resolve, bootstrap and authenticate a strict checker runtime.

    Call before native work, after setting thread limits. Metadata resolution
    delegates to resolve_runtime. This function alone re-execs/imports arclog
    and verifies the installed extension using load_build. Returns the metadata
    receipt with authenticated=True and build set. Authentication is cached only
    per process/exact immutable receipt; each spawned child authenticates itself.
    ARC_STUDY_RUNTIME_SELECTION freezes selection through exec and worker spawn.
    """
    import os
    from types import SimpleNamespace
    selection = resolve_runtime(current, runtime_manifest)
    manifest, ready = selection['manifest'], selection['ready']
    runtime, python = selection['runtime'], selection['python']
    frozen = _frozen_selection(selection['selector'])
    if frozen is None:
        frozen = dict(schema='arclog-runtime-selection-v1', selector=selection['selector'],
                      manifest=manifest, ready=ready)
    os.environ[_SELECTION_ENV] = json.dumps(frozen, separators=(',', ':'))
    if Path(sys.executable).absolute() != python or Path(sys.prefix).resolve() != runtime / 'venv':
        argv = list(getattr(sys, 'orig_argv', []))
        if not argv and sys.argv and Path(sys.argv[0]).is_file():
            argv = [sys.executable, '-B', '-u', *sys.argv]
        if not argv or argv[1:] == ['-']:
            raise ValueError('stdin/embedded callers must launch the selected runtime python directly')
        os.execv(str(python), [str(python), *argv[1:]])
    import arclog
    package = Path(arclog.__file__).resolve().parent
    if not package.is_relative_to(runtime / 'venv'):
        raise ValueError('imported arclog is outside selected runtime venv')
    cache_key = (os.getpid(), str(Path(sys.executable).absolute()), str(package),
                 json.dumps(dict(manifest=manifest, ready=ready), sort_keys=True, separators=(',', ':')))
    with _AUTH_LOCK:
        cached = _AUTHENTICATED.get(cache_key)
        if cached is not None:
            build, paths, state = cached
            if _artifact_state(paths) != state:
                cached = None
        if cached is None:
            build = load_build(arclog, SimpleNamespace(build_receipt=None,
                               engine_commit=manifest['commit'], wheel=Path(ready['wheel'])))
        for receipt, description in ((manifest, 'selected manifest'), (ready, 'ready receipt'),
                                      (frozen.get('build', {}), 'inherited build')):
            for key in ('wheel_sha256', 'native_binary_sha256'):
                if receipt.get(key) is not None and receipt[key] != build[key]:
                    raise ValueError(description + ' differs from installed build: ' + key)
        if cached is None:
            paths = (Path(ready['wheel']), *(package / name for name in sorted(build['native_binary_sha256'])))
            _AUTHENTICATED[cache_key] = (_copy_json(build), paths, _artifact_state(paths))
        frozen['build'] = build
        os.environ[_SELECTION_ENV] = json.dumps(frozen, separators=(',', ':'))
        selection.update(build=_copy_json(build), authenticated=True)
        return selection
