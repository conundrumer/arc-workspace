"""Immutable Git checkouts and the data root shared by judge workers."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import fcntl
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types

HERE=Path(__file__).resolve().parent

def git(*args,cwd=None):
    return subprocess.check_output(['git','-C',str(cwd or HERE),*args],text=True).strip()

def repository():
    if os.environ.get('JUDGE_CODE_REPOSITORY'):return Path(os.environ['JUDGE_CODE_REPOSITORY']).resolve()
    common=Path(git('rev-parse','--git-common-dir'))
    if not common.is_absolute():common=HERE/common
    return common.resolve().parent

def data_root():return Path(os.environ.get('JUDGE_DATA_ROOT', DATA_ROOT / 'judge2')).resolve()

def published_head():return git('rev-parse','--verify','refs/heads/published^{commit}',cwd=repository())

def code_commit():
    value=os.environ.get('JUDGE_PUBLISHED_COMMIT')
    if not value or not re.fullmatch(r'[0-9a-f]{40}',value):raise RuntimeError('run through run_published.py; missing published commit')
    return value

def write_version(directory,commit):
    """One atomic pool/source pointer; readers never see a missing or partial ID."""
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})',commit):raise ValueError('render version must be a full content digest or historical commit')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    try:
        if (directory/'RENDER_VERSION').read_text()==commit+'\n':return
    except FileNotFoundError:pass
    fd,name=tempfile.mkstemp(prefix='.RENDER_VERSION-',dir=directory)
    try:
        with os.fdopen(fd,'w') as out:
            out.write(commit+'\n');out.flush();os.fsync(out.fileno())
        os.replace(name,directory/'RENDER_VERSION')
    finally:
        if os.path.exists(name):os.unlink(name)

def checkout(commit):
    repo=repository();base=repo/'.worktrees';base.mkdir(exist_ok=True)
    with (base/'CHECKOUT.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        target=base/'published'/commit
        if not target.exists():
            target.parent.mkdir(exist_ok=True)
            subprocess.run(['git','-C',str(repo),'worktree','add','--detach',str(target),commit],check=True,stdout=sys.stderr)
        if git('rev-parse','HEAD',cwd=target)!=commit:raise RuntimeError('published worktree has the wrong commit')
        if git('status','--porcelain','--untracked-files=no',cwd=target):raise RuntimeError('published worktree has tracked edits: '+str(target))
    return target

def execute(script,args,commit=None):
    repo=repository();commit=commit or published_head();target=checkout(commit)
    os.environ.update(JUDGE_CODE_REPOSITORY=str(repo),JUDGE_DATA_ROOT=str(data_root()),JUDGE_PUBLISHED_COMMIT=commit)
    os.execv(sys.executable,[sys.executable,'-B',str(target/script),*args])

def activate(script):
    """Direct CLI calls also dispatch to published, never a working copy."""
    if not os.environ.get('JUDGE_PUBLISHED_COMMIT'):execute(script,sys.argv[1:])
    if git('rev-parse','HEAD')!=code_commit():raise RuntimeError('process code does not match its published commit')

@lru_cache(maxsize=1)
def _runtime_selector():
    """Load the coordinated canonical selector, never an unpinned replacement."""
    source=CODE_ROOT/'ast/run/provenance.py'
    content=source.read_bytes()
    expected='0299b982fc59f4de5416d25c95febf4f443fa20dd6ced1aeee060068bc09d763'
    if hashlib.sha256(content).hexdigest()!=expected:
        raise RuntimeError('canonical runtime selector source SHA differs: '+str(source))
    module=types.ModuleType('_pinned_study_runtime_provenance')
    module.__file__=str(source)
    exec(compile(content,str(source),'exec'),module.__dict__)
    return module.resolve_runtime

def runtime_receipt(argument,*,waiting=True):
    """Expose the captured canonical metadata receipt without native authentication."""
    return _runtime_selector()(Path(argument).resolve(),waiting=waiting)

def resolve_runtime(argument):
    """Translate canonical metadata selection; this does not authenticate native code."""
    path=Path(argument).resolve()
    if path.suffix!='.json':return path,None  # explicit legacy sources only
    selected=runtime_receipt(path)
    if selected['waiting_reason'] is not None:return None,selected['waiting_reason']
    # The canonical selector preserves and checks the exact venv entry path.
    return selected['python'].parent.parent,None
