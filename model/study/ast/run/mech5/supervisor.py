"""Serial worker isolation and durable per-pair wall-budget outcomes.

The parent owns the writer lock. Only its one worker evaluates, and the parent
writes a stopped fact only after that worker has been killed and reaped.
"""
import copy
import json
import multiprocessing
from multiprocessing.reduction import DupFd
import os
import threading
import signal
import time
import traceback

from .target_store import Journal


def _restore_lock(handle):
    return handle.detach()


class _LockHandle:
    def __init__(self,fd):self.fd=fd
    def __reduce__(self):
        # Reduce during Process.start(), so spawn passes the descriptor
        # directly. Constructing DupFd earlier would create a socket service.
        return _restore_lock,(DupFd(self.fd),)


def _parent_lifetime(control):
    try:control.recv()
    except (EOFError,OSError):pass
    # No Python cleanup can be trusted if the supervisor has disappeared.
    # SQLite recovers the transaction; the shared file lock closes on exit.
    os._exit(125)


def _worker(args,events,control,inherited_lock):
    from . import targets
    from evaluator import ReplayEvaluator
    targets.STOP=False
    signal.signal(signal.SIGTERM,targets.stop)
    signal.signal(signal.SIGINT,targets.stop)
    threading.Thread(target=_parent_lifetime,args=(control,),daemon=True).start()
    ev=None;worker=None;lock_fd=None
    try:
        lock_fd=inherited_lock
        ev=ReplayEvaluator(run=targets.CODE_ROOT/'ast/run',
            config=targets.DATA_ROOT/'ast/run/corpus-v11/run.json',
            deadline=args.deadline,artifacts=targets.DATA/'replays')
        worker=targets.Pass(args,ev,event=events.send)
        events.send(dict(event='producer',code=worker.journal.code,config=worker.journal.config))
        complete=worker.run();worker.guard();worker.progress(worker.done,force=True)
        events.send(dict(event='finished',complete=complete))
    except BaseException:
        events.send(dict(event='fatal',reason=traceback.format_exc()))
    finally:
        if worker is not None:worker.journal.close();worker.base.close()
        if ev is not None:ev.close()
        events.close()
        if lock_fd is not None:os.close(lock_fd)
        control.close()


def _reap(worker,*,graceful=False):
    if worker.is_alive():
        if graceful:
            worker.terminate();worker.join(timeout=2)
        if worker.is_alive():worker.kill()
    worker.join(timeout=5)
    if worker.is_alive():raise RuntimeError('targets worker could not be reaped; no concurrent writer started')


def persist_stopped(args,producer,active,*,reason,elapsed,error=None):
    """Preserve an already committed pair if its completion event raced expiry."""
    journal=Journal(args.output,producer['code'],producer['config'])
    try:
        row=journal.db.execute("SELECT rowid FROM entries WHERE kind='pair' AND key=?",(active['pair_id'],)).fetchone()
        if row and row[0]!=active.get('prior_rowid'):return False
        inputs=dict(pair_id=active['pair_id'],source_sha256=active['source_sha256'])
        prior=journal.load('pair',active['pair_id'],inputs) or {}
        # Reusing prior references retains facts from an explicitly retried
        # unavailable/stopped attempt. No table or other pass result is copied.
        fact=dict(prior,source_sha256=active['source_sha256'],
            base_result_sha256=active['base_result_sha256'],
            work_stop=dict(kind=reason,phase=active.get('phase','pair_setup'),
                target_id=active.get('target_id'),seconds=args.pair_seconds,elapsed=round(elapsed,6),
                reason=('pair wall budget expired' if reason=='pair_wall_budget' else 'worker exited during pair')))
        if error is not None:fact['work_stop']['error']=error
        journal.save('pair',active['pair_id'],inputs,fact)
        return True
    finally:journal.close()


def supervise(args,*,lock,stopping=lambda:False):
    """Keep one task-cached worker; replace it only on expiry or unexpected exit."""
    context=multiprocessing.get_context('spawn');after=0;attempts=0
    while not stopping():
        child_args=copy.copy(args);child_args.start_after=after
        if args.limit is not None:
            child_args.limit=args.limit-attempts
            if child_args.limit<=0:return False
        receive,send=context.Pipe(duplex=False)
        control,keepalive=context.Pipe(duplex=False)
        worker=context.Process(target=_worker,args=(child_args,send,control,_LockHandle(lock.fileno())),name='targets-worker')
        worker.start();send.close();control.close()
        producer=None;active=None;started=None;finished=None;fatal=None;pipe_closed=False
        try:
            while True:
                if stopping():_reap(worker,graceful=True);return False
                # The clock is checked even with a continuously busy event pipe.
                if active is not None and time.monotonic()-started>=args.pair_seconds:
                    reason='pair_wall_budget';break
                if not pipe_closed and receive.poll(.1):
                    try:message=receive.recv()
                    except EOFError:message=None;pipe_closed=True
                    if message is not None:
                        event=message['event']
                        if event=='producer':producer=message
                        elif event=='pair_started':
                            active=message;started=time.monotonic()
                        elif event=='phase' and active is not None:
                            if message['pair_id']!=active['pair_id']:raise RuntimeError('worker pair phase differs')
                            active.update(phase=message['phase'],target_id=message['target_id'])
                        elif event=='pair_done':
                            after=message['done'];attempts+=1;active=None;started=None
                        elif event=='finished':finished=message['complete']
                        elif event=='fatal':fatal=message['reason']
                        continue
                if not worker.is_alive():
                    # Drain completion messages before interpreting worker exit.
                    if not pipe_closed and receive.poll():continue
                    worker.join(timeout=1)
                    if fatal and active is None:raise RuntimeError('targets worker failed before pair start:\n'+fatal)
                    if finished is not None:return finished
                    if active is None:raise RuntimeError('targets worker exited before pair start: '+str(worker.exitcode))
                    reason='worker_error' if fatal else 'worker_exit';break
                if pipe_closed:time.sleep(.05)
            _reap(worker)
            if producer is None:raise RuntimeError('targets worker supplied no producer identity')
            elapsed=time.monotonic()-started
            written=persist_stopped(args,producer,active,reason=reason,elapsed=elapsed,error=fatal)
            print(json.dumps(dict(event='pair_stopped' if written else 'pair_committed_before_stop',
                pair_id=active['pair_id'],target_id=active.get('target_id'),phase=active.get('phase'),
                reason=reason,seconds=args.pair_seconds,elapsed=round(elapsed,3)),sort_keys=True),flush=True)
            after=active['done'];attempts+=1
        finally:
            _reap(worker);receive.close();keepalive.close()
    return False
