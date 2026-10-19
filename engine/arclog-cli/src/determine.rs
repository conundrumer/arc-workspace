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
use arclog::eval::{RelationValue, RunFault};
use arclog::hash::StableHashMap;
use arclog::harness::{print_ended, require_optimized_build, run_over_corpus, CorpusSolver, SolverResult};
use arclog::judge::candidates::World;
use arclog::judge::determination::{determine, CaseOutcome, DeterminedCase, Determination, Parameter};
use arclog::program::{OutputOwner, ParamValue, ProgramRelation, RigidDetName};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::{resolve_cases, DependencyKind, GraphNodeIndex};
use arclog::session::TaskSession;
use arclog::solver::{CaseName, Exclusion};
use arclog::terms::{Ident, Term, TermId};
use arclog::types::{GraphRelation, ValueType};

use crate::concept_case::{check_case, corpus_limits, corpus_session, read_corpus_task, CorpusTask};
use crate::engine_run::constructions;
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
    let report = run_over_corpus(&corpus, |solver| match &selected {
        Some(ids) if !ids.contains(&solver.task_id) => SolverResult::Pass,
        _ => determine_solver(&corpus, &tasks, solver, &differing),
    }, print_ended);
    let report = match report {
        Ok(report) => report,
        Err(error) => {
            eprintln!("the corpus does not read: {error:?}");
            return ExitCode::from(2);
        }
    };
    let differing = differing.into_inner().expect("a set that no panic poisoned").len();
    let determined = selected.map_or(report.checked, |ids| ids.len());
    let faulted = report.failures.len() - differing;
    println!("{differing} of {determined} solvers differ from their `param` records, and {faulted} others give a fault that keeps a case or a parameter from its comparison");
    if report.failures.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
}

/// A line of the report on a solver.
enum Finding {
    /// A determined value that differs from its `param` record.
    Difference(String),
    /// A fault that keeps a case or a parameter from its comparison.
    Fault(String),
}

/// The report on `solver`, which goes into `differing` where a determined
/// value differs from its record.
fn determine_solver(corpus: &Path, tasks: &Path, solver: &CorpusSolver, differing: &Mutex<BTreeSet<String>>) -> SolverResult {
    let findings = findings(corpus, tasks, &solver.task_id).unwrap_or_else(|fault| vec![Finding::Fault(fault)]);
    if findings.iter().any(|finding| matches!(finding, Finding::Difference(_))) {
        differing.lock().expect("a set that no panic poisoned").insert(solver.task_id.clone());
    }
    let lines: Vec<String> = findings.into_iter().map(|(Finding::Difference(line) | Finding::Fault(line))| line).collect();
    if lines.is_empty() { SolverResult::Pass } else { SolverResult::Fail(lines) }
}

/// Each finding of the determination of the solver `id` and its comparison
/// with the solver's records, or the fault that stops its setup.
fn findings(corpus: &Path, tasks: &Path, id: &str) -> Result<Vec<Finding>, String> {
    let CorpusTask { solver, task, judged } = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let concept = check_case(cases.concept(), &clauses, &mut cache, "the concept case")?;
    let bases = solver.base_case_names(Exclusion::WithoutExcluded);
    let mut programs: Vec<(CaseName, CheckedProgram)> = Vec::new();
    for case in cases.cases().filter(|case| bases.contains(&case.case.name)) {
        let what = format!("the case {}", case_spelled(&case.case.name));
        programs.push((case.case.name.clone(), check_case(case, &clauses, &mut cache, &what)?));
    }
    let session = corpus_session();
    let limits = corpus_limits();
    let constructions = constructions()?;
    let determined: Vec<DeterminedCase<'_>> = programs
        .iter()
        .map(|(name, program)| DeterminedCase { name, program, concept: &concept, task: &task, session: &session, registry, constructions, limits: &limits })
        .collect();
    let determination = determine(&determined, &judged, World::Closed);
    let mut findings: Vec<Finding> = determination.cases.iter().filter_map(|(name, outcome, _)| case_fault(name, outcome)).collect();
    let records: Vec<(&ProgramRelation, &ParamValue)> = solver.arcdata.value().params.iter().map(|param| (&param.value().name, &param.value().value)).collect();
    let comparison = Comparison { determined: &determined, determination: &determination, records: &records, session: &session, registry };
    findings.extend(comparison.findings());
    Ok(findings)
}

/// The fault line of a case that `outcome` gives, or `None` for a case that
/// is solved or holds a `DEMONSTRATED` form.
fn case_fault(name: &CaseName, outcome: &CaseOutcome) -> Option<Finding> {
    let case = case_spelled(name);
    let line = match outcome {
        CaseOutcome::Solved | CaseOutcome::Demonstrated => return None,
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

/// The name of a case as a line gives it: its alts, or `concept` for the
/// case that takes none.
fn case_spelled(name: &CaseName) -> String {
    if name.0.is_empty() { "concept".to_owned() } else { name.0.iter().map(|alt| &*alt.0).collect::<Vec<_>>().join(" ") }
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
            let name = relation_spelled(relation);
            let value = match parameter {
                Parameter::Demonstrated | Parameter::Pick => continue,
                Parameter::Underdetermined(values) => {
                    findings.push(Finding::Fault(format!("{name}: underdetermined: {} values are left after the restriction across cases", values.len())));
                    continue;
                }
                Parameter::Determined(value) => value.clone(),
                Parameter::Open(values) => union(values.clone()),
            };
            let Some(record) = self.record(relation) else { continue };
            let Some((program, node)) = self.determined.iter().find_map(|case| Some((case.program, det_node(case.program, relation)?))) else {
                unreachable!("a parameter that the determination gives is a `DET` of a case it runs")
            };
            let relation = GraphRelation { node, output: None };
            match self.leaves(program, &relation, record, &value, None) {
                Ok((record, engine)) => {
                    if let Some(what) = differs(record, engine, &mut compared) {
                        findings.push(Finding::Difference(format!("{name}: the determined value differs from its `param` record: {what}")));
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

    /// The comparison of the parts of `assembly` with their records, up to
    /// one D4 element, the same for every part, as
    /// `docs/engine/determination.md#rigid_det` gives: its finding, or
    /// `None` where some element makes every part agree, whose rows then
    /// join `compared`.
    fn assembly(&self, assembly: &RigidDetName, compared: &mut Vec<Compared>) -> Option<Finding> {
        let name = relation_spelled(&ProgramRelation::Output(arclog::program::OutputName { of: OutputOwner::RigidDet(assembly.clone()), path: Arc::new([]) }));
        let parts: Vec<(&ProgramRelation, &ParamValue)> = self.records.iter().copied().filter(|(relation, _)| {
            matches!(relation, ProgramRelation::Output(output) if output.of == OutputOwner::RigidDet(assembly.clone()) && output.path.first() != Some(&arclog::program::OutputStep::Pose))
        }).collect();
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
        let mut sides: Vec<(String, GraphRelation, &ParamValue, Arc<Relation>)> = Vec::new();
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
            sides.push((part, graph, record, value));
        }
        let geometry = Geometry::get();
        for &element in geometry.domain(&ValueType::D4) {
            let g = geometry.element(element);
            let mut trial = compared.clone();
            let mut agrees = true;
            for (part, graph, record, value) in &sides {
                let moved = |row: &[TermId], types: &[ValueType]| image(geometry, g, row, types).collect();
                match self.leaves(case.program, graph, record, value, Some(&moved)) {
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
        Some(Finding::Difference(format!("{name}: no one D4 element takes each part of the assembly onto its `param` record")))
    }

    /// The leaves of `record` and of the engine's rows `value` of
    /// `relation`, a relation of `program`, at its column types, each
    /// engine row first moved by `moved` where it is given; or the fault
    /// that keeps them from a comparison.
    fn leaves(
        &self,
        program: &CheckedProgram,
        relation: &GraphRelation,
        record: &ParamValue,
        value: &Relation,
        moved: Option<&dyn Fn(&[TermId], &[ValueType]) -> Vec<TermId>>,
    ) -> Result<Compared, String> {
        let types = program.types.columns(relation).ok_or("the relation's columns have no types")?;
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
        let mut numbers: StableHashMap<Ident, i64> = StableHashMap::default();
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
        let mut rows: Vec<Vec<TermId>> = Vec::new();
        each_row(value, &mut |row| rows.push(moved.map_or_else(|| row.to_vec(), |moved| moved(row, types))));
        let engine = rows.iter().map(|row| row_leaves(row)).collect::<Result<_, _>>()?;
        Ok((written, engine))
    }
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
