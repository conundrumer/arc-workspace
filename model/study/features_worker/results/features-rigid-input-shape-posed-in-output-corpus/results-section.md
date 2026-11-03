Whether a shape in a train input that reappears in a train output at another D4 pose says a task has a rigid assembly. The statistic reads train inputs, train outputs and test inputs. A task is positive where a case of its gold file, revision `gold-v3-rigid-round50`, has a `RIGID_DET` form. The non-held tasks hold 10 positive tasks with several poses, 9 of them with the form in the smallest case, and 8 with one pose, 5 of them with the form in the smallest case and 5 added at round 50. The 99 tasks of `held/leave_out.txt` are left out of the non-held read: its 37 held tasks are read once, for 4 forms, and the other 62, with 2 positive tasks among them, are not read. The 20 evaluation tasks outside that list are plain tasks. 45 plain tasks whose output is or holds a D4 image of the whole input are set apart, and no positive task is among them. That leaves 978 plain tasks and a base rate of 1.0%. The base form is a single-color 8-connected component of at least 4 cells and at least 4 D4 images, colors kept, that the output of its pair holds at a pose the pair's input lacks. Each other row changes what its name says. AUC is positive against plain, at the highest of the boolean and three graded scores: share of pairs, largest shape, and classes hit over classes copied. Intervals are from a task bootstrap, and a resample with no bar counts as 0 bits. At 0 positive hits the interval has no width on the positive side: 0 of 10 allows a true rate up to .31. The control replaces each train output with an output of another plain task of the same size, 95% of them exact, mean of 5 draws. The sweep of all 2,808 form combinations is a maximum over that grid: random labels give a higher best boolean AUC on 64% of 2,000 draws, with a median of .656. On all 18 positive tasks, for single-color and multi-color components of at least 3 cells and 2 images with colors free, no train output has a component at a pose that the task's inputs lack. Of the 45 plain hits of the base form, 17 have same-size grids and also a copy of the shape at an input pose (6855a6e4, 845d6e51), 12 have same-size grids and an output with a symmetry the input lacks (b8825c91, 981571dc), 11 have an output smaller than the input (e78887d1, 0934a4d8), 2 have an output larger than the input (3cd86f4f), and 3 are others (0e206a2e). The gold of 23 of those 45 uses a D4 relation, against 7.6% of plain tasks. Of the tasks set apart, 6 hit the base form. The held rows hold 2 positive and 35 plain tasks, with the score of the non-held read. At the bars of the non-held read, on 1 of 2 positive tasks each, tight windows give -0.11 bits, and the best of the grid gives .40 bits at recall .5 and 1.21 at the best bar. Cost is 4.3 ms median and 83 ms at most per task for all forms in Python on the Mac, most of it tight windows. Run: `work/lm/data-study/features-worker/results/features-rigid-input-shape-posed-in-output-corpus`.

| Form | Positive, of 10 | One pose, of 8 | Looks posed, of 3 | Plain, of 978 | Same pose, positive and plain | AUC, 95% interval | Bits at recall .5 | Bits, best bar at recall .3 | Control, positive and plain | Held: positive of 2, plain of 35 |
|---|---|---|---|---|---|---|---|---|---|---|
| Base form | 0 | 0 | 1 | 45 | 3, 296 | .477 (.470 to .483) | no bar | no bar | 0, .003 | 0, 2; AUC .471; control 0, .011 |
| 4-connected | 0 | 0 | 1 | 46 | 2, 266 | .476 (.470 to .483) | no bar | no bar | 0, .002 |  |
| Multi-color component | 0 | 0 | 1 | 20 | 1, 161 | .490 (.485 to .494) | no bar | no bar | 0, <.001 |  |
| All cells of one color | 0 | 0 | 0 | 9 | 2, 183 | .495 (.492 to .498) | no bar | no bar | 0, 0 |  |
| Tight window | 3 | 1 | 1 | 314 | 3, 477 | .498 (.343 to .651) | no bar | .23 (.00 to 3.26) | .020, .039 | 2, 25; AUC .500; control .100, .080 |
| Colors free | 0 | 0 | 1 | 63 | 4, 332 | .468 (.460 to .475) | no bar | no bar | 0, .016 |  |
| Cells anywhere in the output | 0 | 1 | 1 | 206 | 3, 395 | .395 (.382 to .408) | no bar | no bar | .260, .159 |  |
| Copy in changed cells | 0 | 0 | 1 | 36 | 2, 104 | .482 (.475 to .487) | no bar | no bar | 0, .002 |  |
| Source in another pair | 0 | 0 | 0 | 40 | 2, 45 | .480 (.473 to .485) | no bar | no bar | 0, .003 |  |
| Pose in no input of the task | 0 | 0 | 1 | 46 | 3, 297 | .476 (.470 to .483) | no bar | no bar | 0, .006 |  |
| At least 2 poses in the pair | 1 | 0 | 1 | 81 | 3, 296 | .511 (.452 to .621) | no bar | no bar | 0, .003 |  |
| At least 3 poses in the pair | 0 | 0 | 0 | 28 | 3, 296 | .486 (.481 to .491) | no bar | no bar | 0, .001 |  |
| At least 3 cells | 0 | 0 | 1 | 55 | 3, 336 | .472 (.465 to .479) | no bar | no bar | 0, .007 |  |
| At least 6 cells | 0 | 0 | 0 | 33 | 2, 238 | .483 (.477 to .489) | no bar | no bar | 0, <.001 |  |
| At least 8 cells | 0 | 0 | 0 | 22 | 1, 187 | .489 (.484 to .493) | no bar | no bar | 0, <.001 |  |
| At least 2 images | 0 | 0 | 1 | 51 | 3, 406 | .474 (.467 to .481) | no bar | no bar | 0, .008 |  |
| 8 images | 0 | 0 | 0 | 26 | 2, 203 | .487 (.482 to .491) | no bar | no bar | 0, .001 |  |
| Multi-color, colors free | 0 | 0 | 1 | 18 | 4, 194 | .491 (.487 to .495) | no bar | no bar | 0, .004 |  |
| Multi-color, changed cells | 0 | 0 | 0 | 13 | 0, 37 | .493 (.490 to .496) | no bar | no bar | 0, <.001 |  |
| Colors free, changed cells | 0 | 0 | 1 | 48 | 3, 156 | .475 (.469 to .482) | no bar | no bar | 0, .014 |  |
| 2 poses, changed cells | 0 | 0 | 1 | 45 | 2, 104 | .477 (.470 to .484) | no bar | no bar | 0, .002 |  |
| Colors free, 2 poses, changed cells | 0 | 1 | 1 | 77 | 3, 156 | .461 (.452 to .469) | no bar | no bar | 0, .016 |  |
| Multi-color, 2 poses, changed cells | 0 | 0 | 0 | 15 | 0, 37 | .492 (.488 to .496) | no bar | no bar | 0, <.001 |  |
| 3 poses, colors free | 0 | 0 | 0 | 43 | 4, 332 | .478 (.471 to .485) | no bar | no bar | 0, .005 |  |
| At least 3 poses in the task | 1 | 0 | 0 | 42 | 3, 297 | .530 (.474 to .633) | no bar | no bar | 0, .003 | 0, 1; AUC .486; control 0, .011 |
| Source in another pair, colors free, changed cells | 0 | 0 | 0 | 32 | 2, 20 | .484 (.478 to .489) | no bar | no bar | 0, .018 |  |
| Cells anywhere, changed cells | 0 | 1 | 1 | 113 | 2, 179 | .442 (.433 to .452) | no bar | no bar | .240, .147 |  |
| Tight window, changed cells | 0 | 1 | 0 | 101 | 1, 161 | .448 (.438 to .458) | no bar | no bar | .020, .024 |  |
| Pose in no input of the task, colors free, changed cells | 0 | 0 | 1 | 58 | 3, 159 | .470 (.463 to .478) | no bar | no bar | 0, .032 |  |
| Best of the grid: tight window, colors free, 8 images, changed cells, source in another pair, 2 poses | 5 | 1 | 1 | 221 | 4, 142 | .645 (.490 to .812) | 1.23 (.00 to 3.06) | 2.06 (.00 to 3.06) | .480, .417 | 1, 14; AUC .600; control .800, .663 |

Call: no form is good enough to condition `RIGID_DET`'s prior. Exact components hit at most 2 of 10 positive tasks across the whole grid, tight windows hit 3 of 10 at the plain rate, and the form with the highest AUC stays at its control rate.
