//! The engine's rows of a lib element, and their comparison with the
//! Souffle record.

use std::collections::BTreeSet;
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;

use arclog::algebra::{algebra, Algebra};
use arclog::eval::instance::Construction;
use arclog::eval::unfold::UnfoldOutput;
use arclog::registry::{AlgebraRelation, Component, LibName, Registry};
use arclog::terms::{Color, Constant, Ident, Margins, Number, Term, TermId};
use arclog::types::ValueType;
use serde_json::{json, Value};

use arclog_constructions::shared as constructions;
use crate::renaming::{renaming_exists, EngineLeaf, Leaf};

use super::components::{constructed, unfolded, WALKS};
use super::inputs::{column_text, is_orientation, relation_type, Element};
use super::last_panic;

impl Element<'_> {
    /// What the engine evaluates the element by, or why it does not.
    pub(super) fn subject(&self) -> Result<Subject<'_>, String> {
        match self {
            Element::Relation { name, relation } => {
                let native = algebra(&LibName(name.clone())).ok_or("the engine does not evaluate it")?;
                Ok(Subject::Relation { name, native, relation })
            }
            Element::Component { name, component } if component.reads_outputs() => {
                Ok(Subject::Unfold { name, component })
            }
            Element::Component { name, component } => {
                let construction = constructions()?.get(&LibName(name.clone())).ok_or("the engine has no construction of it")?;
                Ok(Subject::Component { name, construction, component })
            }
        }
    }
}

/// One value of a row: a value as an inputs file writes it, or an Ident of
/// the engine's, which a Souffle record writes as a number.
#[derive(Clone, PartialEq, Debug)]
pub(super) enum Cell {
    Value(Value),
    Ident(Ident),
}

/// The rows of one mode of a relation or of one output of a component,
/// each row once.
pub(super) type Rows = Vec<Vec<Cell>>;

/// The rows of each part of an element, one value per walk: one walk
/// where the element's inputs give no fork.
pub(super) type Walks = Vec<Vec<Rows>>;

/// The rows of each part of one walk on the two sides of a comparison: the
/// engine's, and the other side's.
pub(super) type Compared = (Vec<Rows>, Vec<Rows>);

/// The cell of the term `id` of type `ty`.
pub(super) fn cell(id: TermId, ty: &ValueType) -> Cell {
    match Term::decode(id, ty) {
        Term::Ident(ident) => Cell::Ident(ident),
        _ => Cell::Value(value_json(id, ty)),
    }
}

/// Adds `row` to `rows` where `rows` does not hold it.
pub(super) fn insert(rows: &mut Rows, row: Vec<Cell>) {
    if !rows.contains(&row) {
        rows.push(row);
    }
}

/// The rows of `rows`, which hold no Ident, each as JSON text.
fn texts(rows: &Rows) -> BTreeSet<String> {
    let value = |cell: &Cell| match cell {
        Cell::Value(value) => value.clone(),
        Cell::Ident(_) => unreachable!("rows compared as text hold no Ident"),
    };
    rows.iter().map(|row| Value::from(row.iter().map(value).collect::<Vec<_>>()).to_string()).collect()
}

/// A value of a row as a leaf of [`renaming_exists`]: an integer, or
/// another value by its JSON text.
fn leaf(value: &Value) -> Leaf {
    value.as_i64().map_or_else(|| Leaf::Other(value.to_string().into()), Leaf::Number)
}

/// What the engine evaluates an element by: a relation's native form, a
/// component's construction, or the walks of `Unfold` for a component
/// whose inputs read its outputs.
pub(super) enum Subject<'r> {
    Relation { name: &'r str, native: &'static dyn Algebra, relation: &'r AlgebraRelation },
    Component { name: &'r str, construction: &'static dyn Construction, component: &'r Component },
    Unfold { name: &'r str, component: &'r Component },
}

impl Subject<'_> {
    pub(super) fn name(&self) -> &str {
        match self {
            Subject::Relation { name, .. } | Subject::Component { name, .. } | Subject::Unfold { name, .. } => name,
        }
    }

    /// The name of the part of the rows at `index`: a relation's mode, or
    /// a component's output.
    pub(super) fn part(&self, index: usize) -> String {
        match self {
            Subject::Relation { .. } => format!("mode {index}"),
            Subject::Component { component, .. } | Subject::Unfold { component, .. } => format!("the output {}", component.outputs[index].name.0),
        }
    }

    /// The engine's rows of each mode of a relation's inputs, or of each
    /// output of a component's on each walk, or the stop of the run or the
    /// panic of an evaluation the engine does not yet give.
    pub(super) fn evaluated(&self, inputs: &Value) -> Result<Walks, String> {
        let run = catch_unwind(AssertUnwindSafe(|| match self {
            Subject::Relation { native, relation, .. } => evaluated(*native, relation, inputs).map(|rows| vec![rows]),
            Subject::Component { construction, component, .. } => constructed(*construction, component, inputs).map(|rows| vec![rows]),
            Subject::Unfold { component, .. } => unfolded(component, inputs),
        }));
        run.unwrap_or_else(|_| Err(format!("a panic at {}", last_panic())))
    }
}

/// The engine's rows of each mode of the relation's inputs, or the stop of
/// the run.
pub(super) fn evaluated(native: &dyn Algebra, relation: &AlgebraRelation, inputs: &Value) -> Result<Vec<Rows>, String> {
    let types: Vec<ValueType> = relation.columns.iter().map(relation_type).collect();
    let mut out = Vec::new();
    for mode in inputs["modes"].as_array().into_iter().flatten() {
        let columns = mode_columns(relation, mode);
        let mut rows = Rows::new();
        for probe in mode["rows"].as_array().into_iter().flatten() {
            let mut bound = vec![None; types.len()];
            for (&column, value) in columns.iter().zip(probe.as_array().into_iter().flatten()) {
                bound[column] = Some(term_id(value, &types[column])?);
            }
            let mut emitted = Vec::new();
            native
                .evaluate(&bound, Registry::get(), &mut |row| emitted.push(row.to_vec()))
                .map_err(|reached| format!("a Box past the margin bound: {:?}", reached.margins))?;
            for row in emitted {
                insert(&mut rows, row.iter().zip(&types).map(|(&id, ty)| cell(id, ty)).collect());
            }
        }
        out.push(rows);
    }
    Ok(out)
}

/// The index of each column of a mode of an inputs file, in the mode's
/// order.
pub(super) fn mode_columns(relation: &AlgebraRelation, mode: &Value) -> Vec<usize> {
    let names = mode["mode"].as_array().into_iter().flatten().filter_map(Value::as_str);
    names.map(|name| relation.columns.iter().position(|c| column_text(&c.name) == name).expect("a mode's column is a column of its relation")).collect()
}

/// The term id of an inputs file's `value` at type `ty`.
pub(super) fn term_id(value: &Value, ty: &ValueType) -> Result<TermId, String> {
    let term = match (ty, value) {
        (ValueType::Box, Value::Array(m)) => {
            let margin = |i: usize| m.get(i).and_then(Value::as_i64).map(|n| n as i32).ok_or_else(|| format!("{value} is no Box"));
            Term::Box(Margins { top: margin(0)?, bottom: margin(1)?, left: margin(2)?, right: margin(3)? })
        }
        (ValueType::Color, Value::Number(n)) => {
            let digit = n.as_u64().and_then(|d| u8::try_from(d).ok()).and_then(Color::from_digit).ok_or_else(|| format!("{value} is no color"))?;
            Term::Constant(Constant::Color(digit))
        }
        (_, Value::String(name)) if is_orientation(ty) => {
            Term::Constant(Constant::Orientation(Registry::get().orientation_constant(name).ok_or_else(|| format!("{name} is no constant"))?))
        }
        (_, Value::Number(n)) => Term::Number(Number(n.as_i64().ok_or_else(|| format!("{value} is no number"))? as i32)),
        _ => return Err(format!("{value} is no value of {ty:?}")),
    };
    term.encode().map_err(|reached| format!("a Box past the margin bound: {:?}", reached.margins))
}

pub(crate) fn value_json(id: TermId, ty: &ValueType) -> Value {
    match Term::decode(id, ty) {
        Term::Number(Number(n)) => Value::from(n),
        Term::Box(m) => json!([m.top, m.bottom, m.left, m.right]),
        Term::Constant(Constant::Color(color)) => Value::from(color.digit()),
        Term::Constant(Constant::Orientation(c)) => Value::from(Registry::get().constant_name(c)),
        other => Value::from(format!("{other:?}")),
    }
}

/// Each line on a difference between the engine's rows of `subject` and
/// `other`'s, by mode or by output. Where a side's rows hold an Ident, they
/// agree where one renaming of the engine's Idents onto the other side's
/// makes the rows of every part agree, as [`renaming_exists`] gives.
pub(super) fn differences(subject: &Subject<'_>, other: &str, engine: &[Rows], expected: &[Rows]) -> Vec<String> {
    let name = subject.name();
    if engine.len() != expected.len() {
        return vec![format!("{name}: the engine gives {} parts, {other} {}", engine.len(), expected.len())];
    }
    if engine.iter().chain(expected).flatten().flatten().any(|cell| matches!(cell, Cell::Ident(_))) {
        return renamed_differences(subject, other, engine, expected);
    }
    let mut lines = Vec::new();
    for (index, (got, want)) in engine.iter().zip(expected).enumerate() {
        let (got, want) = (texts(got), texts(want));
        let extra: Vec<&String> = got.difference(&want).collect();
        let missing: Vec<&String> = want.difference(&got).collect();
        if !extra.is_empty() || !missing.is_empty() {
            lines.push(format!(
                "{name}, {}: against {other}, the engine gives {} rows {other} lacks, such as {}, and lacks {} rows, such as {}",
                subject.part(index),
                extra.len(),
                extra.first().map_or("none", |r| r.as_str()),
                missing.len(),
                missing.first().map_or("none", |r| r.as_str())
            ));
        }
    }
    lines
}

/// The line on rows that hold Idents where no one renaming of the engine's
/// Idents makes them agree with `expected`'s. An Ident of `expected`, a
/// Souffle record's, takes a number of its own.
fn renamed_differences(subject: &Subject<'_>, other: &str, engine: &[Rows], expected: &[Rows]) -> Vec<String> {
    let mut numbered: Vec<Ident> = Vec::new();
    let mut theirs: Vec<BTreeSet<Vec<Leaf>>> = Vec::new();
    for rows in expected {
        let mut set = BTreeSet::new();
        for row in rows {
            let mut leaves = Vec::new();
            for cell in row {
                leaves.push(match cell {
                    Cell::Value(value) => leaf(value),
                    Cell::Ident(ident) => {
                        let at = numbered.iter().position(|i| i == ident).unwrap_or_else(|| {
                            numbered.push(*ident);
                            numbered.len() - 1
                        });
                        Leaf::Number(at as i64)
                    }
                });
            }
            set.insert(leaves);
        }
        theirs.push(set);
    }
    let ours = engine.iter().map(|rows| {
        rows.iter()
            .map(|row| {
                row.iter()
                    .map(|cell| match cell {
                        Cell::Value(value) => EngineLeaf::Written(leaf(value)),
                        Cell::Ident(ident) => EngineLeaf::Ident(*ident),
                    })
                    .collect()
            })
            .collect()
    });
    let relations: Vec<(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)> = theirs.iter().zip(ours).collect();
    if renaming_exists(&relations) {
        return Vec::new();
    }
    let counts = |parts: &[Rows]| parts.iter().map(Vec::len).map(|n| n.to_string()).collect::<Vec<_>>().join(", ");
    vec![format!(
        "{}: against {other}, no one renaming of Idents makes the rows agree: by part, the engine gives {} rows, {other} {}",
        subject.name(),
        counts(engine),
        counts(expected)
    )]
}

/// Each line on a difference between the engine's rows and the Souffle
/// record's on each walk of `walks`, over the rows [`reached`] keeps, each
/// line led by its walk where there are several.
pub(super) fn walk_differences(subject: &Subject<'_>, other: &str, walks: &[Compared]) -> Vec<String> {
    let mut lines = Vec::new();
    for (index, (walk, expected)) in walks.iter().enumerate() {
        let (walk, expected) = reached(subject, walk, expected);
        let found = differences(subject, other, &walk, &expected);
        match walks.len() {
            1 => lines.extend(found),
            n => lines.extend(found.into_iter().map(|line| format!("walk {} of {n}: {line}", index + 1))),
        }
    }
    lines
}

/// The rows of `engine` and of the Souffle record's `souffle` that their
/// comparison compares. For `Unfold`, a `take` row stands only at a key and
/// cursor where a side holds a `taken`, `untaken` or `excluded` row, and
/// the other outputs stand in full: the outputs of `Unfold` are the state
/// along a walk, as the Unfold row of `docs/lib-spec.md` gives,
/// while the `take` of Souffle's `Take` holds each given `take` row at
/// every cursor, also at one that no walk reaches.
fn reached(subject: &Subject<'_>, engine: &[Rows], souffle: &[Rows]) -> (Vec<Rows>, Vec<Rows>) {
    let Subject::Unfold { component, .. } = subject else { return (engine.to_vec(), souffle.to_vec()) };
    let outputs: Vec<UnfoldOutput> = component.outputs.iter().map(|output| UnfoldOutput::of(&output.name)).collect();
    let held = |rows: &[Rows]| -> Vec<Vec<Cell>> {
        outputs.iter().zip(rows).filter(|(output, _)| **output != UnfoldOutput::Take).flat_map(|(_, rows)| rows.iter().map(|row| row[..2].to_vec())).collect()
    };
    let reached: Vec<Vec<Cell>> = held(engine).into_iter().chain(held(souffle)).collect();
    let keep = |rows: &[Rows]| -> Vec<Rows> {
        outputs
            .iter()
            .zip(rows)
            .map(|(output, rows)| match output {
                UnfoldOutput::Take => rows.iter().filter(|row| reached.iter().any(|at| at[..] == row[..2])).cloned().collect(),
                _ => rows.clone(),
            })
            .collect()
    };
    (keep(engine), keep(souffle))
}

/// The line that lists the fork of the inputs file `path` of `subject`
/// into `walks`, with the rows of each part on each walk.
pub(super) fn fork_line(subject: &Subject<'_>, path: &Path, walks: &[Vec<Rows>]) -> String {
    let limit = if walks.len() >= WALKS { ", the limit" } else { "" };
    let text = |row: &Vec<Cell>| {
        let cells: Vec<String> = row
            .iter()
            .map(|cell| match cell {
                Cell::Value(value) => value.to_string(),
                Cell::Ident(ident) => format!("{ident:?}"),
            })
            .collect();
        format!("[{}]", cells.join(","))
    };
    let walks: Vec<String> = walks
        .iter()
        .enumerate()
        .map(|(index, parts)| {
            let parts: Vec<String> = parts
                .iter()
                .enumerate()
                .map(|(at, rows)| format!("{} {}", subject.part(at), rows.iter().map(text).collect::<Vec<_>>().join(" ")))
                .collect();
            format!("walk {}: {}", index + 1, parts.join("; "))
        })
        .collect();
    format!("{}: the inputs {} fork into {} walks{limit}: {}", subject.name(), path.display(), walks.len(), walks.join(" | "))
}
