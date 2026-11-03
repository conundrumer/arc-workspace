#!/usr/bin/env python
"""Adds the run's fields to manifest.json and keeps the fields it holds. Run after the final fit."""
import json
import os

D = os.path.dirname(os.path.abspath(__file__)) + '/'
m = json.load(open(D + 'manifest.json'))
keep = dict(m)
f = json.load(open(D + 'final.json'))
m.update(
    command='features_walk_held.sh, features_walk_part.sh, features_rel_crossfit.py, features_rel_data.py, features_rel_fit.py cv and final; the commands are in commands.txt',
    commit='118556b5f',
    task_set='fit: 849 train and 161 test tasks of corpus-v3mix without the 99 evaluation tasks, 26,237 valid-form picks; tune: task folds of the 161 test tasks; read: the 37 held tasks of held/tasks.txt, 431 valid RULE forms, 1,959 picks',
    budget='no search budget: teacher-forced walks; Mac, at most 4 processes',
    measures=['bits saved per relation pick against the steered prior, task bootstrap 95%', 'by class of gold relation and atom position', 'content features CPU per pick', 'fit sample count', 'control on a label drawn from the prior'],
    gold_revision='fit: corpus-v3mix, gold-v3-drift-regold-ba59a0ab1 as its rows manifests give it; read: gold-v3-helper-forms-a036da074 base view, the census forms',
    wheel_engine=dict(path='ast/run/runtime-ba0754492/py313-path', so_sha256='4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371', commit='ba0754492', machine='Mac'),
    steers='relR7 steer as kits/sampler-helper-pool-gold-v3-helper-forms-a036da074/models-context/relR4_o.pkl, whose factors reproduce each census pick; the census walk read these weights on the held picks',
    training_eligibility='train and test tasks are outside held/leave_out.txt; steered weights on train tasks come from steer-fold*.pkl, each fit without the task fold; on test tasks from the steer in use, which was not fit on them',
    node_records='none: walks hold rows at gold picks, in walks/',
    tune=dict(fit_all_forms_1010_tasks=dict(no_content_300_trees_2_folds=.292, no_content_500_trees_1_fold=.322, content_300_trees_1_fold=.312, control_200_trees_1_fold=-.005),
              fit_test_tasks_200_trees=dict(rows_all_earlier_forms=.231, rows_parents=.348, rows_all_earlier_forms_no_reader_count=.149), content_with_rows_all_earlier_forms_200_trees=.240,
              steer_fold0_bits_test_rows=3.257, steer_in_use_bits_test_rows=3.305),
    content_cost=dict(ms_per_pick_mean=44.7, ms_per_pick_median_form=15.5, table_share_relation_options=.622, table_share_gold=.697, prefix_table_share_after_first_atom=.664),
    result=f,
)
for k, v in keep.items():
    if k in ('prediction', 'name', 'purpose', 'start'):
        assert m[k] == v
tmp = D + 'manifest.json.new'
json.dump(m, open(tmp, 'w'), indent=1)
os.replace(tmp, D + 'manifest.json')
