//! What the comparisons with Souffle's rows share (`compare`, `row-parity`):
//! the pair names, Souffle's rows as `scripts/souffle_parity.py rerun --json`
//! writes them, and the engine's rows of a relation on a pair, as the leaves
//! those rows write.

use std::collections::{BTreeMap, BTreeSet};
use std::ops::ControlFlow;

use arclog::eval::join::each_row;
use arclog::eval::models::ModelsEnd;
use arclog::eval::{relation_of, Evaluation, RelationValue};
use arclog::program::{DeclaredName, InstanceName, OutputName, OutputOwner, OutputStep, PortName, ProgramRelation, RelationName};
use arclog::relations::Relation;
use arclog::resolver::Side;
use arclog::task::Task;
use arclog::terms::{Example, Term};
use arclog::types::{GraphRelation, ValueType};
use serde_json::Value;

use crate::renaming::{term_leaves, EngineLeaf, Leaf};
use crate::row_counts::column_names;

/// The pair names of the task's examples, as the snapshot writes them.
pub(crate) fn pair_name(task: &Task, example: usize) -> String {
    if example < task.train.len() { format!("train {example}") } else { format!("test {}", example - task.train.len()) }
}


/// The rows of Souffle's rerun of a case on one pair, each relation by its
/// arclog name, in the rerun's order, and the number Souffle gives each
/// orientation constant of the lib, by its name.
pub(crate) struct Rerun {
    pub(crate) relations: Vec<(String, BTreeSet<Vec<Leaf>>)>,
    pub(crate) orientation_constants: BTreeMap<String, i64>,
}

impl Rerun {
    /// The rerun that `json`, the output of `rerun --json`, gives.
    pub(crate) fn of(json: &Value) -> Option<Rerun> {
        let relations = json.get("relations")?.as_array()?.iter().map(|relation| {
            let [name, rows] = relation.as_array()?.as_slice() else { return None };
            let rows = rows.as_array()?.iter().map(|row| row.as_array()?.iter().map(Leaf::of).collect()).collect::<Option<_>>()?;
            Some((name.as_str()?.to_owned(), rows))
        });
        let constants = json.get("orientation_constants")?.as_object()?;
        Some(Rerun {
            relations: relations.collect::<Option<_>>()?,
            orientation_constants: constants.iter().map(|(name, n)| Some((name.clone(), n.as_i64()?))).collect::<Option<_>>()?,
        })
    }
}

/// What the engine gives for a relation on a pair.
pub(crate) enum EngineRows {
    /// The relation's rows, each the leaves Souffle's rerun writes for it,
    /// the same at every model of the case.
    Rows(Vec<Vec<EngineLeaf>>),
    /// Two models of the case give the relation different rows, so Souffle's
    /// one set of rows has nothing to compare with.
    DifferBetweenModels,
    /// A text for rows the engine cannot give.
    Fault(String),
}

/// The columns of a row of the engine that a comparison reads.
#[derive(Clone, Copy)]
pub(crate) enum Projection<'a> {
    /// Every row position, in order.
    All,
    /// These row positions, in this order.
    Positions(&'a [usize]),
}

/// The relation that `name` gives in `program`: a relation a clause derives
/// or a parameter stores, or, for `&<instance>.<port>`, an output of that
/// instance.
fn named_relation(program: &arclog::check::CheckedProgram, name: &str) -> Option<GraphRelation> {
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written(name.into())));
    relation_of(program, &declared).or_else(|| {
        let (instance, port) = name.split_once('.')?;
        let output = OutputName {
            of: OutputOwner::Instance(InstanceName(DeclaredName::Written(instance.into()))),
            path: [OutputStep::Port(PortName(port.into()))].into(),
        };
        relation_of(program, &ProgramRelation::Output(output))
    })
}

/// The names of the row positions of the relation that `name` declares in
/// the program of `evaluation` (`column_names`); `None` where the program
/// derives no relation of that name, and a text where its columns have no
/// types.
pub(crate) fn engine_columns(evaluation: &Evaluation<'_>, name: &str) -> Option<Result<Vec<String>, String>> {
    let program = evaluation.program;
    let relation = named_relation(program, name)?;
    Some(match program.types.columns(&relation) {
        Some(types) => Ok(column_names(evaluation, &relation, types.len())),
        None => Err("rows whose columns have no types".to_owned()),
    })
}

/// The engine's rows of the relation that `name` declares on `example`,
/// each row the leaves Souffle's rerun writes for it, as `projection` gives, an orientation
/// constant by the number `constants` gives its name; `None` where the
/// program derives no relation of that name. The rows are read at each
/// model of the case: where two models give different rows as sets, the
/// result is [`EngineRows::DifferBetweenModels`].
pub(crate) fn engine_rows(evaluation: &Evaluation<'_>, name: &str, example: Example, constants: &BTreeMap<String, i64>, projection: Projection<'_>) -> Option<EngineRows> {
    let program = evaluation.program;
    let relation = named_relation(program, name)?;
    let on = (program.program.side(relation.node) == Side::PerInput).then_some(example);
    let Some(types) = program.types.columns(&relation) else { return Some(EngineRows::Fault("rows whose columns have no types".to_owned())) };
    let mut first: Option<Vec<Vec<EngineLeaf>>> = None;
    let mut fault = None;
    let mut differ = false;
    let end = evaluation.models(&relation, on, &mut |value| {
        let RelationValue::Rows(rows) = value else {
            fault = Some(format!("{value:?}"));
            return ControlFlow::Break(());
        };
        let rows = match model_leaves(evaluation, rows, types, constants, projection) {
            Ok(rows) => rows,
            Err(text) => {
                fault = Some(text);
                return ControlFlow::Break(());
            }
        };
        match &first {
            None => first = Some(rows),
            Some(kept) if same_rows(kept, &rows) => {}
            Some(_) => {
                differ = true;
                return ControlFlow::Break(());
            }
        }
        ControlFlow::Continue(())
    });
    match end {
        Err(error) => return Some(EngineRows::Fault(error.message.to_string())),
        Ok(ModelsEnd::Stopped(stop)) if !differ && fault.is_none() => return Some(EngineRows::Fault(format!("{stop:?}"))),
        Ok(_) => {}
    }
    Some(match (fault, differ, first) {
        (Some(text), _, _) => EngineRows::Fault(text),
        (None, true, _) => EngineRows::DifferBetweenModels,
        (None, false, Some(rows)) => EngineRows::Rows(rows),
        (None, false, None) => EngineRows::Rows(Vec::new()),
    })
}

/// The leaves of the rows of one model's value of a relation of column
/// types `types`.
pub(crate) fn model_leaves(
    evaluation: &Evaluation<'_>,
    rows: &Relation,
    types: &[ValueType],
    constants: &BTreeMap<String, i64>,
    projection: Projection<'_>,
) -> Result<Vec<Vec<EngineLeaf>>, String> {
    let mut written = Vec::new();
    let mut faults = BTreeSet::new();
    each_row(rows, &mut |row| match row.iter().zip(types).map(|(&id, ty)| term_leaves(Term::decode(id, ty), evaluation.registry, &|name| souffle_number(name, constants))).collect::<Result<Vec<_>, _>>() {
        Ok(leaves) => written.push(match projection {
        Projection::All => leaves.concat(),
        Projection::Positions(positions) => positions.iter().flat_map(|&position| leaves[position].clone()).collect(),
    }),
        Err(text) => {
            faults.insert(text);
        }
    });
    faults.into_iter().next().map_or(Ok(written), Err)
}

/// The leaf of the orientation constant `name` in Souffle's rerun: its
/// number in `constants`.
pub(crate) fn souffle_number(name: &str, constants: &BTreeMap<String, i64>) -> Result<Leaf, String> {
    constants.get(name).map(|&n| Leaf::Number(n)).ok_or_else(|| format!("the orientation constant {name}, which the rerun gives no number"))
}

/// Whether `a` and `b` hold the same rows, each row once.
pub(crate) fn same_rows(a: &[Vec<EngineLeaf>], b: &[Vec<EngineLeaf>]) -> bool {
    a.iter().all(|row| b.contains(row)) && b.iter().all(|row| a.contains(row))
}
