"""Hook refusals and advisories across executable shell boundaries."""
import pytest
from tests.conftest import script


@pytest.mark.parametrize('command', [
    'until grep -q done file; do :; read -t 5 </dev/zero; done',
    'while kill -0 12345; do :; done',
    'while kill -0 1; do : | :; done',
    'while kill -0 1; do read x | :; done',
    'while kill -0 1; do :; : | read x; done',
    'f() { while kill -0 1; do :; done; }; f',
    'time while kill -0 1; do :; done',
    'case x in x) while kill -0 1; do :; done;; esac',
    'while kill -0 1; do command -p true; done',
    'while kill -0 1; do command -p -- true; done',
    'while kill -0 1; do builtin -- true; done',
    "X=value command -p bash -c 'while kill -0 1; do :; done'",
    "command -p -- bash -c 'while kill -0 1; do :; done'",
    ": 'unattended-wait: command'; while kill -0 12345; do true; done",
    '(while kill -0 12345; do :; done) &',
    'while kill -0 1 && kill -0 2; do\n:\ndone',
    'result="$(while kill -0 12345; do :; done)"',
    'echo $(echo $(while kill -0 1; do :; done))',
    'echo `while kill -0 1; do :; done`',
    'cat <(while kill -0 1; do :; done)',
    'cat >$(while kill -0 1; do :; done)',
    'cat <<EOF\n$(while kill -0 1; do :; done)\nEOF\n',
    'while read line; do echo "$(while kill -0 1; do :; done)"; done',
    "bash -c 'while kill -0 12345 2>/dev/null; do :; done'",
    "/bin/bash -lc 'while kill -0 1; do :; done'",
    "command env -i bash -c 'while kill -0 1; do :; done'",
    '''sh -c "bash -c 'while kill -0 1; do :; done'"''',
    "bash -s <<'EOF'\nwhile kill -0 1; do :; done\nEOF\n",
    "bash <<< 'while kill -0 1; do :; done'",
    'bash -c "$(while kill -0 1; do :; done)"',
    'while kill -0 1 || read line; do :; done',
    'until kill -0 1 && read line; do :; done',
    'while ! { kill -0 1 && read line; }; do :; done',
    'while { read line & kill -0 1; }; do :; done',
    'while { for x in a; do read line; done; kill -0 1; }; do :; done',
    'while if kill -0 1; then read line; else true; fi; do :; done',
    'while kill -0 1 || sleep 1; do :; done',
    'while f() { read line; }; do :; done',
    "env -u X bash --norc -c 'while kill -0 1; do :; done'",
    'until kill -0 1 && wait; do :; done',
    "bash -c 'while kill -0 1 || read line; do :; done'",
])
def test_denied(command: str) -> None:
    hook = script('busy_loop_hook')
    data = {'tool_name': 'Bash', 'tool_input': {'command': command}}
    assert hook.check(data)
    assert hook.context(data) is None


@pytest.mark.parametrize('command', [
    "echo 'while kill -0 1; do :; done'",
    'echo \\while kill -0 1 # while kill -0 1; do :; done',
    '# while kill -0 1; do :; done\necho ok',
    "cat <<'EOF'\nwhile kill -0 1; do :; done\nEOF\n",
    "bash -c 'echo ok' 'while kill -0 1; do :; done'",
    "printf '%s' 'while kill -0 1; do :; done'",
    "bash -c 'cat' <<'EOF'\nwhile kill -0 1; do :; done\nEOF\n",
    "bash -nc 'while kill -0 1; do :; done'",
    "command -v bash 'while kill -0 1; do :; done'",
    "command -V bash 'while kill -0 1; do :; done'",
    "command -pv bash 'while kill -0 1; do :; done'",
    "builtin bash -c 'while kill -0 1; do :; done'",
    "command builtin bash -c 'while kill -0 1; do :; done'",
    'bash -c "$script"',
    'echo "<(while kill -0 1; do :; done)"',
    "bash -o noexec -c 'while kill -0 1; do :; done'",
    'while read l; do echo "$l"; done < f',
    'while read l; do :; done < f',
    "while printf 'a\\n' | read x; do :; done",
    'while read x | true && read y; do :; done',
    "echo 'time while kill -0 1; do :; done'",
    "echo 'case x in x) while kill -0 1; do :; done;; esac'",
    'while sleep 1; do :; done',
    'while kill -0 1; do sleep 1; done',
    'while kill -0 1; do python work.py; done',
    'for i in a b; do echo "$i"; done',
    'while kill -0 1 && read line; do :; done',
    'until kill -0 1 || read line; do :; done',
    'while ! read line; do :; done',
    'while read line; kill -0 1; do :; done',
    'while { read line; kill -0 1; }; do :; done',
    'while if kill -0 1; then read line; else sleep 1; fi; do :; done',
    "bash -c 'while read line; do :; done'",
    "bash <<< 'while read line; do echo ok; done'",
])
def test_clear(command: str) -> None:
    hook = script('busy_loop_hook')
    data = {'tool_name': 'Bash', 'tool_input': {'command': command}}
    assert hook.check(data) is None
    assert hook.context(data) is None


@pytest.mark.parametrize('command', [
    'while kill -0 12345; do printf ""; done',
    'while kill -0 1; do printf x | :; done',
    'case x in x) while kill -0 1; do printf x; done;; esac',
    'while kill -0 1; do x=1; done',
    'while kill -0 1; do ((x++)); done',
    ": 'unattended-wait: command'; while kill -0 1; do printf ''; done",
    'echo "$(while kill -0 1; do printf \'\'; done)"',
    'while kill -0 1; do echo ok; done; until test -f f; do false; done',
    "bash -c 'while kill -0 1; do printf x; done'",
    "bash -s <<'EOF'\nwhile kill -0 1; do printf x; done\nEOF\n",
])
def test_warning(command: str) -> None:
    hook = script('busy_loop_hook')
    data = {'tool_name': 'Monitor', 'tool_input': {'command': command}}
    assert hook.check(data) is None
    warning = hook.context(data)
    assert warning and len(warning.splitlines()) == 1


def test_monitor_without_command() -> None:
    hook = script('busy_loop_hook')
    data = {'tool_name': 'Monitor', 'tool_input': {'ws': 'workspace'}}
    assert hook.check(data) is None
    assert hook.context(data) is None
