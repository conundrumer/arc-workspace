//! A check that tracks this crate while it is in progress: each worked
//! expansion of `work/feature-spec/feature-spec.md#worked-expansions` gives its
//! stated value through the expander. It prints each case that fails.

use std::path::Path;

use crate::run::{cell_text, concept_program, Evaluated, Host, ModelValue, Value};

/// What a case states.
pub enum Expect {
    /// The rows at each example, in the order of the train examples, then the test input.
    Rows(&'static [usize]),
    /// The one number at each example.
    Numbers(&'static [i64]),
    /// The rows of a task-wide relation.
    TaskRows(usize),
    /// The rows of a task-wide relation with each named column's cells, as text.
    TaskCells(&'static [&'static str], &'static [&'static str]),
    /// The cells at the first example, with each named column's text, as a set.
    FirstCells(&'static [&'static str], &'static [&'static str]),
    Refused,
    Fault,
}

pub struct Case {
    pub solver: &'static str,
    /// Forms that the case adds to the state.
    pub state: &'static str,
    pub term: &'static str,
    /// Whether the term is a relation, read apart from a root.
    pub relation: bool,
    pub task_wide: bool,
    pub columns: &'static [&'static str],
    pub expect: Expect,
}

const fn rel(solver: &'static str, term: &'static str, expect: Expect) -> Case {
    Case { solver, state: "", term, relation: true, task_wide: false, columns: &[], expect }
}
const fn feature(solver: &'static str, term: &'static str, expect: Expect) -> Case {
    Case { solver, state: "", term, relation: false, task_wide: false, columns: &[], expect }
}
const fn wide(solver: &'static str, term: &'static str, expect: Expect) -> Case {
    Case { solver, state: "", term, relation: true, task_wide: true, columns: &[], expect }
}
const fn named(solver: &'static str, term: &'static str, columns: &'static [&'static str], expect: Expect) -> Case {
    Case { solver, state: "", term, relation: true, task_wide: false, columns, expect }
}

macro_rules! text {
    ($($part:expr),+ $(,)?) => { concat!($($part),+) };
}

macro_rules! sizes { () => { "(component Cardinality (member &ink (Col) (P)) size)" } }
macro_rules! marks { () => { "(join (project &rays.ray Origin) input (Origin P))" } }
macro_rules! pairs { () => { "(join (lib-join (join (project input P) d4_elem) apply (D D) (P P)) (project input P) (P_out P))" } }
macro_rules! cells { () => { "(component Connectivity (node &ink (Col) (P)) component)" } }
macro_rules! boxes { () => { text!("(component BoundingBox (cell ", cells!(), " (Id) (P)) box)") } }
macro_rules! rel_ { () => { text!("(lib-join (join ", cells!(), " ", boxes!(), " (Id Id)) relative (Base B) (X P))") } }
macro_rules! equal_ { () => { text!("(component Inclusion (pattern ", rel_!(), " () (Id X_rel)) (observed ", rel_!(), " () (Id X_rel)) equal)") } }
macro_rules! class_ { () => { text!("(component Quotient (equivalent ", equal_!(), " () (Id Id_2)) class)") } }
macro_rules! pool_ { () => { "(pool ?x &output Color (component Cardinality (member (project &output ?x) () (?x)) size))" } }
macro_rules! order_of { ($pool:expr) => { text!("(component Order (member (project ", $pool, " N) () (N)) (score (project ", $pool, " N) () (N N)) maximal)") } }

const TWO: &str = "(INIT &a Connectivity (node (P) (&ink *P)))\n(INIT &b Connectivity (key ((&ink ^Col)) (node (P) (&ink Col *P))))\n(RULE &two (&a.component *P *Id) (&b.component (:key *Col) P (:Id *Id_2)))";

/// Each worked expansion.
pub const CASES: &[Case] = &[
    feature("25d487eb", "(cardinality (project &ink Col))", Expect::Numbers(&[2, 2, 2, 2])),
    feature("25d487eb", "(cardinality &ink)", Expect::Numbers(&[9, 16, 9, 16])),
    rel("25d487eb", "(join &mark input (P P))", Expect::Rows(&[1, 1, 1, 1])),
    rel("25d487eb", "(join-label &mark P input)", Expect::Rows(&[1, 1, 1, 1])),
    named("25d487eb", "(join (join &ink input (P P)) input (P P))", &["P", "Col", "Col_2", "Col_3"], Expect::Rows(&[9, 16, 9, 16])),
    named("25d487eb", "(join-label (join-label &ink P input) P input)", &["P", "Col", "Col_2", "Col_3"], Expect::Rows(&[9, 16, 9, 16])),
    rel("25d487eb", "(join &rays.ray input (Origin P))", Expect::Rows(&[12, 9, 13, 15])),
    rel("25d487eb", "(join-label &rays.ray Origin input)", Expect::Rows(&[12, 9, 13, 15])),
    named("25d487eb", "(join (component Cardinality (member &ink (P) (Col)) size) input (P P))", &["P", "N", "Col"], Expect::Rows(&[9, 16, 9, 16])),
    named("25d487eb", "(join-label (group-sizes &ink P) P input)", &["P", "N", "Col"], Expect::Rows(&[9, 16, 9, 16])),
    rel("25d487eb", "(lib-join &mark margin (B P))", Expect::Rows(&[4, 4, 4, 4])),
    rel("25d487eb", "(select (lib-join (project &ink P) dist_pair (P P)) K = K2)", Expect::Rows(&[0, 0, 0, 6])),
    rel("25d487eb", "(select (lib-join (project &ink P) dist_pair (P P)) K > K2)", Expect::Rows(&[18, 32, 18, 29])),
    rel("25d487eb", "(select &rays.ray K = 0)", Expect::Rows(&[1, 1, 1, 1])),
    feature("25d487eb", "(cardinality (component Singleton (member &ink (P) (Col)) plural))", Expect::Numbers(&[0, 0, 0, 0])),
    named("25d487eb", "(component Singleton (member (join &mark input (P P)) (Col) (P Col_2)) value)", &["Col", "P", "Col_2"], Expect::Rows(&[1, 1, 1, 1])),
    named("25d487eb", text!("(component Cardinality (member ", sizes!(), " (N) (Col)) size)"), &["N", "N_2"], Expect::FirstCells(&["N", "N_2"], &["1 1", "8 1"])),
    named("25d487eb", "(group-sizes (group-sizes &ink Col) N)", &["N", "N_2"], Expect::FirstCells(&["N", "N_2"], &["1 1", "8 1"])),
    rel("25d487eb", order_of!(sizes!()), Expect::FirstCells(&["N"], &["8"])),
    rel("25d487eb", "(component Cardinality (member (project &ink Col) (Col) ()) size)", Expect::FirstCells(&["Col", "N"], &["c1 1", "c2 1"])),
    rel("25d487eb", "(component Cardinality (member &body_count.size (N) (Col)) size)", Expect::FirstCells(&["N", "N_2"], &["1 1", "8 1"])),
    rel("25d487eb", "(component Cardinality (member &mark (Col) (P)) (domain &ink (Col)) size)", Expect::FirstCells(&["Col", "N"], &["c1 1", "c2 0"])),
    rel("25d487eb", text!("(component Excess (plus &ink () (P Col)) (minus ", marks!(), " () (Origin Col)) excess)"), Expect::Numbers(&[8, 15, 8, 15])),
    feature("25d487eb", "(cardinality-ratio &mark &ink)", Expect::FirstCells(&["N", "N_2"], &["1 9"])),
    named("25d487eb", "(component Connectivity (node &ink (Col) (P)) (step step_offset () (V)) component)", &["Col", "P", "Id"], Expect::Rows(&[9, 16, 9, 16])),
    feature("25d487eb", text!("(cardinality (project (component Quotient (equivalent ", pairs!(), " () (P P_out)) class) Id))"), Expect::Numbers(&[40, 21, 48, 48])),
    feature("0d3d703e", text!("(cardinality (project (component Quotient (equivalent ", pairs!(), " () (P P_out)) class) Id))"), Expect::Numbers(&[3, 3, 3, 3, 3])),
    feature("25d487eb", text!("(cardinality (project ", class_!(), " Id_2))"), Expect::Numbers(&[2, 2, 2, 2])),
    rel("25d487eb", "(select (join &beam ex_output (E E) (P P)) Col != Col_2)", Expect::TaskRows(0)),
    rel("25d487eb", "(join &beam ex_output (E E) (P P))", Expect::TaskRows(24)),
    feature("25d487eb", "(cardinality (join &beam output (P P)))", Expect::Numbers(&[9, 5, 10, 0])),
    named("0d3d703e", "(join ex_input ex_output (P P))", &["E", "P", "Col", "E_2", "Col_2"], Expect::TaskRows(180)),
    rel("0d3d703e", "(join ex_input ex_output (E E) (P P))", Expect::TaskRows(36)),
    rel("0d3d703e", "(join-label &output P ex_output)", Expect::TaskRows(36)),
    rel("25d487eb", "(antijoin &beam ex_output (E E) (P P) (Col Col))", Expect::TaskCells(&["E"], &["e3"])),
    wide("25d487eb", "(component Cardinality (member &ink (E) (P Col)) size)", Expect::TaskCells(&["E", "N"], &["e0 9", "e1 16", "e2 9", "e3 16"])),
    wide("25d487eb", "(component Cardinality (member &ink () (Col)) size)", Expect::TaskCells(&["N"], &["5"])),
    Case { solver: "25d487eb", state: "(RULE &x (&ink *P (:Col *E)))", term: "(project &x E P E_2)", relation: true, task_wide: true, columns: &["E", "P", "E_2"], expect: Expect::TaskRows(50) },
    rel("a6953f00", "&corner", Expect::Rows(&[1; 32])),
    wide("a6953f00", "(project &corner D)", Expect::Fault),
    named("25d487eb", pool_!(), &["C", "N"], Expect::Rows(&[2, 2, 2, 2])),
    rel("25d487eb", order_of!(pool_!()), Expect::Numbers(&[3, 3, 3, 3])),
    feature("25d487eb", text!("(cardinality ", pool_!(), ")"), Expect::Numbers(&[2, 2, 2, 2])),
    feature("25d487eb", "(cardinality (pool ?x &ink Offset (component Cardinality (member (project &ink ?x) () (?x)) size)))", Expect::Numbers(&[0, 0, 0, 0])),
    rel("25d487eb", order_of!("(pool ?x &ink Offset (component Cardinality (member (project &ink ?x) () (?x)) size))"), Expect::Rows(&[0, 0, 0, 0])),
    feature("009d5c81", "(cardinality SharedColor)", Expect::TaskCells(&["N"], &["3"])),
    feature("070dd51e", "(value-set RarestColor C)", Expect::TaskCells(&["C"], &["c3", "c8"])),
    rel("25d487eb", "(join &ink ChangedPairs (Col C_to))", Expect::TaskRows(19)),
    Case { solver: "25d487eb", state: TWO, term: "(pool ?x &two Ident (project &two ?x))", relation: true, task_wide: false, columns: &[], expect: Expect::Refused },
    Case { solver: "25d487eb", state: TWO, term: "(pool ?x &two Ident (component Cardinality (member (project &two ?x) () (?x)) size))", relation: true, task_wide: false, columns: &[], expect: Expect::FirstCells(&["N"], &["1", "2"]) },
    Case { solver: "150deff5", state: "(RULE &poses (&piece.member (:Pose *Pz)))", term: "(value-set &poses Pz)", relation: false, task_wide: false, columns: &[], expect: Expect::Refused },
];

fn numbers(value: &Value) -> Vec<Vec<usize>> {
    let mut out = Vec::new();
    for at in &value.at {
        for (_, models) in &at.examples {
            for model in models {
                if let ModelValue::Rows(rows) = model {
                    out.push(vec![rows.len()]);
                } else {
                    out.push(vec![usize::MAX]);
                }
            }
        }
    }
    out
}

/// The row texts at the columns `names`, as a set, over one list of models.
fn cells(value: &Value, names: &[&str], models: &[ModelValue]) -> Vec<String> {
    let positions: Vec<Option<usize>> = names.iter().map(|name| value.row_names.iter().position(|held| held == name)).collect();
    let mut out = Vec::new();
    for model in models {
        let ModelValue::Rows(rows) = model else { continue };
        for row in rows {
            let texts: Vec<String> = positions.iter().map(|at| at.map_or("?".to_string(), |at| cell_text(row[at], &value.types[at]))).collect();
            out.push(texts.join(" "));
        }
    }
    out.sort();
    out.dedup();
    out
}

fn check_value(case: &Case, value: &Value) -> Result<(), String> {
    for name in case.columns {
        if !value.row_names.iter().any(|held| held == name) {
            return Err(format!("no column {name}: {:?}", value.row_names));
        }
    }
    if !case.columns.is_empty() && value.row_names.len() != case.columns.len() {
        return Err(format!("the columns are {:?}", value.row_names));
    }
    let at = value.at.first().ok_or("no assignment")?;
    match &case.expect {
        Expect::Rows(counts) => {
            let found: Vec<usize> = numbers(value).into_iter().flatten().collect();
            if found != *counts { return Err(format!("rows {found:?}")); }
        }
        Expect::Numbers(expected) => {
            let mut found = Vec::new();
            for (_, models) in &at.examples {
                for model in models {
                    match model {
                        ModelValue::Rows(rows) if rows.len() == 1 && rows[0].len() == 1 => found.push(arclog::terms::Term::decode_number(rows[0][0]) as i64),
                        other => return Err(format!("no number: {other:?}")),
                    }
                }
            }
            if found != *expected { return Err(format!("numbers {found:?}")); }
        }
        Expect::TaskRows(count) => {
            let found = numbers(value);
            if found != [vec![*count]] { return Err(format!("rows {found:?}")); }
        }
        Expect::TaskCells(names, expected) => {
            let found = cells(value, names, &at.examples[0].1);
            let mut wanted: Vec<String> = expected.iter().map(|text| text.to_string()).collect();
            wanted.sort();
            if found != wanted { return Err(format!("cells {found:?}")); }
        }
        Expect::FirstCells(names, expected) => {
            let found = cells(value, names, &at.examples[0].1);
            let mut wanted: Vec<String> = expected.iter().map(|text| text.to_string()).collect();
            wanted.sort();
            if found != wanted { return Err(format!("cells {found:?}")); }
        }
        Expect::Refused | Expect::Fault => return Err("a value".to_string()),
    }
    Ok(())
}

/// Runs each case, printing each that fails, and gives the counts that pass and
/// fail.
pub fn run(corpus: &Path, tasks: &Path) -> (usize, usize) {
    let (mut passed, mut failed) = (0, 0);
    for case in CASES {
        let outcome: Result<(), String> = (|| {
            let program = concept_program(corpus, case.solver)?;
            let program = match program.rfind("(OUT") {
                Some(at) if !case.state.is_empty() => format!("{}\n{}\n{}", &program[..at], case.state, &program[at..]),
                _ => program,
            };
            let host = Host::new(&program, &tasks.join(format!("{}.json", case.solver)))?;
            let evaluated = if case.relation { host.relation(case.term, case.task_wide) } else { host.feature(case.term) };
            match (&case.expect, evaluated) {
                (Expect::Refused, Evaluated::Refused(_)) | (Expect::Fault, Evaluated::Fault(_)) => Ok(()),
                (_, Evaluated::Refused(message)) => Err(format!("refused: {message}")),
                (_, Evaluated::Fault(message)) => Err(format!("fault: {message}")),
                (_, Evaluated::Value(value)) => check_value(case, &value),
            }
        })();
        match outcome {
            Ok(()) => passed += 1,
            Err(message) => {
                failed += 1;
                println!("FAIL {} {}\n  {message}", case.solver, case.term);
            }
        }
    }
    (passed, failed)
}
