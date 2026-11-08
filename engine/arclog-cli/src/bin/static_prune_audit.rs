//! Native counterexample search for the static-pruning implementation arguments.
//! This command evaluates library relations, not a second arithmetic model.
use arclog::algebra::{algebra, geometry::Geometry};
use arclog::eval::instance::{ConstructionContext, GroupInputs};
use arclog::eval::join::Budget;
use arclog::eval::{Cancellation, Caps, Limits};
use arclog::program::FactRelation;
use arclog::registry::{LibName, Registry};
use arclog::relations::RowSet;
use arclog::session::{SessionBound, TaskSession};
use arclog::study::StudyProgram;
use arclog::terms::{Margins, Term, TermId};
use arclog::types::ValueType;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::time::Instant;

#[derive(Default)]
struct ResultCount {
    cases: u64,
    stops: u64,
    errors: u64,
    failures: u64,
    examples: Vec<Value>,
}
#[derive(Default)]
struct Audit {
    counts: BTreeMap<String, ResultCount>,
}
fn rows(name: &str, bound: &[Option<TermId>]) -> Result<Vec<Vec<TermId>>, String> {
    let relation =
        algebra(&LibName(name.into())).ok_or_else(|| format!("no native algebra {name}"))?;
    let mut out = Vec::new();
    relation
        .evaluate(bound, Registry::get(), &mut |row| out.push(row.to_vec()))
        .map_err(|stop| format!("{stop:?}"))?;
    Ok(out)
}
impl Audit {
    fn check(
        &mut self,
        rule: &str,
        relation: &str,
        bound: Vec<Option<TermId>>,
        holds: impl FnOnce(&[Vec<TermId>]) -> bool,
    ) {
        let count = self.counts.entry(rule.into()).or_default();
        count.cases += 1;
        match rows(relation, &bound) {
            Err(error) if error.starts_with("no native algebra ") => {
                count.errors += 1;
                if count.examples.len() < 8 {
                    count.examples.push(json!({"error":error}));
                }
            }
            Err(_) => count.stops += 1,
            Ok(out) => {
                if holds(&out) {
                    return;
                }
                count.failures += 1;
                if count.examples.len() < 8 {
                    count.examples.push(json!({"relation":relation,
                        "bound":bound.iter().map(|v|v.map(TermId::fixed_encoding)).collect::<Vec<_>>(),
                        "rows":out.iter().map(|r|r.iter().map(|v|v.fixed_encoding()).collect::<Vec<_>>()).collect::<Vec<_>>() }));
                }
            }
        }
    }
    fn json(&self) -> Value {
        json!(
            self.counts
                .iter()
                .map(|(rule, c)| (
                    rule,
                    json!({"cases":c.cases,"stopped":c.stops,"errors":c.errors,
            "counterexamples":c.failures,"examples":c.examples})
                ))
                .collect::<BTreeMap<_, _>>()
        )
    }
}
fn zero() -> TermId {
    Term::Box(Margins {
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
    })
    .encode()
    .unwrap()
}
fn negative_distance() -> Value {
    let number = |n| Term::encode_number(n);
    let mut supplied = RowSet::empty(2);
    supplied.insert(vec![number(0), number(-1)].into());
    let inputs = vec![
        RowSet::empty(2),
        RowSet::empty(3),
        RowSet::empty(1),
        supplied,
    ];
    let types: Vec<Box<[ValueType]>> = [2, 3, 1, 2]
        .into_iter()
        .map(|width| vec![ValueType::Int; width].into())
        .collect();
    let session = TaskSession::new(
        SessionBound {
            bytes: 512 * 1024 * 1024,
        },
        Caps::CORPUS,
    );
    let limits = Limits::new(None, Cancellation::default());
    let mut budget = Budget::new(&limits, &session);
    let mut context = ConstructionContext {
        session: &session,
        registry: Registry::get(),
        budget: &mut budget,
    };
    let construction = arclog_constructions::shared()
        .unwrap()
        .get(&LibName("Distance".into()))
        .unwrap();
    match construction.evaluate(
        &GroupInputs {
            inputs: &inputs,
            types: &types,
            columns: &types,
            wanted: &[true, true],
        },
        &mut context,
    ) {
        Ok(result) => {
            json!({"rows":result.outputs[0].rows().map(|r|r.iter().map(|v|Term::decode_number(*v)).collect::<Vec<_>>()).collect::<Vec<_>>()})
        }
        Err(stop) => json!({"stopped":format!("{stop:?}")}),
    }
}
fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let option = |name: &str| {
        args.windows(2)
            .find(|p| p[0] == name)
            .map(|p| PathBuf::from(&p[1]))
            .ok_or_else(|| format!("missing {name}"))
    };
    let tasks = option("--tasks")?;
    let output = option("--output")?;
    let mut files: Vec<_> = std::fs::read_dir(tasks)
        .map_err(|e| e.to_string())?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.extension().is_some_and(|e| e == "json"))
        .collect();
    files.sort();
    let started = Instant::now();
    let mut positions = BTreeMap::new();
    let mut maximum = 0usize;
    for (i, path) in files.iter().enumerate() {
        let task =
            arclog::task::read_task(path).map_err(|e| format!("{}: {e:?}", path.display()))?;
        for fact in [FactRelation::ExInput, FactRelation::ExOutput] {
            let relation = task.fact_rows(fact, None);
            for part in relation.parts() {
                for row in part.rows.rows() {
                    positions.insert(row[1].fixed_encoding(), row[1]);
                }
            }
        }
        for example in task.examples() {
            let grid = task.input(example).rows();
            maximum = maximum.max(grid.len()).max(grid[0].len());
        }
        if (i + 1) % 100 == 0 || i + 1 == files.len() {
            println!(
                "{}",
                json!({"stage":"task_domains","done":i+1,"total":files.len(),"positions":positions.len(),"elapsed":started.elapsed().as_secs_f64()})
            );
        }
    }
    let geometry = Geometry::get();
    let mut audit = Audit::default();
    for (relation, ty) in [
        ("opposite", ValueType::Dir),
        ("diag_opposite", ValueType::DiagDir),
        ("dir8_opposite", ValueType::Dir8),
        ("perp", ValueType::Axis),
        ("diag_perp", ValueType::DiagAxis),
        ("perp_dir", ValueType::Dir),
    ] {
        for &v in geometry.domain(&ty) {
            audit.check(
                &format!("unsatisfiable.{relation}.same"),
                relation,
                vec![Some(v), Some(v)],
                |r| r.is_empty(),
            );
        }
    }
    for &sense in geometry.domain(&ValueType::Sense) {
        for &dir in geometry.domain(&ValueType::Dir) {
            audit.check(
                "unsatisfiable.turn.same",
                "turn",
                vec![Some(sense), Some(dir), Some(dir)],
                |r| r.is_empty(),
            );
        }
    }
    let memberships = [
        ("dir_elem", ValueType::Dir),
        ("diag_dir_elem", ValueType::DiagDir),
        ("dir8_elem", ValueType::Dir8),
        ("axis_elem", ValueType::Axis),
        ("diag_axis_elem", ValueType::DiagAxis),
        ("axis4_elem", ValueType::Axis4),
        ("d4_elem", ValueType::D4),
        ("c4_elem", ValueType::C4),
        ("sense_elem", ValueType::Sense),
        ("sym_elem", ValueType::Sym),
    ];
    for (name, tested) in &memberships {
        let target = geometry.domain(tested);
        for (_, bound_type) in &memberships {
            let source = geometry.domain(bound_type);
            let subset = source.iter().all(|v| target.contains(v));
            let disjoint = source.iter().all(|v| !target.contains(v));
            if subset || disjoint {
                for &v in source {
                    audit.check(
                        &format!("membership.{bound_type:?}.{name}"),
                        name,
                        vec![Some(v)],
                        |r| if subset { r.len() == 1 } else { r.is_empty() },
                    );
                }
            }
        }
    }
    let total = positions.len();
    for (i, &p) in positions.values().enumerate() {
        for relation in ["inside", "interior"] {
            audit.check(
                &format!("repeat.{relation}"),
                relation,
                vec![Some(p), Some(p)],
                |r| {
                    if relation == "inside" {
                        r.len() == 1
                    } else {
                        r.is_empty()
                    }
                },
            );
        }
        for (relation, ty) in [
            ("same_dist", ValueType::Dir),
            ("same_line", ValueType::Axis4),
            ("same_corner", ValueType::DiagDir),
            ("same_slab", ValueType::Dir),
            ("nearer", ValueType::Dir8),
            ("gap", ValueType::Dir8),
        ] {
            for &d in geometry.domain(&ty) {
                let mut bound = vec![Some(d), Some(p), Some(p)];
                if relation == "gap" {
                    bound.push(None);
                }
                audit.check(&format!("repeat.{relation}"), relation, bound, |r| {
                    if matches!(relation, "nearer" | "gap") {
                        r.is_empty()
                    } else {
                        r.len() == 1
                    }
                });
            }
        }
        for &d in geometry.domain(&ValueType::Dir8) {
            audit.check(
                "unsatisfiable.neighbor.same",
                "neighbor",
                vec![Some(p), Some(d), Some(p)],
                |r| r.is_empty(),
            );
            audit.check(
                "alias.jump.zero",
                "jump",
                vec![Some(p), Some(d), Some(Term::encode_number(0)), None],
                |r| r.len() == 1 && r[0][3] == p,
            );
        }
        audit.check(
            "alias.compose.right_zero",
            "compose",
            vec![Some(p), Some(zero()), None],
            |r| r.len() == 1 && r[0][2] == p,
        );
        audit.check(
            "alias.compose.left_zero",
            "compose",
            vec![Some(zero()), Some(p), None],
            |r| r.len() == 1 && r[0][2] == p,
        );
        audit.check(
            "alias.relative.zero_base",
            "relative",
            vec![Some(zero()), Some(p), None],
            |r| r.len() == 1 && r[0][2] == p,
        );
        audit.check(
            "constant.relative.same",
            "relative",
            vec![Some(p), Some(p), None],
            |r| r.len() == 1 && r[0][2] == zero(),
        );
        if (i + 1) % 10000 == 0 || i + 1 == total {
            println!(
                "{}",
                json!({"stage":"position_laws","done":i+1,"total":total,"elapsed":started.elapsed().as_secs_f64()})
            );
        }
    }
    for (relation, ty) in [
        ("edge_inset", ValueType::Dir),
        ("edge_outset", ValueType::Dir),
        ("corner_inset", ValueType::DiagDir),
        ("corner_outset", ValueType::DiagDir),
        ("jump_offset", ValueType::Dir8),
    ] {
        for &d in geometry.domain(&ty) {
            audit.check(
                &format!("constant.{relation}.zero"),
                relation,
                vec![Some(d), Some(Term::encode_number(0)), None],
                |r| r.len() == 1 && r[0][2] == zero(),
            );
        }
    }
    for relation in ["uniform_inset", "uniform_outset"] {
        audit.check(
            &format!("constant.{relation}.zero"),
            relation,
            vec![Some(Term::encode_number(0)), None],
            |r| r.len() == 1 && r[0][1] == zero(),
        );
    }
    for &d in geometry.domain(&ValueType::Dir) {
        for relation in ["axis_inset", "axis_outset"] {
            audit.check(
                &format!("constant.{relation}.zero"),
                relation,
                vec![
                    Some(d),
                    Some(Term::encode_number(0)),
                    Some(Term::encode_number(0)),
                    None,
                ],
                |r| r.len() == 1 && r[0][3] == zero(),
            );
        }
    }
    let max = i32::try_from(maximum).map_err(|e| e.to_string())?;
    for t in -max..=max {
        for side in -max..=max {
            for gap in -max..=max {
                audit.check(
                    "numeric.divide.nonnegative_columns",
                    "divide",
                    vec![
                        Some(Term::encode_number(t)),
                        Some(Term::encode_number(side)),
                        Some(Term::encode_number(gap)),
                        None,
                        None,
                    ],
                    |r| {
                        r.iter().all(|row| {
                            [0, 1, 3, 4]
                                .into_iter()
                                .all(|column| Term::decode_number(row[column]) >= 0)
                        })
                    },
                );
            }
        }
        for gap in -max..=max {
            audit.check(
                "unsatisfiable.divide.zero_side",
                "divide",
                vec![
                    Some(Term::encode_number(t)),
                    Some(Term::encode_number(0)),
                    Some(Term::encode_number(gap)),
                    None,
                    None,
                ],
                |r| r.is_empty(),
            );
        }
    }
    let inset = rows("uniform_inset", &[Some(Term::encode_number(1)), None])?[0][1];
    let box_extent = rows(
        "box_extent",
        &[
            Some(inset),
            Some(zero()),
            Some(geometry.domain(&ValueType::Axis)[0]),
            None,
        ],
    )?;
    let position_probe = "(RULE &ints NumberDomain) (RULE &probe (&ints (:N *K)) (uniform_outset (:K K) (:B *P)) (frame_extent (:P P) (:A *A) (:N *N))) (OUT (input ^P ^Col))";
    let checked = StudyProgram::from_sexp(position_probe, Registry::get())
        .map(|_| "accepted".to_string())
        .unwrap_or_else(|e| e);
    let failed = audit
        .counts
        .values()
        .any(|c| c.failures != 0 || c.errors != 0);
    let result = json!({"schema":"arclog-static-prune-law-audit-v1","tasks":files.len(),"positions":total,
        "coverage_complete":false,"uncovered":["derived Box/Offset domains beyond task fact Positions","all narrowed construction/proposer numeric outputs","native checked prefix and replacement admission"],
        "numeric_input_interval":[-max,max],"rules":audit.json(),"elapsed_seconds":started.elapsed().as_secs_f64(),
        "dropped_spec_counterexamples":{"box_extent_N":box_extent.iter().map(|r|Term::decode_number(r[3])).collect::<Vec<_>>(),
            "generic_Distance_K":negative_distance()},"position_type_probe":{"program":position_probe,"checker":checked},
        "scope":"native algebra evaluations over task fact positions and finite orientation domains; no corpus mutation or static pruning enabled"});
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::write(
        &output,
        serde_json::to_vec_pretty(&result).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    println!(
        "{}",
        json!({"stage":"complete","output":output,"elapsed":started.elapsed().as_secs_f64()})
    );
    if failed {
        return Err("native law audit found counterexamples or unsupported relation errors; inspect the saved report".into());
    }
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(1)
    }
}
