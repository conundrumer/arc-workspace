"""Project-agent delete refusals for executable shell input and role roots."""

import json
import sys
import os
from pathlib import Path

import pytest

from engine import checkout
from handbook.paths import scripts_importable

scripts_importable()

from delete_bash_hook import check  # pyright: ignore[reportMissingImports]
from tree_reads import scratch  # pyright: ignore[reportMissingImports]

AGENT = 'a0000000000000001'
JOINED = checkout.scripts() / 'joined_hooks.py'
MAIN = checkout.main_worktree(checkout.ROOT)


@pytest.fixture
def session(tmp_path, monkeypatch):
    root = tmp_path / 'checkout'
    definitions = root / '.claude' / 'agents'
    definitions.mkdir(parents=True)
    for kind in ['ticket-reviewer', 'code-reviewer', 'design-reviewer', 'doc-reviewer', 'item-checker', 'lib-reviewer', 'code-editor']:
        (definitions / f'{kind}.md').write_text('fixture')
    (root / '.git').write_text(f'gitdir: {MAIN / ".git"}\n')
    monkeypatch.setattr(checkout, 'ROOT', root)
    project = tmp_path / 'project' 
    transcripts = project / 's' / 'subagents'
    transcripts.mkdir(parents=True)
    (project / 's.jsonl').write_text('')
    (transcripts / f'agent-{AGENT}.jsonl').write_text('')
    (transcripts / f'agent-{AGENT}.meta.json').write_text(json.dumps({'agentType': 'ticket-reviewer'}))
    # Only paths and process environment are replaced; repo readers stay real.
    import tree_reads  # pyright: ignore[reportMissingImports]
    monkeypatch.setattr(tree_reads, 'SCRATCH_ROOT', tmp_path / 'scratch-root')
    monkeypatch.setattr(os, 'environ', {})
    monkeypatch.setenv('DELETE_TEST_ROOT', str(scratch('s', project.name)))
    return {'tool_name': 'Bash', 'agent_id': AGENT,
            'transcript_path': str(project / 's.jsonl'), 'cwd': str(tmp_path),
            'tool_input': {'command': ''}}


def command(session, text):
    return session | {'tool_input': {'command': text}}


CONTEXTS = [
    'rm -rf {p}', 'rmdir {p}', 'unlink {p}', 'find {p} -delete',
    'git -C {p} clean -fd', 'git rm -- {p}', 'git worktree remove {p}',
    'mv {p} /tmp/destination', 'sh -c "rm -rf {p}"',
    "timeout 60 env -u FORCE_COLOR sh -c 'rm -rf {p}'",
    'sh <<SH\nrm -rf {p}\nSH\n',
    "sh <<'SH'\nrm -rf {p}\nSH\n",
    'sh <<-SH\n\trm -rf {p}\n\tSH\n',
    ': "$(rm -rf {p})"', ': `rm -rf {p}`', 'cat <(rm -rf {p})',
    'cat >(rm -rf {p})', 'echo >"$(rm -rf {p})"',
    'X=$(rm -rf {p})', 'cat <<DATA\n$(rm -rf {p})\nDATA\n',
    'sh -c sh <<SH\nrm -rf {p}\nSH\n',
    "sh 3<<'DATA' <<'SH'\nrm /outside/inert\nDATA\nrm -rf {p}\nSH\n",
    'sh <<ONE <<TWO\n: inert\nONE\nrm -rf {p}\nTWO\n',
    'S={p}; rm -rf "$S"', 'rm -rf $DELETE_TEST_ROOT/../outside',
    ': "${{V:-$(rm -rf {p})}}"', ': "$((1 + $(rm -rf {p})))"',
    ': "${{V:-`rm -rf {p}`}}"', ': "$((1 + `rm -rf {p}`))"',
    'find -H {p} -delete',
    'sh 3<<SH <&3\nrm -rf {p}\nSH\n',
    '(false) || rm -rf {p}',
    '! rm -rf {p}',
    'r\\\nm -rf {p}',
]


@pytest.mark.parametrize('form', CONTEXTS)
def test_deletes_are_checked_in_executable_contexts(session, form):
    assert check(command(session, form.format(p='/outside/reviewer'))) is not None
    if 'DELETE_TEST_ROOT' not in form:
        own = scratch('s', Path(session['transcript_path']).parent.name)
        assert check(command(session, form.format(p=own / 'probe'))) is None


@pytest.mark.parametrize('text', [
    "echo 'rm -rf /outside'", 'echo "rm -rf /outside"', '# rm -rf /outside\ntrue',
    r'echo \$(rm -rf /outside)', "cat <<'DATA'\n$(rm -rf /outside)\nDATA\n",
    'cat <<DATA\nrm -rf /outside\nDATA\n', r'echo "\$(rm -rf /outside)"',
    'echo "<(rm -rf /outside)"',
])
def test_inert_text_is_allowed(session, text):
    # An escaped dollar followed by bare parentheses is invalid shell syntax.
    if text == r'echo \$(rm -rf /outside)':
        assert check(command(session, text)) is not None
    else:
        assert check(command(session, text)) is None


@pytest.mark.parametrize('text', [
    'python -c "import os; os.remove(\'/outside\')"',
    "sh <<'SH'\npython <<'PY'\nfrom pathlib import Path\nPath('/outside').unlink()\nPY\nSH\n",
    ': "$(python -c \'import shutil; shutil.rmtree("/outside")\')"',
    'ls | xargs rm -f', 'rm "$UNSET_DELETE_OPERAND"',
    'echo "$(unterminated"', 'for p in /outside; do rm "$p"; done',
    'coproc rm /outside', 'sudo -u nobody rm /outside',
])
def test_python_and_unreadable_deletes_are_refused(session, text, monkeypatch):
    monkeypatch.delenv('UNSET_DELETE_OPERAND', raising=False)
    assert check(command(session, text)) is not None


def test_substitution_directory_is_local(session):
    own = scratch('s', Path(session['transcript_path']).parent.name)
    assert check(command(session, f'cd {own}; : "$(cd /outside; rm probe)"; rm probe')) is not None
    assert check(command(session, f'cd {own} && : "$(cd child && rm probe)" && rm probe')) is None
    assert check(command(session, f'cd /outside; : "$(cd {own}; rm probe)"; rm probe')) is not None
    assert check(command(session, f'cd {own} && rm probe')) is None
    assert check(command(session, f'cd {own} || rm /outside/probe')) is not None


def test_invoked_python_file_has_no_required_shell_delete_word(session):
    project = Path(session['transcript_path']).parent
    own = scratch('s', project.name)
    own.mkdir(parents=True, exist_ok=True)
    script = own / 'delete-fixture.py'
    script.write_text("from pathlib import Path\nPath('/outside').unlink()\n")
    try:
        assert check(command(session, f'uv run python {script}')) is not None
    finally:
        script.unlink()


@pytest.mark.parametrize('kind', ['ticket-reviewer', 'code-reviewer', 'design-reviewer',
                                  'doc-reviewer', 'item-checker', 'lib-reviewer', 'code-editor',
                                  'general-purpose'])
def test_role_roots(session, kind):
    meta = Path(session['transcript_path']).parent / 's' / 'subagents' / f'agent-{AGENT}.meta.json'
    meta.write_text(json.dumps({'agentType': kind}))
    from state_reads import new_state  # pyright: ignore[reportMissingImports]
    new_state()
    assert (check(command(session, 'rm /outside/probe')) is not None) == (kind != 'general-purpose')
    reason = check(command(session, 'rm /tmp/probe'))
    assert (reason is not None) == (kind not in {'code-editor', 'general-purpose'})


def test_main_session_is_exempt(session):
    session.pop('agent_id')
    assert check(command(session, 'rm /outside')) is None


def test_symbolic_link_is_checked_where_it_stands(session, tmp_path):
    own = scratch('s', Path(session['transcript_path']).parent.name)
    own.mkdir(parents=True)
    link = own / 'link'
    link.symlink_to(tmp_path, target_is_directory=True)
    assert check(command(session, f'rm {link}')) is None
    assert check(command(session, f'rm {link}/outside')) is not None


def test_unknown_pipeline_input_and_split_variables_are_refused(session):
    own = scratch('s', Path(session['transcript_path']).parent.name)
    assert check(command(session, "printf 'rm /outside' | sh")) is not None
    assert check(command(session, "printf 'rm /outside' |& sh")) is not None
    assert check(command(session, f"S='{own}/x /outside'; rm $S")) is not None
    assert check(command(session, f"S={own}; T=$S; rm $T/probe")) is None
    assert check(command(session | {'cwd': str(own)}, '/usr/bin/env -C /outside rm probe')) is not None


def test_joined_entry_does_not_skip_substitutions(session, monkeypatch):
    from tests.hookrun import run_hook
    monkeypatch.setattr(sys, 'argv', [str(JOINED), 'bash'])
    code, out, err = run_hook(JOINED, json.dumps(command(session, ': "$(rm -rf /outside)"')), env={})
    assert code == 0 and 'failed' not in err, err
    assert json.loads(out)['hookSpecificOutput']['permissionDecision'] == 'deny'


@pytest.mark.parametrize(('refused', 'allowed'), [
    ("A=1 eval 'rm /outside/probe'", 'A=1 rm "{s}/probe"'),
    ('cd "{s}" && command cd / && rm probe',
     'cd "{s}" && command cd child && rm probe'),
    ('cd "{s}" && builtin cd / && rm probe',
     'cd "{s}" && builtin cd child && rm probe'),
    ('cd "{s}" && pushd / && rm probe',
     'cd "{s}" && pushd child && rm probe'),
    ('cd /outside; pushd "{s}"; popd; rm probe',
     'cd "{s}" && pushd child && popd && rm probe'),
    ("TARGET={s}; sh -c 'rm \"$TARGET/probe\"'",
     "export TARGET={s}; sh -c 'rm \"$TARGET/probe\"'"),
    ("env TARGET=/outside sh -c 'rm \"$TARGET/probe\"'",
     "env TARGET={s} sh -c 'rm \"$TARGET/probe\"'"),
    ('TARGET={s}; unset TARGET; rm "$TARGET/probe"',
     'TARGET={s}; unset TARGET; TARGET={s}; rm "$TARGET/probe"'),
    ("export TARGET={s}; export -n TARGET; sh -c 'rm \"$TARGET/probe\"'",
     "TARGET={s}; export -n TARGET; export TARGET={s}; sh -c 'rm \"$TARGET/probe\"'"),
    (': ${{MISSING:-<(rm /outside/probe)}}', ': ${{MISSING:-<(rm {s}/probe)}}'),
    (': ${{MISSING:->(rm /outside/probe)}}', ': ${{MISSING:->(rm {s}/probe)}}'),
    (': $((1 + <(rm /outside/probe)))', ': $((1 + <(rm {s}/probe)))'),
    ('find "{s}/.." -delete', 'find "{s}/child/.." -delete'),
    ('find "{s}/../." -delete', 'find "{s}/." -delete'),
    ('cd /outside && pushd {s} && popd +0 && rm probe',
     'cd {s} && pushd child && popd +0 && cd {s} && rm probe'),
    ('cd /outside && pushd {s} && pushd +1 && rm probe',
     'cd {s} && pushd child && rm probe'),
    ('readonly TARGET=/outside; TARGET={s}; rm "$TARGET/probe"',
     'readonly TARGET=/outside; TARGET={s}; rm "{s}/probe"'),
    *[(f'TARGET={{s}}; {builtin}; rm "$TARGET/probe"',
       f'TARGET={{s}}; {builtin}; rm {{s}}/probe')
      for builtin in ['declare TARGET=/outside', 'typeset TARGET=/outside',
                      'local TARGET=/outside', 'readonly TARGET=/outside',
                      'read TARGET <<< /outside', 'printf -v TARGET /outside',
                      'mapfile TARGET', 'readarray TARGET', 'getopts x TARGET',
                      'let TARGET=0']],
])
def test_state_and_nested_expansion_refusals(session, monkeypatch, refused, allowed):
    from tests.hookrun import run_hook
    own = scratch('s', Path(session['transcript_path']).parent.name)
    monkeypatch.setattr(sys, 'argv', [str(JOINED), 'bash'])
    for text, deny in [(refused, True), (allowed, False)]:
        event = command(session, text.format(s=own))
        assert (check(event) is not None) == deny
        code, out, err = run_hook(JOINED, json.dumps(event), env={})
        assert code == 0 and 'failed' not in err, err
        response = json.loads(out) if out.strip() else {}
        assert (response.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny') == deny


@pytest.mark.parametrize(('text', 'program'), [
    ('rm "$UNKNOWN_DELETE_ROOT/probe"', 'rm'),
    ('printf x | xargs unlink', 'unlink'),
])
def test_unresolved_delete_reason_identifies_the_call(session, monkeypatch, text, program):
    event = command(session, text)
    reason = check(event)
    assert reason is not None and program in reason
    from tests.hookrun import run_hook
    monkeypatch.setattr(sys, 'argv', [str(JOINED), 'bash'])
    code, out, err = run_hook(JOINED, json.dumps(event), env={})
    assert code == 0 and 'failed' not in err, err
    response = json.loads(out)['hookSpecificOutput']
    assert response['permissionDecision'] == 'deny'
    assert program in response['permissionDecisionReason']


def test_final_dot_resolves_a_directory_link(session, monkeypatch, tmp_path):
    from tests.hookrun import run_hook
    own = scratch('s', Path(session['transcript_path']).parent.name)
    own.mkdir(parents=True)
    (own / 'outside').symlink_to(tmp_path, target_is_directory=True)
    (own / 'inside').symlink_to(own, target_is_directory=True)
    monkeypatch.setattr(sys, 'argv', [str(JOINED), 'bash'])
    for link, denied in [('outside', True), ('inside', False)]:
        event = command(session, f'find {own}/{link}/. -delete')
        assert (check(event) is not None) == denied
        code, out, err = run_hook(JOINED, json.dumps(event), env={})
        assert code == 0 and 'failed' not in err, err
        response = json.loads(out) if out.strip() else {}
        assert (response.get('hookSpecificOutput', {}).get('permissionDecision') == 'deny') == denied
