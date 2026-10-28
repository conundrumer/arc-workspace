# Native evaluator failure containment

Task-scoped Python evaluation, gold-table collection, component collection,
continuation collection and ingestion catch native panics inside the cache
guard's lifetime. A native assertion is still an error, reported as a Python
ValueError with the original panic reason. It never becomes a successful
empty table or a replacement assignment. Failed case observations/results
are discarded before that exception reaches Python. The mutex does not
unwind and poison while the original error is being propagated.

`finish_case` is an explicit discard operation. It can acquire a previously
poisoned cache solely to discard its case data and clear the poison flag;
it does not resume a partially updated observation. Other cache operations
reject a poisoned cache with an explicit request to finish the failed case.
This prevents cleanup from replacing an original packing error with a
second `task evaluator cache is not poisoned` panic.

Observed example: corpus-v6 runtime6108, task0becf7df `$Line`, native packing
assertion arity3/schema2 followed by a panic during finally/finish_case.
The foreign-shaped held assignment is a separate core validation fix owned
by export. This boundary preserves that error and prevents it escaping as
PanicException (BaseException) or killing cleanup through mutex poisoning.
