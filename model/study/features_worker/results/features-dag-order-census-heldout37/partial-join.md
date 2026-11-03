# DAG order census: partial

Revision gold-v3-helper-forms-a036da074-base, mode join. 23664 rows of form and arm, over 2448 forms of scope and 431 forms in the relation pick read. This file is rewritten by features_dag_census_read.py, and part3.json holds the same numbers.

Written rows against census-base: ({'equal': 1626, 'either has no figure': 6, 'one has no figure': 2}, [('269e22fb', 5, 'before', None, 85.11), ('269e22fb', 5, 'parents', None, 85.22)])

Written order, RULE, parents: 431 forms, 37 tasks, 1959 picks, 1761 picks where gold is alive.

## random topological orders, scope and body

390 forms, 37 tasks, 2598 orders kept, 22 orders refused.

- Bits per gold-alive pick: written 3.062 (2.906 to 3.218), orders 3.349 (3.200 to 3.483).
- Written minus orders: -0.286 (-0.372 to -0.195). As a share of written: -0.093 (-0.124 to -0.062).
- All picks: written 3.196 (3.043 to 3.343), orders 3.464 (3.313 to 3.607), written minus orders -0.268 (-0.327 to -0.203).
- At the picks alive in written order: orders 3.359 (3.210 to 3.496), written minus orders -0.297 (-0.359 to -0.231).

## random topological orders, body only

390 forms, 37 tasks, 2598 orders kept, 22 orders refused.

- Bits per gold-alive pick: written 3.062 (2.906 to 3.218), orders 3.349 (3.200 to 3.483).
- Written minus orders: -0.286 (-0.372 to -0.195). As a share of written: -0.093 (-0.124 to -0.062).
- All picks: written 3.196 (3.043 to 3.343), orders 3.464 (3.313 to 3.607), written minus orders -0.268 (-0.327 to -0.203).
- At the picks alive in written order: orders 3.359 (3.210 to 3.496), written minus orders -0.297 (-0.359 to -0.231).

## canonical order, scope and body

407 forms, 37 tasks, 407 orders kept, 3 orders refused.

- Bits per gold-alive pick: written 3.082 (2.911 to 3.250), orders 3.271 (3.130 to 3.411).
- Written minus orders: -0.189 (-0.282 to -0.096). As a share of written: -0.061 (-0.095 to -0.030).
- All picks: written 3.204 (3.043 to 3.361), orders 3.385 (3.246 to 3.520), written minus orders -0.181 (-0.263 to -0.102).
- At the picks alive in written order: orders 3.281 (3.133 to 3.425), written minus orders -0.199 (-0.275 to -0.129).

## Form totals

| kind and scope | forms | written | random mean | canonical | forms with written at or under the random mean |
|---|---|---|---|---|---|
| DET nondesc | 112 | 17.09 | 17.78 | 17.39 | 89 |
| DET parents | 112 | 14.8 | 15.69 | 15.34 | 100 |
| INIT nondesc | 248 | 37.4 | 39.61 | 36.16 | 196 |
| INIT parents | 248 | 32.75 | 35.11 | 31.88 | 221 |
| RULE nondesc | 390 | 32.93 | 35.99 | 35.29 | 316 |
| RULE parents | 390 | 30.36 | 33.5 | 32.95 | 324 |

## Orders refused

[
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(5), PathSt",
323
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(8), PathSt",
268
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(7), PathSt",
251
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(9), PathSt",
239
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(4), PathSt",
217
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(6), PathSt",
194
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(11), PathS",
174
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(16), PathS",
165
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(15), PathS",
146
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(10), PathS",
141
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(0), PathSt",
139
],
[
"dead: Dead: try:construct:atom cannot close",
133
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(17), PathS",
127
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(13), PathS",
124
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(3), PathSt",
120
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(18), PathS",
117
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(1), PathSt",
111
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(12), PathS",
104
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(24), PathS",
97
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(20), PathS",
91
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(22), PathS",
90
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(2), PathSt",
90
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(19), PathS",
73
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(21), PathS",
62
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(23), PathS",
51
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(25), PathS",
45
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(14), PathS",
44
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(28), PathS",
42
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(27), PathS",
39
],
[
"error: ValueError: Check(Safety) at Path(NodePath([PathStep(29), PathS",
35
]
]
