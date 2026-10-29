"""Print Codex threads whose work stopped with nobody continuing it.

A turn ending with a final answer that starts with COORDINATOR:, or a failed or
interrupted turn, prints at once. Any other completed turn
prints when no new turn starts on that thread within IDLE seconds, including a
turn with an empty final answer, except the one turn right after an END, which
acknowledges the coordinator's answer to that request. Failed requests
print at once. The dups thread answers other threads' questions, so its idle
turns never print.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import json, pathlib, select, sys, time
IDLE = 120
final, idle, ended = {}, {}, set()
QUIET = {'dups'}

def emit(text):
    print(text, flush=True)

def handle(r):
    if r.get('error') is not None:
        emit(f"REQUEST FAILED id={r.get('id')}: {str(r['error'].get('message'))[:200]}")
        return
    p, m = r.get('params') or {}, r.get('method')
    thread = p.get('threadId'); name = names.get(thread)
    if name is None:
        return
    if m == 'turn/started':
        idle.pop(thread, None)
    elif m == 'item/completed':
        item = p['item']
        if item.get('type') == 'agentMessage' and item.get('phase') == 'final_answer':
            final[p.get('turnId')] = item.get('text') or ''
    elif m == 'turn/completed':
        turn = p['turn']; status = turn.get('status')
        text = ' '.join(final.pop(turn['id'], '').split())[:300]
        if status != 'completed' or text.lstrip(' *').startswith('COORDINATOR:'):
            emit(f"END {name} [{status}]: {text}"); ended.add(thread)
        elif thread in ended:
            ended.discard(thread)
        elif name not in QUIET:
            idle[thread] = (time.monotonic() + IDLE, f"IDLE {name}: {text or '(empty final answer)'}")

def main():
    global names
    D = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_ROOT / 'codex-adm'
    names = {(D / f'{n}.thread').read_text().strip(): n.replace('cjudge', 'auditor') for n in sys.argv[2:]}
    import os
    fd, buf = sys.stdin.fileno(), b''
    while True:
        ready, _, _ = select.select([fd], [], [], 5)
        if ready:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            buf += chunk
            *lines, buf = buf.split(b'\n')
            for line in lines:
                try:
                    handle(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass
        now = time.monotonic()
        for thread, (due, text) in list(idle.items()):
            if now >= due:
                del idle[thread]; emit(text)


if __name__ == '__main__':
    main()
