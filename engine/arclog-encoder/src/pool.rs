//! The expansion of `pool`: the union of a body with a hole bound to each
//! column of a relation of one kind, as
//! `work/feature-spec/feature-spec.md#operators` gives it.
//!
//! Each branch has a column `C`, whose value is the column's identity in the
//! engine, a lib name. So two columns that give one number stay two rows. A
//! branch that the checker refuses is left out.

use arclog::types::ValueType;

use crate::expand::{label_of, unique, Col, Expander, Mark, Rows};
use crate::expression::{Kind, Rel};
use crate::schema::ColumnFacts;

/// A pool in progress, whose hole a branch binds to one column.
#[derive(Clone, Debug)]
pub struct Frame {
    /// The hole, `?x`.
    pub hole: String,
    /// The relation the pool ranges over.
    pub over: Rel,
    /// The name, in that relation, of the column that the hole holds.
    pub column: String,
    /// The relation that stands for `over` where the pool has no branch.
    pub empty: Option<Rows>,
    /// In an enumeration, where no column is bound yet: the kind's type, of a
    /// column that the hole stands for.
    pub open: Option<ValueType>,
}

impl Frame {
    /// The column's name under the hole: `?x` gives `X`.
    pub fn name(&self) -> String {
        label_of(self.hole.trim_start_matches('?'))
    }
}

/// The value type that a kind's name gives.
pub(crate) fn kind_type(name: &str) -> Option<ValueType> {
    Some(match name {
        "Int" | "number" | "Number" => ValueType::Int,
        "Nat" => ValueType::Nat,
        "Color" => ValueType::Color,
        "Example" => ValueType::Example,
        "Unit" => ValueType::Unit,
        "LibName" => ValueType::LibName,
        "Box" => ValueType::Box,
        "Position" => ValueType::Position,
        "Offset" => ValueType::Offset,
        "Ident" => ValueType::OPEN_IDENT,
        "C4" => ValueType::C4,
        "D4" => ValueType::D4,
        "Dir" => ValueType::Dir,
        "DiagDir" => ValueType::DiagDir,
        "Dir8" => ValueType::Dir8,
        "Axis" => ValueType::Axis,
        "DiagAxis" => ValueType::DiagAxis,
        "Axis4" => ValueType::Axis4,
        "Sym" => ValueType::Sym,
        "Sense" => ValueType::Sense,
        _ => return None,
    })
}

/// Whether the column `facts` is of the kind `kind`: its type stands at or
/// under the kind's value type, and it has the lineage roots the kind names.
fn of_kind(facts: &ColumnFacts, kind: &Kind) -> Result<bool, String> {
    match kind {
        Kind::Type(name) => {
            let ty = kind_type(name).ok_or_else(|| format!("`{name}` is no value type"))?;
            Ok(facts.ty.is_below(&ty))
        }
        Kind::LineageRoot(kind, root) => Ok(of_kind(facts, kind)? && facts.roots.iter().any(|held| held == root)),
    }
}

/// The value type of a kind.
fn value_type(kind: &Kind) -> Result<ValueType, String> {
    match kind {
        Kind::Type(name) => kind_type(name).ok_or_else(|| format!("`{name}` is no value type")),
        Kind::LineageRoot(kind, _) => value_type(kind),
    }
}

impl Expander<'_> {
    /// `rows`, with the column of each pool in progress over the relation
    /// `rel` under the hole's name.
    pub(crate) fn under_holes(&self, rel: &Rel, mut rows: Rows) -> Rows {
        for frame in self.frames.iter().filter(|frame| frame.over == *rel) {
            let name = frame.name();
            if let Some(ty) = &frame.open {
                if !rows.columns.iter().any(|column| column.name == name) {
                    rows.columns.push(Col::typed(name, Some(ty.clone())));
                }
                continue;
            }
            let Some(at) = rows.columns.iter().position(|column| column.name == frame.column) else { continue };
            if rows.columns[at].name == name {
                continue;
            }
            // A name already taken takes a suffix.
            if let Some(other) = rows.columns.iter().position(|column| column.name == name) {
                let mut taken: Vec<String> = rows.columns.iter().map(|column| column.name.clone()).collect();
                rows.columns[other].name = unique(&name, &mut taken);
            }
            rows.columns[at].name = name;
        }
        rows
    }

    /// The column that `name` addresses in `rows`: a hole's name where a pool
    /// in progress binds it, under the hole's name, or else the column it holds.
    pub(crate) fn resolved(&self, rows: &Rows, name: &str) -> String {
        if !name.starts_with('?') {
            return name.to_string();
        }
        let Some(frame) = self.frames.iter().rev().find(|frame| frame.hole == name) else { return name.to_string() };
        let under = frame.name();
        if rows.columns.iter().any(|column| column.name == under) { under } else { frame.column.clone() }
    }

    pub(crate) fn resolved_all(&self, rows: &Rows, names: &[String]) -> Vec<String> {
        names.iter().map(|name| self.resolved(rows, name)).collect()
    }

    /// The relation that stands for `over` where a pool in progress has no
    /// branch.
    pub(crate) fn empty_for(&self, rel: &Rel) -> Option<Rows> {
        self.frames.iter().rev().find(|frame| frame.over == *rel).and_then(|frame| frame.empty.clone())
    }

    pub(crate) fn pool(&mut self, hole: &str, over: &Rel, kind: &Kind, body: &Rel) -> Result<Rows, String> {
        // The columns of the relation, from its forms alone.
        let start = self.forms.len();
        let rows = self.rel(over)?;
        let facts = self.tables.columns_of(&self.forms, &rows)?;
        self.forms.truncate(start);
        let mut branches: Vec<(Rows, String)> = Vec::new();
        for column in &rows.columns {
            let Some(found) = facts.iter().find(|facts| facts.path == column.path) else { continue };
            if !of_kind(found, kind)? {
                continue;
            }
            let mark = self.forms.len();
            self.frames.push(Frame { hole: hole.to_string(), over: over.clone(), column: column.name.clone(), empty: None, open: None });
            let branch = self.rel(body);
            let frame = self.frames.pop().expect("the frame of this branch");
            let accepted = match branch {
                Ok(branch) => self.tables.accepts(&self.forms).map(|()| branch).ok(),
                Err(_) => None,
            };
            match accepted {
                Some(branch) => {
                    let renamed = rename_bound(branch, &frame);
                    branches.push((renamed, found.identity.clone()));
                }
                None => self.forms.truncate(mark),
            }
        }
        if branches.is_empty() {
            return self.empty_pool(hole, over, kind, body);
        }
        // Every branch has one set of column names.
        let mut names: Vec<String> = branches[0].0.columns.iter().map(|column| column.name.clone()).collect();
        names.sort();
        for (branch, _) in &branches {
            let mut own: Vec<String> = branch.columns.iter().map(|column| column.name.clone()).collect();
            own.sort();
            if own != names {
                return Err(format!("the branches of a pool have the columns {names:?} and {own:?}, and a body ends in a `project` or a `component`"));
            }
        }
        // `C`, then the body's columns.
        let mut taken = vec!["C".to_string()];
        let labels: Vec<(String, String)> = names.iter().map(|name| (name.clone(), unique(name, &mut taken))).collect();
        let type_of = |name: &str| branches[0].0.columns.iter().find(|column| column.name == name).and_then(|column| column.ty.clone());
        let mut parts = Vec::new();
        for (index, (branch, identity)) in branches.iter().enumerate() {
            let marks: Vec<(usize, Mark)> = branch.columns.iter().enumerate().map(|(at, column)| {
                let label = labels.iter().find(|(name, _)| *name == column.name).expect("a column of one set of names").1.clone();
                (at, if index == 0 { Mark::Fresh(label) } else { Mark::Join(label) })
            }).collect();
            let constant = if index == 0 { "*C" } else { "C" };
            parts.push(format!("({} (lib_name {identity:?} (:Name {constant})))", branch.atom(&marks)));
        }
        let mut columns = vec![Col::typed("C", Some(ValueType::LibName))];
        columns.extend(labels.iter().map(|(name, label)| Col::typed(label.clone(), type_of(name))));
        Ok(self.query(&[format!("(OR {})", parts.join("\n    "))], columns))
    }

    /// A pool with no branch: the hole holds a column of the kind's type over
    /// an empty relation, and the body joins that relation, so the pool has
    /// the body's columns and no rows.
    fn empty_pool(&mut self, hole: &str, over: &Rel, kind: &Kind, body: &Rel) -> Result<Rows, String> {
        let name = label_of(hole.trim_start_matches('?'));
        let none = self.empty_relation(&value_type(kind)?, &name)?;
        self.frames.push(Frame { hole: hole.to_string(), over: over.clone(), column: name.clone(), empty: Some(none.clone()), open: None });
        let branch = self.rel(body);
        self.frames.pop();
        let branch = branch?;
        let mut taken: Vec<String> = Vec::new();
        let marks: Vec<(usize, Mark)> = branch.columns.iter().enumerate().map(|(at, column)| (at, Mark::Fresh(unique(&label_of(&column.name), &mut taken)))).collect();
        let columns: Vec<Col> = marks.iter().map(|(at, mark)| match mark {
            Mark::Fresh(label) => Col::typed(label.clone(), branch.columns[*at].ty.clone()),
            _ => unreachable!("each mark is fresh"),
        }).collect();
        let atom = branch.atom(&marks);
        Ok(self.query(&[atom, none.atom(&[])], columns))
    }

    /// The columns of a pool, with its hole open: `C`, then the body's.
    pub(crate) fn pool_columns(&mut self, hole: &str, over: &Rel, kind: &Kind, body: &Rel) -> Result<Rows, String> {
        let name = label_of(hole.trim_start_matches('?'));
        self.frames.push(Frame { hole: hole.to_string(), over: over.clone(), column: name, empty: None, open: Some(value_type(kind)?) });
        let branch = self.rel(body);
        self.frames.pop();
        let branch = branch?;
        let mut taken = vec!["C".to_string()];
        let mut columns = vec![Col::typed("C", Some(ValueType::LibName))];
        for column in &branch.columns {
            columns.push(Col::typed(unique(&column.name, &mut taken), column.ty.clone()));
        }
        Ok(self.query(&[], columns))
    }

    /// A relation with no rows, and one column `name` of the type `ty`.
    fn empty_relation(&mut self, ty: &ValueType, name: &str) -> Result<Rows, String> {
        let (grid, cell, color) = if self.task_wide { ("ex_input", "(:E *E_0) (:P *P_0) (:Col *Col_0)", "(:E E_0) (:P P_0) (:Col Col_0)") } else { ("input", "(:P *P_0) (:Col *Col_0)", "(:P P_0) (:Col Col_0)") };
        let binder = match ty {
            ValueType::Color => format!("({grid} (:Col *{name}))"),
            ValueType::Position | ValueType::Box => format!("({grid} (:P *{name}))"),
            ValueType::Int => format!("(margin (:B P_0) (:K *{name}))"),
            ValueType::Nat => format!("(sub_extent (:P P_0) (:K *{name}))"),
            ValueType::Offset => format!("(step_offset (:V *{name}))"),
            ValueType::Example if self.task_wide => format!("(ex_input (:E *{name}))"),
            ValueType::Dir => format!("(dir_elem (:D *{name}))"),
            ValueType::DiagDir => format!("(diag_dir_elem (:D *{name}))"),
            ValueType::Dir8 => format!("(dir8_elem (:D *{name}))"),
            ValueType::Axis => format!("(axis_elem (:A *{name}))"),
            ValueType::DiagAxis => format!("(diag_axis_elem (:Da *{name}))"),
            ValueType::Axis4 => format!("(axis4_elem (:A *{name}))"),
            ValueType::D4 => format!("(d4_elem (:D *{name}))"),
            ValueType::C4 => format!("(c4_elem (:D *{name}))"),
            ValueType::Sym => format!("(sym_elem (:S *{name}))"),
            ValueType::Sense => format!("(sense_elem (:S *{name}))"),
            ValueType::LibName => format!("(lib_name \"none\" (:Name *{name}))"),
            ValueType::Ident(_) => {
                let instance = self.fresh();
                let cell_read = if self.task_wide { "(ex_input (:E *E_1) (:P *P))" } else { "(input (:P *P))" };
                self.forms.push(format!("(INIT {instance} Connectivity\n  (node (P)\n    {cell_read}))"));
                format!("({instance}.component (:Id *{name}))")
            }
            other => return Err(format!("no relation holds a column of the type {other:?}, so the pool has no value")),
        };
        let keyword = self.keyword();
        let relation = self.fresh();
        self.forms.push(format!("({keyword} {relation}\n  ({grid} {cell})\n  (NOT ({grid} {color}))\n  {binder})"));
        Ok(Rows { relation, columns: vec![Col::typed(name, Some(ty.clone()))] })
    }
}

/// `rows`, with the column that the frame's hole holds under the hole's name.
fn rename_bound(mut rows: Rows, frame: &Frame) -> Rows {
    let name = frame.name();
    if rows.columns.iter().any(|column| column.name == name) {
        return rows;
    }
    for column in &mut rows.columns {
        if column.name == frame.column {
            column.name = name.clone();
        }
    }
    rows
}
