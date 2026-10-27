//! What the comparisons with Souffle's rows share (`compare`, `row-parity`):
//! the pair names, Souffle's rows as `scripts/souffle_parity.py rerun --json`
//! writes them, and the engine's rows of a relation on a pair, as the leaves
//! those rows write.

use std::collections::{BTreeMap, BTreeSet};
use std::ops::ControlFlow;

use arclog::eval::join::each_row;
use arclog::eval::models::ModelsEnd;
use arclog::eval::{input_relation, relation_of, Evaluation, RelationValue};
use arclog::hash::StableHashSet;
use arclog::program::{DeclaredName, InstanceName, OutputName, OutputOwner, OutputStep, PortName, ProgramRelation, RelationName};
use arclog::relations::Relation;
use arclog::resolver::Side;
use arclog::task::Task;
use arclog::registry::Registry;
use arclog::terms::{Content, Example, Ident, InternTable, Term};
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

/// What the engine gives for a relation on a pair, for the comparisons that
/// need one set of rows (`compare`).
pub(crate) enum EngineRows {
    /// The relation's rows, each the leaves Souffle's rerun writes for it,
    /// the same at every model of the case.
    Rows(Vec<Vec<EngineLeaf>>),
    /// Two models of the case give the relation different rows, so Souffle's
    /// one set of rows has nothing to compare with.
    DifferBetweenModels,
    /// The reason that the name gives no one relation of the engine to
    /// compare.
    Skip(String),
    /// A text for rows the engine cannot give.
    Fault(String),
}

/// What the engine gives for a relation on a pair, at each model of the case.
pub(crate) enum EngineModels {
    /// The relation at each model, with the models that give the same rows
    /// and the same picks once; one entry where every model gives the same.
    Models(Vec<EngineModel>),
    /// The reason that the name gives no one relation of the engine to
    /// compare.
    Skip(String),
    /// A text for rows the engine cannot give.
    Fault(String),
}

/// One model of the case: the relation's rows there, each the leaves
/// Souffle's rerun writes for it, and the rows there of each pick asked for
/// (`PickRequest`), in the order asked, `None` where the model holds no
/// choice at it.
#[derive(Clone)]
pub(crate) struct EngineModel {
    pub(crate) rows: Vec<Vec<EngineLeaf>>,
    pub(crate) picks: Vec<Option<Vec<Vec<EngineLeaf>>>>,
}

impl EngineModel {
    /// Whether `self` and `other` hold the same rows and the same rows at
    /// each pick.
    fn same_as(&self, other: &EngineModel) -> bool {
        same_rows(&self.rows, &other.rows)
            && self.picks.len() == other.picks.len()
            && self.picks.iter().zip(&other.picks).all(|(a, b)| match (a, b) {
                (Some(a), Some(b)) => same_rows(a, b),
                (None, None) => true,
                _ => false,
            })
    }
}

/// A chosen relation whose rows at each model of the case a comparison
/// reads: the name of the relation and the columns of its rows that it reads.
#[derive(Clone, Copy)]
pub(crate) struct PickRequest<'a> {
    pub(crate) name: &'a str,
    pub(crate) projection: Projection<'a>,
}

/// One row position that a comparison reads, and whether its Idents are
/// written as the sets of their members.
#[derive(Clone, Copy)]
pub(crate) struct Column {
    pub(crate) position: usize,
    /// The Ident at the position is one that a lib relation mints, so it is
    /// written as the text of the set of its members (`ident_text`), not
    /// left as an Ident for a renaming.
    pub(crate) minted: bool,
}

/// The columns of a row of the engine that a comparison reads.
#[derive(Clone, Copy)]
pub(crate) enum Projection<'a> {
    /// Every row position, in order.
    All,
    /// These columns, in this order.
    Positions(&'a [Column]),
}

/// The reason that a name which several nodes of the graph hold, one per
/// `DEMO_RULE`, is not compared: Souffle's rows are the union over the
/// rules, and the engine's are those of one node.
const SEVERAL_FORMS: &str = "several forms of the program derive the name";

/// The relation that `name` gives in `program`: a relation a clause derives
/// or a parameter stores, or, for `&<instance>.<port>`, an output of that
/// instance, else its input of that port; the reason for a skip where more
/// than one node holds the name.
pub(crate) fn named_relation(program: &arclog::check::CheckedProgram, name: &str) -> Option<Result<GraphRelation, String>> {
    let declared = ProgramRelation::Declared(RelationName(DeclaredName::Written(name.into())));
    let relation = relation_of(program, &declared).or_else(|| {
        let (instance, port) = name.split_once('.')?;
        let instance = InstanceName(DeclaredName::Written(instance.into()));
        let port = PortName(port.into());
        let output = OutputName { of: OutputOwner::Instance(instance.clone()), path: [OutputStep::Port(port.clone())].into() };
        relation_of(program, &ProgramRelation::Output(output)).or_else(|| input_relation(program, &instance, &port))
    })?;
    let nodes = &program.program.graph.nodes;
    let holders = nodes.iter().filter(|node| node.kind == nodes[relation.node.0 as usize].kind).count();
    Some(if holders > 1 { Err(SEVERAL_FORMS.to_owned()) } else { Ok(relation) })
}

/// One row position of the engine's relation, by its name.
pub(crate) struct EngineColumn {
    pub(crate) name: String,
    /// The column's type is a `Pose`, whose value depends on the frame, which
    /// no read observes (`docs/arclog/rigid.md`).
    pub(crate) pose: bool,
}

/// The example `relation` is read on at the pair of `example`: that example
/// for a relation per input, else none.
fn read_on(program: &arclog::check::CheckedProgram, relation: &GraphRelation, example: Example) -> Option<Example> {
    (program.program.side(relation.node) == Side::PerInput).then_some(example)
}

/// The row positions of the relation that `name` declares in the program of
/// `evaluation`, each by its name (`column_names`); `None` where the program
/// derives no relation of that name, [`EngineModels::Skip`] where several
/// nodes derive it, and a [`EngineModels::Fault`] where its columns have no
/// types.
pub(crate) fn engine_columns(evaluation: &Evaluation<'_>, name: &str) -> Option<Result<Vec<EngineColumn>, EngineModels>> {
    let program = evaluation.program;
    let relation = match named_relation(program, name)? {
        Ok(relation) => relation,
        Err(reason) => return Some(Err(EngineModels::Skip(reason))),
    };
    Some(match program.types.columns(&relation) {
        Some(types) => Ok(column_names(evaluation, &relation, types.len())
            .into_iter()
            .zip(types)
            .map(|(name, ty)| EngineColumn { name, pose: matches!(ty, ValueType::Pose(_)) })
            .collect()),
        None => Err(EngineModels::Fault("rows whose columns have no types".to_owned())),
    })
}

/// The engine's rows of the relation that `name` declares on `example`,
/// each row the leaves Souffle's rerun writes for it, as `projection` gives, an orientation
/// constant by the number `constants` gives its name; `None` where the
/// program derives no relation of that name. The rows are read at each
/// model of the case: where two models give different rows as sets, the
/// result is [`EngineRows::DifferBetweenModels`].
pub(crate) fn engine_rows(evaluation: &Evaluation<'_>, name: &str, example: Example, constants: &BTreeMap<String, i64>, projection: Projection<'_>) -> Option<EngineRows> {
    Some(match models_of(evaluation, name, example, constants, projection, &[], 2)? {
        EngineModels::Skip(reason) => EngineRows::Skip(reason),
        EngineModels::Fault(text) => EngineRows::Fault(text),
        EngineModels::Models(mut models) if models.len() == 1 => EngineRows::Rows(models.remove(0).rows),
        EngineModels::Models(_) => EngineRows::DifferBetweenModels,
    })
}

/// The engine's rows of the relation that `name` declares on `example` at
/// each model of the case, as `projection` gives them, with the rows at the
/// model of each of `picks`; `None` where the program derives no relation of
/// that name.
pub(crate) fn engine_models(
    evaluation: &Evaluation<'_>,
    name: &str,
    example: Example,
    constants: &BTreeMap<String, i64>,
    projection: Projection<'_>,
    picks: &[PickRequest<'_>],
) -> Option<EngineModels> {
    models_of(evaluation, name, example, constants, projection, picks, usize::MAX)
}

/// [`engine_models`], stopping at the `at_most`th distinct model.
fn models_of(
    evaluation: &Evaluation<'_>,
    name: &str,
    example: Example,
    constants: &BTreeMap<String, i64>,
    projection: Projection<'_>,
    picks: &[PickRequest<'_>],
    at_most: usize,
) -> Option<EngineModels> {
    let program = evaluation.program;
    let relation = match named_relation(program, name)? {
        Ok(relation) => relation,
        Err(reason) => return Some(EngineModels::Skip(reason)),
    };
    let on = read_on(program, &relation, example);
    let Some(types) = program.types.columns(&relation) else { return Some(EngineModels::Fault("rows whose columns have no types".to_owned())) };
    let mut chosen = Vec::new();
    for pick in picks {
        let relation = match named_relation(program, pick.name) {
            Some(Ok(relation)) => relation,
            Some(Err(reason)) => return Some(EngineModels::Fault(format!("the open parameter {}: {reason}", pick.name))),
            None => return Some(EngineModels::Fault(format!("the program has no relation {}, a pick of the open value", pick.name))),
        };
        let Some(types) = program.types.columns(&relation) else { return Some(EngineModels::Fault(format!("the rows of {} have no column types", pick.name))) };
        let on = read_on(program, &relation, example);
        chosen.push(((relation, on), types));
    }
    let asked: Vec<_> = chosen.iter().map(|(asked, _)| asked.clone()).collect();
    let mut models: Vec<EngineModel> = Vec::new();
    let mut fault = None;
    let end = evaluation.models_with_picks(&relation, on, &asked, &mut |value, at_model| {
        let RelationValue::Rows(rows) = value else {
            fault = Some(format!("{value:?}"));
            return ControlFlow::Break(());
        };
        let read = || -> Result<EngineModel, String> {
            let rows = model_leaves(evaluation, rows, types, constants, projection)?;
            let mut held = Vec::new();
            for ((pick, (_, types)), value) in picks.iter().zip(&chosen).zip(at_model) {
                held.push(match value {
                    None => None,
                    Some(RelationValue::Rows(rows)) => Some(model_leaves(evaluation, rows, types, constants, pick.projection)?),
                    Some(other) => return Err(format!("{}: {other:?}", pick.name)),
                });
            }
            Ok(EngineModel { rows, picks: held })
        };
        let model = match read() {
            Ok(model) => model,
            Err(text) => {
                fault = Some(text);
                return ControlFlow::Break(());
            }
        };
        if !models.iter().any(|kept| kept.same_as(&model)) {
            models.push(model);
        }
        if models.len() >= at_most { ControlFlow::Break(()) } else { ControlFlow::Continue(()) }
    });
    match end {
        Err(error) => return Some(EngineModels::Fault(error.message.to_string())),
        Ok(ModelsEnd::Stopped(stop)) if fault.is_none() => return Some(EngineModels::Fault(format!("{stop:?}"))),
        Ok(_) => {}
    }
    Some(match fault {
        Some(text) => EngineModels::Fault(text),
        None if models.is_empty() => EngineModels::Models(vec![EngineModel { rows: Vec::new(), picks: vec![None; picks.len()] }]),
        None => EngineModels::Models(models),
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
    each_row(rows, &mut |row| {
        let leaves = row.iter().zip(types).map(|(&id, ty)| term_leaves(Term::decode(id, ty), evaluation.registry, &|name| souffle_number(name, constants))).collect::<Result<Vec<_>, _>>();
        match leaves.and_then(|leaves| projected(evaluation, leaves, constants, projection)) {
            Ok(leaves) => written.push(leaves),
            Err(text) => {
                faults.insert(text);
            }
        }
    });
    faults.into_iter().next().map_or(Ok(written), Err)
}

/// The leaves of one row, whose positions hold `leaves`, as `projection`
/// reads them.
fn projected(evaluation: &Evaluation<'_>, leaves: Vec<Vec<EngineLeaf>>, constants: &BTreeMap<String, i64>, projection: Projection<'_>) -> Result<Vec<EngineLeaf>, String> {
    let Projection::Positions(columns) = projection else { return Ok(leaves.concat()) };
    let mut row = Vec::new();
    for column in columns {
        for leaf in &leaves[column.position] {
            match leaf {
                EngineLeaf::Ident(ident) if column.minted => {
                    let table = evaluation.session.intern.read().expect("an intern table that no panic poisoned");
                    row.push(EngineLeaf::Written(Leaf::Other(ident_text(&table, evaluation.registry, *ident, constants)?.into())));
                }
                other => row.push(other.clone()),
            }
        }
    }
    Ok(row)
}

/// The text of the set of members that `ident` labels, as the Souffle side
/// writes the id a lib relation mints (`parity.idents.Writer`): a member as
/// `[leaf,leaf,...]` with each Example leaf left out and each Ident leaf as
/// the text of its own set, and the set as `{member,member,...}` with the
/// members sorted by their text. A text for an Ident that labels no set.
fn ident_text(table: &InternTable, registry: &Registry, ident: Ident, constants: &BTreeMap<String, i64>) -> Result<String, String> {
    let Content::Set(set) = table.content(ident) else { return Err("an Ident that a file writes labels no set of members".to_owned()) };
    let mut fields = Vec::new();
    field_types(set.member_type(), &mut fields);
    let mut members = Vec::new();
    for member in set.each() {
        let mut leaves = Vec::new();
        for (&id, ty) in member.iter().zip(&fields) {
            if *ty == ValueType::Example {
                continue;
            }
            for leaf in term_leaves(Term::decode(id, ty), registry, &|name| souffle_number(name, constants))? {
                leaves.push(match leaf {
                    EngineLeaf::Written(Leaf::Number(n)) => n.to_string(),
                    EngineLeaf::Written(Leaf::Other(text)) => text.to_string(),
                    EngineLeaf::Ident(inner) => ident_text(table, registry, inner, constants)?,
                });
            }
        }
        members.push(format!("[{}]", leaves.join(",")));
    }
    members.sort();
    Ok(format!("{{{}}}", members.join(",")))
}

/// The types of the columns that a value of type `ty` takes, a record's
/// fields side by side at every depth.
fn field_types(ty: &ValueType, out: &mut Vec<ValueType>) {
    match ty {
        ValueType::Record(fields) => fields.iter().for_each(|(_, field)| field_types(field, out)),
        other => out.push(other.clone()),
    }
}

/// The leaf of the orientation constant `name` in Souffle's rerun: its
/// number in `constants`.
pub(crate) fn souffle_number(name: &str, constants: &BTreeMap<String, i64>) -> Result<Leaf, String> {
    constants.get(name).map(|&n| Leaf::Number(n)).ok_or_else(|| format!("the orientation constant {name}, which the rerun gives no number"))
}

/// Whether `a` and `b` hold the same rows, each row once.
pub(crate) fn same_rows(a: &[Vec<EngineLeaf>], b: &[Vec<EngineLeaf>]) -> bool {
    fn set(side: &[Vec<EngineLeaf>]) -> StableHashSet<&Vec<EngineLeaf>> {
        side.iter().collect()
    }
    set(a) == set(b)
}
