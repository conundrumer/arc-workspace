"""Task groups for the read, from the gold files at gold-v3-rigid-round50.

Positive: the gold file has a RIGID_DET form in some case. One-pose stems are the group that the earlier read fixed, from rigid.md's Evidence: a stamp and its direction stored as one assembly, one pose in the observed data. Looks-posed stems are rigid.md's. All other tasks are plain.

Split: left-out is the 62 evaluation tasks of leave_out.txt outside held/tasks.txt, held is held/tasks.txt, train is the rest.

Writes labels.tsv: task, group, split, form_in_file, form_in_smallest, added_round50, alt_path of the first form.
"""
import collections
import gzip
import json
import os
import re

R = '/Users/davidlu/code/arc-workspace/'
GOLD = R + 'work/lm/data-study/gold/gen-v3-11f6a212c/'
HELD = R + 'work/lm/data-study/sampler/sampler-worker/held/'
RUN = os.path.dirname(os.path.abspath(__file__)) + '/'
ONE_POSE = '08573cc6 7447852a 0becf7df 8403a5d5 1e5d6875 3f23242b 3ac3eb23 3618c87e'.split()
LOOKS = '291dc1e1 3e980e27 626c0bcc ed74f2f2'.split()


def strip_comments(s):
    return re.sub(r';[^\n]*', '', s)


def has_form(text):
    return re.search(r'\(RIGID_DET\b', strip_comments(text)) is not None


def alt_path(text):
    """The ALT names that enclose the first RIGID_DET form, from a paren walk of the text."""
    s = text
    i, depth = 0, 0
    stack = []
    in_str = False
    while i < len(s):
        ch = s[i]
        if in_str:
            in_str = ch != '"'
        elif ch == '"':
            in_str = True
        elif ch == ';':
            i = s.find('\n', i)
            if i < 0:
                break
        elif ch == '(':
            m = re.match(r'\((ALT|RIGID_DET)\s+(\S+)', s[i:])
            if m and m.group(1) == 'ALT':
                stack.append((depth, m.group(2)))
            if m and m.group(1) == 'RIGID_DET':
                return '/'.join(n for _, n in stack) or '-'
            depth += 1
        elif ch == ')':
            depth -= 1
            while stack and stack[-1][0] >= depth:
                stack.pop()
        i += 1
    return ''


def main():
    tasks = sorted(f[:-5] for f in os.listdir(R + 'data/tasks') if f.endswith('.json'))
    gen = GOLD + 'corpus/gen/'
    leave = set(open(HELD + 'leave_out.txt').read().split())
    held = set(open(HELD + 'tasks.txt').read().split())
    r50 = set(open(GOLD + 'changed-gold-round50.txt').read().split())
    rows = []
    for t in tasks:
        p = gen + t + '.arclog'
        if not os.path.exists(p):
            rows.append((t, 'no-gold', 'none', 0, 0, 0, ''))
            continue
        text = open(p).read()
        in_file = has_form(text)
        small, path = 0, ''
        if in_file:
            path = alt_path(text)
            q = f'{GOLD}ast-corpus/{t}/pairs.jsonl.gz'
            with gzip.open(q, 'rt') as f:
                small = int(any('RIGID_DET' in json.loads(x)['gold_sexp'] for x in f))
        if t in ONE_POSE:
            group = 'one-pose'
        elif in_file:
            group = 'positive'
        elif t in LOOKS:
            group = 'looks-posed'
        else:
            group = 'plain'
        split = 'held' if t in held else 'left-out' if t in leave else 'train'
        rows.append((t, group, split, int(in_file), small, int(t in r50), path))
    with open(RUN + 'labels.tsv', 'w') as f:
        f.write('task\tgroup\tsplit\tform_in_file\tform_in_smallest\tadded_round50\talt_path\n')
        for r in rows:
            f.write('\t'.join(map(str, r)) + '\n')
    c = collections.Counter((r[1], r[2]) for r in rows)
    for k in sorted(c):
        print(k, c[k])
    for r in rows:
        if r[3]:
            print(r)
    print('one-pose stems without the form:', [r[0] for r in rows if r[1] == 'one-pose' and not r[3]])


main()
