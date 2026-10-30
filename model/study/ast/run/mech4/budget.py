"""Auditable per-pair native-call/work ledger, including split/provenance calls."""
from common import canonical,digest
import json
import time


class Bound(RuntimeError):pass


class Budget:
    def __init__(self,journal,pair_id,scope,config,stopping,before_call):
        self.journal=journal;self.pair=pair_id;self.scope=scope;self.config=config
        self.start=time.monotonic();self.stopping=stopping
        self.before_call=before_call
    def used(self):
        count,charge=self.journal.db.execute('SELECT count(*),coalesce(sum(charge),0) FROM operations '
            'WHERE pair_id=? AND scope=?',(self.pair,self.scope)).fetchone()
        return count,charge
    def remaining(self):
        count,charge=self.used()
        return max(.001,min(self.config['pair_seconds']-charge,self.config['pair_seconds']-(time.monotonic()-self.start)))
    def check(self):
        count,charge=self.used()
        if self.stopping():raise Bound('interrupted after durable work')
        if charge>=self.config['pair_seconds'] or time.monotonic()-self.start>=self.config['pair_seconds']:
            raise Bound('pair native-call/time bound reached')
    def replay(self,ev,*args,**kwargs):
        self.check();phase=kwargs.pop('_phase','TRAIN screen')
        if self.used()[0]>=self.config['max_native_calls']:raise Bound('pair native-call bound reached')
        self.before_call()
        identity=digest(dict(args=args,kwargs=kwargs))
        # Reserve before execution. A killed in-flight operation is charged its
        # full declared deadline, rather than disappearing on restart.
        with self.journal.db:
            cursor=self.journal.db.execute('INSERT INTO operations(pair_id,scope,phase,identity,charge,status,payload) '
                'VALUES (?,?,?,?,?,?,?)',(self.pair,self.scope,phase,identity,ev.deadline,'started',None))
            number=cursor.lastrowid
        start=time.monotonic()
        try:
            result=ev.replay_program(*args,**kwargs)
        except BaseException:
            # Keep reserved upper bound for an unfinished/uncertain operation.
            raise
        with self.journal.db:
            self.journal.db.execute('UPDATE operations SET charge=?,status=?,payload=? WHERE id=?',
                (time.monotonic()-start,'finished',canonical(dict(engine=result['engine'],artifact=result['artifact'],
                    result_sha256=digest(result))),number))
        return result
    def ledger(self):
        rows=self.journal.db.execute('SELECT id,phase,identity,charge,status,payload FROM operations '
            'WHERE pair_id=? AND scope=? ORDER BY id',(self.pair,self.scope)).fetchall()
        return [dict(id=i,phase=p,identity=h,charged_seconds=c,status=s,receipt=json.loads(r) if r else None)
                for i,p,h,c,s,r in rows]


class ReplayProxy:
    """Delegate the same evaluator, charging EVERY canonical proof operation."""
    def __init__(self,ev,budget):
        object.__setattr__(self,'ev',ev);object.__setattr__(self,'budget',budget)
    def __getattr__(self,name):return getattr(self.ev,name)
    def __setattr__(self,name,value):setattr(self.ev,name,value)
    def replay_program(self,*args,**kwargs):
        return self.budget.replay(self.ev,*args,**kwargs,_phase='independent TRAIN+TEST/provenance')
