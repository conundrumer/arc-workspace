"""The writer plan of a process: `ordered` or `unordered` (lookahead_legal.PLAN_RULES gives the rules of each).

A tree records the plan of its training rows. fit_trees.py writes its report beside the tree as `<tree>.json`: the report's `plan`, else the plan folder of each of its
`points_dir` (samples/SET/points/<plan>). A tree with no report gives the plan in its file's base name, where the name has one.

The plan of a process (plan_of_process):
- With a tree (WRITER_TREE), the plan that the tree records. WRITER_PLAN, where it is set, must give the same plan, else the plan raises. A tree that records no plan needs WRITER_PLAN.
- With no tree (the hand-set distribution), WRITER_PLAN, else NO_TREE_PLAN.

This module imports no other module of the sampler, so a script that starts sampler processes can read a tree's plan.
"""
import json
import os

PLANS = ('ordered', 'unordered')
NO_TREE_PLAN = 'ordered'  # the first-guess plan


def plan_of_tree(path):
    """The plan that the tree at `path` records, else None. Raises where the report and the file's name give different plans, or where the report's points folders differ in plan."""
    named = next((p for p in ('unordered', 'ordered') if p in os.path.basename(path)), None)
    try:
        with open(path + '.json') as f:
            report = json.load(f)
    except (OSError, ValueError):
        return named
    if report.get('plan') in PLANS:
        got = {report['plan']}
    else:
        dirs = report.get('points_dir') or []
        got = {os.path.basename(os.path.normpath(d)) for d in ([dirs] if isinstance(dirs, str) else dirs)} & set(PLANS)
    if len(got) > 1:
        raise ValueError('the report %s.json gives the plans %s' % (path, sorted(got)))
    recorded = next(iter(got), None)
    if recorded is not None and named is not None and recorded != named:
        raise ValueError('the report %s.json gives the plan %r, and the file name gives %r' % (path, recorded, named))
    return recorded or named


def plan_of_process(tree, setting):
    """(plan, source): the writer plan of a process whose tree is `tree` (WRITER_TREE; '' or None for none) and whose WRITER_PLAN is `setting` ('' or None for none), and where it comes from."""
    if setting and setting not in PLANS:
        raise ValueError('WRITER_PLAN: %r is not one of %s' % (setting, PLANS))
    if not tree:
        return (setting, 'WRITER_PLAN') if setting else (NO_TREE_PLAN, 'the plan with no WRITER_TREE')
    recorded = plan_of_tree(tree)
    if recorded is None:
        if not setting:
            raise ValueError('WRITER_TREE %s records no plan (no report %s.json, and no plan in its name): set WRITER_PLAN' % (tree, tree))
        return setting, 'WRITER_PLAN; WRITER_TREE %s records no plan' % tree
    if setting and setting != recorded:
        raise ValueError('WRITER_PLAN gives %r, and WRITER_TREE %s records %r: unset WRITER_PLAN, or set it to %s' % (setting, tree, recorded, recorded))
    return recorded, 'WRITER_TREE %s' % tree


def of_environment():
    """(plan, source) of this process's environment (WRITER_TREE, WRITER_PLAN)."""
    return plan_of_process(os.environ.get('WRITER_TREE'), os.environ.get('WRITER_PLAN'))
