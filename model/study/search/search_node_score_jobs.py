"""Writes the job files of the node score run from the base kit's job file, and checks them.

  <python> -I search_node_score_jobs.py BASE_JOBS OUT_FOLDER

BASE_JOBS is the 100-line job file of the base kit. The base line of a task and seed has ARCLOG_IDENT_SOURCE=type and the arm dagb or dagbf.
Writes to OUT_FOLDER:
  stage1  search-node-score-jobs-parity-2tasks-300s.txt: 6 lines at 300 s. Four parity lines (ship.npz with NODE_SCORE_CHECK=1, tasks 135a2760 and 74dd1130,
          seeds 0 and 1000), and one mt line and one depth line on 135a2760 at seed 0.
  stage2  search-node-score-jobs-arms-heldout50-2seeds-600s.txt: 300 lines, in the task order of BASE_JOBS, the 6 lines of a task together: bundle, mt, depth,
          each at seed 0 and 1000.
Prints the counts of the checks. The exit status is 1 where one fails.
"""
import os
import re
import sys

NODE_SCORE = 'NODE_SCORE=$PWD/scores/%s.npz '
CHECK = 'NODE_SCORE_CHECK=1 '
FILES = ('search-node-score-jobs-parity-2tasks-300s.txt', 'search-node-score-jobs-arms-heldout50-2seeds-600s.txt')
LINE = re.compile(r'^(?P<head>.*?)\./run3600\.sh (?P<task>\w+) (?P<arm>\w+)_s(?P<seed>[01]) (?P<models>\S+) (?P<seconds>\d+)$')


def bundle_line(line):
    """A base line as a bundle line: ident source value, arm dagb -> bundle, dagbf -> bundlef."""
    m = LINE.match(line)
    assert m and m['arm'] in ('dagb', 'dagbf'), line
    head = m['head'].replace('ARCLOG_IDENT_SOURCE=type', 'ARCLOG_IDENT_SOURCE=value')
    arm = {'dagb': 'bundle', 'dagbf': 'bundlef'}[m['arm']]
    return '%s./run3600.sh %s %s_s%s %s %s' % (head, m['task'], arm, m['seed'], m['models'], m['seconds'])


def main():
    base, out = open(sys.argv[1]).read().split('\n'), sys.argv[2]
    base = [x for x in base if x.strip()]
    ok = True

    def say(label, good, text=''):
        nonlocal ok
        ok = ok and good
        print('%-5s %s %s' % ('ok' if good else 'FAIL', label, text))
    bundle = [bundle_line(x) for x in base]
    stage2 = []
    for task in dict.fromkeys(LINE.match(x)['task'] for x in base):
        mine = [x for x in bundle if LINE.match(x)['task'] == task]
        for name in ('bundle', 'mt', 'depth'):
            for x in mine:
                if name == 'bundle':
                    stage2.append(x)
                else:
                    m = LINE.match(x)
                    arm = m['arm'].replace('bundle', name)
                    stage2.append('%s%s./run3600.sh %s %s_s%s %s %s' % (m['head'], NODE_SCORE % name, task, arm, m['seed'], m['models'], m['seconds']))
    stage1 = []
    for task, fold in (('135a2760', ''), ('74dd1130', 'f')):
        for x in bundle:
            m = LINE.match(x)
            if m['task'] == task:
                stage1.append('%s%s%s./run3600.sh %s parity%s_s%s %s 300' % (m['head'], NODE_SCORE % 'ship', CHECK, task, fold, m['seed'], m['models']))
    for name in ('mt', 'depth'):
        m = LINE.match(next(x for x in bundle if LINE.match(x)['task'] == '135a2760' and LINE.match(x)['seed'] == '0'))
        stage1.append('%s%s./run3600.sh 135a2760 %s_s0 %s 300' % (m['head'], NODE_SCORE % name, name, m['models']))
    for name, lines in zip(FILES, (stage1, stage2)):
        with open(os.path.join(out, name), 'w') as f:
            f.write('\n'.join(lines) + '\n')
    # checks
    tasks2 = [LINE.match(x)['task'] for x in stage2]
    say('stage 2 lines', len(stage2) == 300, '%d lines, %d tasks' % (len(stage2), len(set(tasks2))))
    say('6 lines per task, together', all(tasks2[i:i + 6] == [tasks2[i]] * 6 for i in range(0, 300, 6)) and len(set(tasks2)) == 50)
    say('task order is the base order', list(dict.fromkeys(tasks2)) == list(dict.fromkeys(LINE.match(x)['task'] for x in base)))
    ident = sum(' ARCLOG_IDENT_SOURCE=value ' in x for x in stage2 + stage1)
    say('ident source value on every line', ident == len(stage1) + len(stage2), '%d lines' % ident)
    # bundle lines against the base lines
    got = [x for x in stage2 if LINE.match(x)['arm'].startswith('bundle')]
    same = all(a.replace('ARCLOG_IDENT_SOURCE=value', 'ARCLOG_IDENT_SOURCE=type').replace(' bundlef_', ' dagbf_').replace(' bundle_', ' dagb_') == b for a, b in zip(got, base))
    say('bundle lines differ from the base only in value and the arm', len(got) == 100 and same, '%d lines' % len(got))
    # mt and depth lines against their bundle lines
    bad = 0
    for i in range(0, 300, 6):
        for k, name in ((2, 'mt'), (4, 'depth')):
            for s in (0, 1):
                a, b = stage2[i + s].split(), stage2[i + k + s].split()
                want = [t for t in b if t != NODE_SCORE.strip() % name]
                want = [t.replace(name, 'bundle', 1) if t.startswith(name) and t.endswith('_s%d' % s if s == 0 else '_s1') else t for t in want]
                bad += want != a
    say('mt and depth lines differ from their bundle lines only in NODE_SCORE and the arm', bad == 0, '%d lines differ otherwise' % bad)
    arms = sorted({LINE.match(x)['arm'] + '_s' + LINE.match(x)['seed'] for x in stage2})
    say('arms', len(arms) == 12, ' '.join(arms))
    say('stage 1 lines', len(stage1) == 6 and all(LINE.match(x)['seconds'] == '300' for x in stage1), '%d lines' % len(stage1))
    print('PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
