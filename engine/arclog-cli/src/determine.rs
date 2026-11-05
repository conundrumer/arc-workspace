//! `determine`: determines the parameters of each solver given, or of every
//! solver of the corpus, from its task's evidence, on its base cases, and
//! compares each determined value with the solver's `param` rows, as
//! `docs/engine/determination.md#end-check` gives. It prints each
//! difference by solver and parameter, and each fault that keeps a case or
//! a parameter from its comparison, with its form, as that fault.
//!
//! Its arguments: the corpus directory, the directory of the task files,
//! then the task ids of the solvers to run; every solver of the corpus where
//! it is given none.

use std::cell::RefCell;
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::process::ExitCode;
use std::sync::{Arc, Mutex};

use arclog::algebra::geometry::Geometry;
use arclog::check::{CheckCache, CheckedProgram, SolverClauses};
use arclog::eval::determinations::{det_node, relation_spelled};
use arclog::eval::examples::{scope_of, ExampleScope};
use arclog::eval::join::{each_row, union};
use arclog::eval::rigid::image;
use arclog::eval::{output_relation, RelationValue, RunFault};
use arclog::hash::StableHashMap;
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, CorpusSolver, SolverResult};
use arclog::judge::candidates::World;
use arclog::judge::determination::{determine, CaseOutcome, DeterminedCase, Determination, Parameter};
use arclog::eval::instance::Constructions;
use arclog::eval::Limits;
use arclog::task::{JudgedTask, Task};
use arclog::program::{OutputOwner, ParamValue, ProgramRelation, RigidDetName};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::{resolve_cases, DependencyKind, GraphNodeIndex, Side};
use arclog::session::TaskSession;
use arclog::solver::{CaseName, Exclusion, Solver};
use arclog::terms::{Ident, Term, TermId};
use arclog::types::{GraphRelation, ValueType};

use arclog::stream::corpus::{case_spelled, check_case, check_cases};
use arclog::decode::corpus::{corpus_session, read_corpus_task, CorpusTask};
use crate::concept_case::{corpus_limits, determined_cases};
use arclog_constructions::shared as constructions;
use crate::renaming::{renaming_exists, same_without_idents, term_leaves, EngineLeaf, Leaf};
use crate::select::selected;

const USAGE: &str = "usage: arclog-cli determine <corpus-dir> <tasks-dir> [<task_id> ...]";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let [corpus, tasks, task_ids @ ..] = args else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let (corpus, tasks) = (PathBuf::from(corpus), PathBuf::from(tasks));
    let selected = selected(task_ids, &[], Path::new("")).expect("a selection by task id alone reads no file");
    let differing: Mutex<BTreeSet<String>> = Mutex::default();
    let report = run_over_corpus(&corpus, selected.as_ref(), |solver| determine_solver(&corpus, &tasks, solver, &differing), print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let differing = differing.into_inner().expect("a set that no panic poisoned").len();
    let determined = report.checked;
    let faulted = report.failures.len() - differing;
    println!("{differing} of {determined} solvers differ from their `param` records, and {faulted} others give a fault that keeps a case or a parameter from its comparison");
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// A line of the report on a solver.
pub(crate) enum Finding {
    /// A determined value that differs from its `param` record: the
    /// parameter as a line spells it, and the line.
    Difference { parameter: String, line: String },
    /// A fault that keeps a case or a parameter from its comparison.
    Fault(String),
}

impl Finding {
    /// The line of the finding.
    pub(crate) fn line(&self) -> &str {
        match self {
            Finding::Difference { line, .. } | Finding::Fault(line) => line,
        }
    }
}

/// The report on `solver`, which goes into `differing` where a determined
/// value differs from its record.
fn determine_solver(corpus: &Path, tasks: &Path, solver: &CorpusSolver, differing: &Mutex<BTreeSet<String>>) -> SolverResult {
    let findings = solver_determination(corpus, tasks, &solver.task_id).map_or_else(|fault| vec![Finding::Fault(fault)], |setup| setup.findings);
    if findings.iter().any(|finding| matches!(finding, Finding::Difference { .. })) {
        differing.lock().expect("a set that no panic poisoned").insert(solver.task_id.clone());
    }
    let lines: Vec<String> = findings.iter().map(|finding| finding.line().to_owned()).collect();
    if lines.is_empty() { SolverResult::Pass } else { SolverResult::Fail(lines) }
}

/// A solver's checked cases with the determination run on its base cases
/// and compared with the solver's `param` records.
pub(crate) struct SolverDetermination {
    pub(crate) task: Task,
    pub(crate) judged: JudgedTask,
    concept: CheckedProgram,
    /// The solver, which gives the departures of each of its cases from the
    /// concept case.
    pub(crate) solver: Arc<Solver>,
    /// Every case the `exclude` forms leave, checked once, in the order of
    /// `Solver::case_names`.
    programs: Vec<(CaseName, CheckedProgram)>,
    session: TaskSession,
    limits: Limits,
    constructions: &'static Constructions,
    pub(crate) determination: Determination,
    /// Each finding of the determination and of its comparison with the
    /// records.
    pub(crate) findings: Vec<Finding>,
}

impl SolverDetermination {
    /// Every checked case, as the determination takes it.
    pub(crate) fn cases(&self) -> Vec<DeterminedCase<'_>> {
        determined_cases(&self.programs, &self.concept, &self.task, &self.session, self.constructions, &self.limits)
    }
}

/// The checked cases of the solver `id`, their determination and its
/// findings, or the fault that stops their setup.
pub(crate) fn solver_determination(corpus: &Path, tasks: &Path, id: &str) -> Result<SolverDetermination, String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let concept = check_case(&solver, cases.concept(), &clauses, &mut cache, "the concept case", false)?;
    let names = solver.case_names(Exclusion::WithoutExcluded);
    let programs = check_cases(&solver, &cases, &clauses, &mut cache, &|name| names.contains(name), false)?;
    let session = corpus_session();
    let limits = corpus_limits();
    let constructions = constructions()?;
    let bases = solver.base_case_names(Exclusion::WithoutExcluded);
    let (determination, findings) = {
        let determined = determined_cases(&programs, &concept, &task, &session, constructions, &limits);
        let base_cases: Vec<DeterminedCase<'_>> = determined.iter().filter(|case| bases.contains(case.name)).copied().collect();
        let determination = determine(&base_cases, &judged, World::Closed);
        let mut findings: Vec<Finding> = determination.cases.iter().filter_map(|(name, outcome, _)| case_fault(name, outcome)).collect();
        let records: Vec<(&ProgramRelation, &ParamValue)> = solver.arcdata.value().params.iter().map(|param| (&param.value().name, &param.value().value)).collect();
        let comparison = Comparison { determined: &base_cases, determination: &determination, records: &records, session: &session, registry, numbers: RefCell::default() };
        findings.extend(comparison.findings());
        (determination, findings)
    };
    Ok(SolverDetermination { task, judged, concept, solver, programs, session, limits, constructions, determination, findings })
}

/// The fault line of a case that `outcome` gives, or `None` for a case that
/// is solved.
fn case_fault(name: &CaseName, outcome: &CaseOutcome) -> Option<Finding> {
    let case = case_spelled(name);
    let line = match outcome {
        CaseOutcome::Solved => return None,
        CaseOutcome::Stopped { stop, parameters } => {
            let parameters: Vec<String> = parameters.iter().map(relation_spelled).collect();
            format!("{case}: a stop at {:?} at the form {:?}, with a domain of several values at {}", stop.bound, stop.form, parameters.join(", "))
        }
        CaseOutcome::Fault(fault) => format!("{case}: {}", fault_text(fault)),
        CaseOutcome::Unsolved => format!("{case}: no assignment at which the case solves every train pair is left"),
    };
    Some(Finding::Fault(line))
}

/// A fault of a run as a line gives it, with its form.
fn fault_text(fault: &RunFault) -> String {
    format!("a fault of the run at {:?}: {}", fault.form, fault.message)
}

/// One relation's rows on both sides, as [`renaming_exists`] takes them: the
/// record's, and the engine's.
type Compared = (BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>);

/// The comparison of a solver's determined values with its records.
struct Comparison<'c> {
    determined: &'c [DeterminedCase<'c>],
    determination: &'c Determination,
    records: &'c [(&'c ProgramRelation, &'c ParamValue)],
    session: &'c TaskSession,
    registry: &'c Registry,
    /// The number of each Ident of the records, one numbering across every
    /// relation compared, so that one entity has one number.
    numbers: RefCell<StableHashMap<Ident, i64>>,
}

impl Comparison<'_> {
    /// Each finding of the comparison: each parameter that the
    /// determination gives a value or an error, in its order, then each
    /// `RIGID_DET` assembly whose parts the records give, in the order of
    /// the records. The Idents of every relation compared share one
    /// renaming.
    fn findings(&self) -> Vec<Finding> {
        let mut findings = Vec::new();
        let mut compared: Vec<Compared> = Vec::new();
        for (relation, parameter) in &self.determination.parameters {
            if self.determination.reads_demonstrated(relation) {
                continue;
            }
            let name = relation_spelled(relation);
            let value = match parameter {
                Parameter::Pick => continue,
                Parameter::Underdetermined(values) => {
                    findings.push(Finding::Fault(format!("{name}: underdetermined: {} values are left after the restriction across cases", values.len())));
                    continue;
                }
                Parameter::Determined(value) => value.clone(),
                Parameter::Open(values) => union(values.clone()),
            };
            let Some(record) = self.record(relation) else {
                if !self.in_compared_assembly(relation) && self.read_by_program(relation) {
                    findings.push(Finding::Fault(format!("{name}: no `param` record gives the parameter, so its determined value is not compared")));
                }
                continue;
            };
            let Some((program, node)) = self.det(relation) else {
                unreachable!("a parameter that the determination gives is a `DET` of a case it runs")
            };
            let relation = GraphRelation { node, output: None };
            let Some(types) = program.types.columns(&relation) else {
                findings.push(Finding::Fault(format!("{name}: the relation's columns have no types")));
                continue;
            };
            match self.leaves(types, record, &rows_of(&value)) {
                Ok((record, engine)) => {
                    if let Some(what) = differs(record, engine, &mut compared) {
                        findings.push(Finding::Difference { parameter: name.clone(), line: format!("{name}: the determined value differs from its `param` record: {what}") });
                    }
                }
                Err(fault) => findings.push(Finding::Fault(format!("{name}: {fault}"))),
            }
        }
        let mut assemblies: Vec<&RigidDetName> = Vec::new();
        for (relation, _) in self.records {
            if let ProgramRelation::Output(output) = relation
                && let OutputOwner::RigidDet(assembly) = &output.of
                && !assemblies.contains(&assembly)
            {
                assemblies.push(assembly);
            }
        }
        for assembly in assemblies {
            if let Some(finding) = self.assembly(assembly, &mut compared) {
                findings.push(finding);
            }
        }
        findings
    }

    /// The record of `relation`, or `None` where the solver holds none.
    fn record(&self, relation: &ProgramRelation) -> Option<&ParamValue> {
        self.records.iter().find(|(name, _)| *name == relation).map(|(_, value)| *value)
    }

    /// The program of the first case that runs the `DET` of `relation`, and
    /// that `DET`'s node in it, or `None` where no case runs it.
    fn det(&self, relation: &ProgramRelation) -> Option<(&CheckedProgram, GraphNodeIndex)> {
        self.determined.iter().find_map(|case| Some((case.program, det_node(case.program, relation)?)))
    }

    /// Whether the `OUT` form of some case reads the `DET` of `relation`,
    /// through clauses and instances and through no task-wide relation's
    /// body. Such a `DET` is a parameter, which the program reads as stored
    /// facts. Each other `DET` is part of the determination.
    fn read_by_program(&self, relation: &ProgramRelation) -> bool {
        self.determined.iter().any(|case| {
            let (Some(node), Some(output)) = (det_node(case.program, relation), output_relation(case.program)) else { return false };
            let graph = &case.program.program.graph;
            let mut seen = vec![false; graph.nodes.len()];
            let mut stack = vec![output.node];
            while let Some(at) = stack.pop() {
                if std::mem::replace(&mut seen[at.0 as usize], true) {
                    continue;
                }
                if at == node {
                    return true;
                }
                let kind = &graph.nodes[at.0 as usize].kind;
                if !matches!(kind, DependencyKind::Parameter(_) | DependencyKind::RigidAssembly(_))
                    && !(matches!(kind, DependencyKind::Chosen(_)) && case.program.program.side(at) == Side::TaskWide)
                {
                    stack.extend(graph.reads[at.0 as usize].iter().copied());
                }
            }
            false
        })
    }

    /// Whether the `DET` of `relation` is read by a `RIGID_DET` assembly
    /// whose parts the records give, which [`Self::assembly`] compares
    /// through those parts.
    fn in_compared_assembly(&self, relation: &ProgramRelation) -> bool {
        let Some((program, node)) = self.det(relation) else {
            return false;
        };
        let graph = &program.program.graph;
        graph.nodes.iter().zip(&graph.reads).any(|(assembly, reads)| {
            matches!(&assembly.kind, DependencyKind::RigidAssembly(name) if reads.contains(&node) && self.records.iter().any(|(record, _)| is_part(record, name)))
        })
    }

    /// The comparison of the parts of `assembly` with their records, up to
    /// one D4 element, the same for every part, as
    /// `docs/engine/determination.md#rigid_det` gives: its finding, or
    /// `None` where some element makes every part agree, whose rows then
    /// join `compared`.
    fn assembly(&self, assembly: &RigidDetName, compared: &mut Vec<Compared>) -> Option<Finding> {
        let name = relation_spelled(&ProgramRelation::Output(arclog::program::OutputName { of: OutputOwner::RigidDet(assembly.clone()), path: Arc::new([]) }));
        let parts: Vec<(&ProgramRelation, &ParamValue)> = self.records.iter().copied().filter(|(relation, _)| is_part(relation, assembly)).collect();
        let Some((case, node)) = self.determined.iter().find_map(|case| {
            let solved = self.determination.cases.iter().any(|(name, outcome, _)| name == case.name && matches!(outcome, CaseOutcome::Solved));
            let nodes = &case.program.program.graph.nodes;
            let node = nodes.iter().position(|node| matches!(&node.kind, DependencyKind::RigidAssembly(found) if found == assembly))?;
            solved.then_some((case, GraphNodeIndex(node as u32)))
        }) else {
            return Some(Finding::Fault(format!("{name}: no solved base case evaluates the assembly, so its parts are not compared")));
        };
        let parameters = self.determination.values(case.name);
        let evaluation = case.evaluation(&parameters);
        // Each part: its name, its record, and the engine's rows with the
        // column of the Pose at which each row stands.
        let mut engine: Vec<(String, &ParamValue, &[ValueType], usize, Vec<Vec<TermId>>)> = Vec::new();
        for (relation, record) in parts {
            let ProgramRelation::Output(output) = relation else { unreachable!("an output of the assembly") };
            let part = relation_spelled(relation);
            let graph = GraphRelation { node, output: Some(output.path.clone()) };
            if scope_of(case.program, &graph) != ExampleScope::TaskWide {
                return Some(Finding::Fault(format!("{part}: the part is a relation per example, and its `param` record is task-wide")));
            }
            let value = match evaluation.relation(&graph, None) {
                Ok(RelationValue::Rows(rows)) => rows,
                Ok(other) => return Some(Finding::Fault(format!("{part}: the part at the determined values is {other:?}"))),
                Err(fault) => return Some(Finding::Fault(format!("{part}: {}", fault_text(&fault)))),
            };
            let Some(types) = case.program.types.columns(&graph) else {
                return Some(Finding::Fault(format!("{part}: the relation's columns have no types")));
            };
            let Some(pose_column) = types.iter().position(|ty| matches!(ty, ValueType::Pose(_))) else {
                return Some(Finding::Fault(format!("{part}: the part's columns hold no Pose")));
            };
            engine.push((part, record, types, pose_column, rows_of(&value)));
        }
        // One Pose value for every part: the first that a row holds.
        let pose = engine.iter().find_map(|(_, _, _, pose_column, rows)| rows.first().map(|row| row[*pose_column]));
        // A part's record holds its columns without the Pose.
        let mut sides: Vec<(String, &ParamValue, Vec<ValueType>, Vec<Vec<TermId>>)> = Vec::new();
        for (part, record, types, pose_column, rows) in engine {
            let kept = |column: &usize| *column != pose_column;
            let rows = rows.into_iter().filter(|row| Some(row[pose_column]) == pose).map(|row| (0..row.len()).filter(kept).map(|column| row[column]).collect()).collect();
            let types = (0..types.len()).filter(kept).map(|column| types[column].clone()).collect();
            sides.push((part, record, types, rows));
        }
        let geometry = Geometry::get();
        for &element in geometry.domain(&ValueType::D4) {
            let g = geometry.element(element);
            let mut trial = compared.clone();
            let mut agrees = true;
            for (part, record, types, rows) in &sides {
                let moved: Vec<Vec<TermId>> = rows.iter().filter_map(|row| image(geometry, g, row, types).map(Vec::from)).collect();
                match self.leaves(types, record, &moved) {
                    Ok((record, engine)) => agrees = differs(record, engine, &mut trial).is_none(),
                    Err(fault) => return Some(Finding::Fault(format!("{part}: {fault}"))),
                }
                if !agrees {
                    break;
                }
            }
            if agrees {
                *compared = trial;
                return None;
            }
        }
        Some(Finding::Difference { parameter: name.clone(), line: format!("{name}: no one D4 element takes each part of the assembly onto its `param` record") })
    }

    /// The leaves of `record` and of the engine's `rows`, at the column
    /// `types`; or the fault that keeps them from a comparison.
    fn leaves(&self, types: &[ValueType], record: &ParamValue, rows: &[Vec<TermId>]) -> Result<Compared, String> {
        let encoded = {
            let mut table = self.session.intern.write().expect("an intern table that no panic poisoned");
            arclog::terms::encode_param_value(record, types, self.registry, &mut table)
                .map_err(|error| format!("the `param` record does not read at the relation's column types: {error:?}"))?
        };
        let orientation = |name: &str| Ok(Leaf::Other(name.into()));
        let row_leaves = |row: &[TermId]| -> Result<Vec<EngineLeaf>, String> {
            let leaves: Result<Vec<Vec<EngineLeaf>>, String> = row.iter().zip(types).map(|(&id, ty)| term_leaves(Term::decode(id, ty), self.registry, &orientation)).collect();
            Ok(leaves?.concat())
        };
        let mut numbers = self.numbers.borrow_mut();
        let mut written = BTreeSet::new();
        for row in &encoded {
            let leaves = row_leaves(row)?.into_iter().map(|leaf| match leaf {
                EngineLeaf::Written(leaf) => leaf,
                EngineLeaf::Ident(ident) => {
                    let next = numbers.len() as i64;
                    Leaf::Number(*numbers.entry(ident).or_insert(next))
                }
            });
            written.insert(leaves.collect());
        }
        let engine = rows.iter().map(|row| row_leaves(row)).collect::<Result<_, _>>()?;
        Ok((written, engine))
    }
}

/// The rows of `relation`.
fn rows_of(relation: &Relation) -> Vec<Vec<TermId>> {
    let mut rows = Vec::new();
    each_row(relation, &mut |row| rows.push(row.to_vec()));
    rows
}

/// Whether `relation` is a part of `assembly`: an output of it other than
/// its pose.
fn is_part(relation: &ProgramRelation, assembly: &RigidDetName) -> bool {
    matches!(relation, ProgramRelation::Output(output) if output.of == OutputOwner::RigidDet(assembly.clone()) && output.path.first() != Some(&arclog::program::OutputStep::Pose))
}

/// What differs between the record's rows and the engine's rows of one
/// relation, `None` where they agree, at each place that holds no Ident,
/// and, where the engine's rows hold Idents, under one renaming with the
/// relations of `compared`, which they then join.
fn differs(record: BTreeSet<Vec<Leaf>>, engine: Vec<Vec<EngineLeaf>>, compared: &mut Vec<Compared>) -> Option<String> {
    if let (Some(ours), Some(theirs)) = (engine.first(), record.first())
        && ours.len() != theirs.len()
    {
        return Some(format!("its rows hold {} leaves in the engine and {} in the record", ours.len(), theirs.len()));
    }
    if !same_without_idents(&engine, &record) {
        return Some(format!("{} rows against the record's {}", engine.len(), record.len()));
    }
    if !engine.iter().flatten().any(|leaf| matches!(leaf, EngineLeaf::Ident(_))) {
        return None;
    }
    compared.push((record, engine));
    let relations: Vec<(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = compared.iter().map(|(record, engine)| (record, engine.clone())).collect();
    if renaming_exists(&relations) {
        return None;
    }
    compared.pop();
    Some("no one renaming of Idents makes its rows and those of the relations compared before it agree".to_owned())
}
