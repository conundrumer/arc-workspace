"""Session budget selectors must refuse before profiling any selected run."""

import json
import os
import subprocess

import pytest

from tests.test_profile_runs import assistant, user, write_jsonl
from tests.conftest import script

profile_runs = script('profile_runs')
transcripts = script('transcripts')


@pytest.fixture
def population(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'environ', {})
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path / '.claude'))
    monkeypatch.setenv('ARC_CACHE', str(tmp_path / 'cache'))
    project = tmp_path / '.claude/projects/project'
    agents = project / 'session-123/subagents'
    agents.mkdir(parents=True)
    main = project / 'session-123.jsonl'
    write_jsonl(main, [user(0, 'brief'), assistant(1, {'type': 'text', 'text': 'done'})])
    path = agents / 'agent-a0.jsonl'
    write_jsonl(path, [user(0, 'brief'), assistant(50,
                  {'type': 'text', 'text': 'done'}, stop='end_turn')])
    path.with_suffix('.meta.json').write_text(json.dumps({'agentType': 'code-reviewer'}))
    paths = [path]
    original = subprocess.run
    children = []
    def run(command, *args, **kwargs):
        if isinstance(command, list) and any(str(p).endswith('/budgets.py') for p in command):
            children.append(command)
        kwargs.setdefault('env', dict(os.environ))
        return original(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', run)
    transcripts.new_state()
    return main, paths, children


@pytest.mark.parametrize('selectors', ['session', 'prefix', 'path', 'mixed-first', 'mixed-last'])
@pytest.mark.parametrize('filters', [[], ['--type', 'code-reviewer'],
                                    ['--active-since', '2026-10-04T00:00:30Z']])
def test_session_refused(population, selectors, filters, capsys):
    main, paths, children = population
    ids = {'session': ['session-123'], 'prefix': ['session-'], 'path': [str(main)],
           'mixed-first': [str(main), str(paths[0])],
           'mixed-last': [str(paths[0]), str(main)]}[selectors]
    assert profile_runs.main([*ids, '--run-budgets', *filters]) == 2
    out = capsys.readouterr()
    assert 'wall ' not in out.out
    assert out.err
    assert not children


