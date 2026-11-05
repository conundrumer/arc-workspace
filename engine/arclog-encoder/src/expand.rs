//! The expansion of a ground expression into arclog forms, by the rules of
//! `work/feature-spec/feature-spec.md#how-an-expression-expands`. Each
//! operator of the grammar is a primitive of this expander, and a macro of the
//! library names a composition of primitives.
//!
//! What reaches the checker is plain arclog, so the expansion decides nothing
//! that the checker decides: a binding the checker refuses gives forms that it
//! refuses. The expansion refuses only what it cannot write, such as a column
//! that the relation at that node does not have.

use arclog::program::ColumnName;
use arclog::registry::{ColumnType, Component, Column as LibColumn, InputPort, LibEntry, LibName, Macro, Port, Registry};
use arclog::resolver::registry_columns::component;

use crate::expression::{Binding, Column, Feature, Field, Leaf, Op, Operand, Reader, Rel, Written};
use crate::library::{library, HoleKind, Library};
use crate::schema::Tables;

/// The forms of one expression.
#[derive(Clone, Debug)]
pub struct Expanded {
    /// The forms in dependency order, each as text.
    pub forms: Vec<String>,
    /// The relation that the last form gives, which the root's value reads.
    pub export: String,
    /// The columns of that relation.
    pub columns: Vec<String>,
    /// Whether the expression's `QUERY` forms expand to `DET`.
    pub task_wide: bool,
}

/// The mark and the name of a label at a site.
#[derive(Clone, Debug)]
pub(crate) enum Mark {
    Fresh(String),
    Join(String),
    Key(String),
    Zero,
}

impl Mark {
    fn text(&self) -> String {
        match self {
            Mark::Fresh(label) => format!("*{label}"),
            Mark::Join(label) => label.clone(),
            Mark::Key(label) => format!("^{label}"),
            Mark::Zero => "0".to_string(),
        }
    }
}

/// A column of a relation in the expansion.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Col {
    pub(crate) name: String,
    pub(crate) path: Vec<String>,
}

impl Col {
    pub(crate) fn plain(name: impl Into<String>) -> Col {
        let name = name.into();
        Col { path: vec![name.clone()], name }
    }
}

/// A relation that a form can read: its spelling and its columns.
#[derive(Clone, Debug)]
pub struct Rows {
    pub(crate) relation: String,
    pub(crate) columns: Vec<Col>,
}

impl Rows {
    pub(crate) fn index(&self, name: &str) -> Result<usize, String> {
        self.columns.iter().position(|column| column.name == name).ok_or_else(|| {
            let names: Vec<&str> = self.columns.iter().map(|column| column.name.as_str()).collect();
            format!("`{}` has no column `{name}`: its columns are {}", self.relation, names.join(", "))
        })
    }

    /// The atom that reads this relation, with `marks` at the columns they
    /// name, grouped into the sites their paths write.
    pub(crate) fn atom(&self, marks: &[(usize, Mark)]) -> String {
        let mut groups: Vec<(&str, Vec<String>)> = Vec::new();
        for (index, mark) in marks {
            let path = &self.columns[*index].path;
            let inner = match &path[1..] {
                [] => mark.text(),
                [field] => format!("(:{field} {})", mark.text()),
                _ => panic!("a column's path holds at most a record and a field"),
            };
            match groups.iter_mut().find(|(head, _)| *head == path[0]) {
                Some((_, items)) => items.push(inner),
                None => groups.push((&path[0], vec![inner])),
            }
        }
        let sites: Vec<String> = groups.iter().map(|(head, items)| format!("(:{head} {})", items.join(" "))).collect();
        if sites.is_empty() {
            format!("({})", self.relation)
        } else {
            format!("({} {})", self.relation, sites.join(" "))
        }
    }
}

/// A label named by a column: its name with its first letter in upper case,
/// since a field's name is PascalCase.
pub(crate) fn label_of(name: &str) -> String {
    let mut chars = name.chars();
    match chars.next() {
        Some(first) => first.to_uppercase().chain(chars).collect(),
        None => String::new(),
    }
}

/// `name`, with the suffix `_2`, then `_3`, where `taken` holds it, and added
/// to `taken`.
pub(crate) fn unique(name: &str, taken: &mut Vec<String>) -> String {
    let mut held = name.to_string();
    let mut suffix = 2;
    while taken.contains(&held) {
        held = format!("{name}_{suffix}");
        suffix += 1;
    }
    taken.push(held.clone());
    held
}

fn spelled(name: &ColumnName) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => format!("c{slot}"),
    }
}

/// Whether a column of a component is `key`.
fn is_key(column: &LibColumn) -> bool {
    arclog::registry::is_key(column)
}

/// The expansion in progress of one expression.
pub struct Expander<'a> {
    pub(crate) registry: &'a Registry,
    pub(crate) tables: &'a dyn Tables,
    pub(crate) task_wide: bool,
    pub(crate) library: &'a Library,
    pub(crate) forms: Vec<String>,
    pub(crate) next: usize,
    /// The pools in progress, innermost last.
    pub(crate) frames: Vec<crate::pool::Frame>,
}

/// Whether an expression with these leaves is task-wide: a leaf has an Example
/// column, or is a proposer, which reads every example.
fn leaf_is_task_wide(leaf: &Leaf, tables: &dyn Tables) -> bool {
    match leaf {
        Leaf::ExInput | Leaf::ExOutput | Leaf::Proposer(_) => true,
        Leaf::Table(name) => tables.table(name).is_some_and(|schema| schema.has_example),
        Leaf::Input | Leaf::Output | Leaf::Lib(_) | Leaf::Program(_) => false,
    }
}

/// Whether `rel` has a task-wide leaf, in a macro's argument as well.
pub fn rel_is_task_wide(rel: &Rel, tables: &dyn Tables, reader: &Reader<'_>) -> bool {
    let mut found = false;
    rel.each_leaf(&mut |leaf| found |= leaf_is_task_wide(leaf, tables));
    rel.each_call(&mut |name, args| found |= call_is_task_wide(name, args, tables, reader));
    found
}

fn call_is_task_wide(name: &str, args: &[Written], tables: &dyn Tables, reader: &Reader<'_>) -> bool {
    let Some(found) = reader.library.get(name) else { return false };
    found.holes.iter().zip(args).any(|(hole, arg)| {
        matches!(hole.kind, HoleKind::Relation | HoleKind::Grid) && reader.rel_text(&arg.to_string()).is_ok_and(|rel| rel_is_task_wide(&rel, tables, reader))
    })
}

/// Whether the expression `feature` is task-wide.
pub fn feature_is_task_wide(feature: &Feature, tables: &dyn Tables, reader: &Reader<'_>) -> bool {
    match feature {
        Feature::Call(name, args) => call_is_task_wide(name, args, tables, reader),
        _ => feature.relation().is_some_and(|rel| rel_is_task_wide(rel, tables, reader)),
    }
}

fn reader_of(registry: &Registry) -> Reader<'_> {
    Reader { registry, library: library(), program_relations: &crate::program_relations::is_program_relation }
}

/// The forms of the ground expression `feature` over `tables`.
pub fn expand(feature: &Feature, tables: &dyn Tables, registry: &Registry) -> Result<Expanded, String> {
    let task_wide = feature_is_task_wide(feature, tables, &reader_of(registry));
    expand_at(feature, tables, registry, task_wide)
}

/// [`expand`], with the expression read as task-wide where `task_wide` holds.
pub fn expand_at(feature: &Feature, tables: &dyn Tables, registry: &Registry, task_wide: bool) -> Result<Expanded, String> {
    let mut expander = Expander { registry, tables, task_wide, library: library(), forms: Vec::new(), next: 0, frames: Vec::new() };
    let rows = expander.feature(feature)?;
    Ok(Expanded { forms: expander.forms, export: rows.relation, columns: rows.columns.into_iter().map(|column| column.name).collect(), task_wide })
}

/// The forms of the relation `rel`, to read it apart from a root.
pub fn expand_rel(rel: &Rel, tables: &dyn Tables, registry: &Registry, task_wide: bool) -> Result<Expanded, String> {
    let task_wide = task_wide || rel_is_task_wide(rel, tables, &reader_of(registry));
    let mut expander = Expander { registry, tables, task_wide, library: library(), forms: Vec::new(), next: 0, frames: Vec::new() };
    let rows = expander.rel(rel)?;
    // A leaf or a table of the state gives no form, so the read of it does.
    let rows = expander.copy_of(&rows);
    Ok(Expanded { forms: expander.forms, export: rows.relation, columns: rows.columns.into_iter().map(|column| column.name).collect(), task_wide })
}

impl Expander<'_> {
    fn resolved_pairs(&self, left: &Rows, right: &Rows, pairs: &[(Column, Column)]) -> Vec<(Column, Column)> {
        pairs.iter().map(|(l, r)| (self.resolved(left, l), self.resolved(right, r))).collect()
    }

    pub(crate) fn fresh(&mut self) -> String {
        self.next += 1;
        format!("&feature_{}", self.next)
    }

    /// The keyword of a `QUERY` form of this expression.
    pub(crate) fn keyword(&self) -> &'static str {
        if self.task_wide { "DET" } else { "RULE" }
    }

    /// A `QUERY` form with the body `conjuncts`, whose columns are `columns`.
    pub(crate) fn query(&mut self, conjuncts: &[String], columns: Vec<String>) -> Rows {
        let name = self.fresh();
        let keyword = self.keyword();
        self.forms.push(format!("({keyword} {name}\n  {})", conjuncts.join("\n  ")));
        Rows { relation: name, columns: columns.into_iter().map(Col::plain).collect() }
    }

    /// A relation that reads every column of `rows`, under the labels they name.
    fn copy_of(&mut self, rows: &Rows) -> Rows {
        let (marks, labels) = fresh_marks(rows);
        let atom = rows.atom(&marks);
        self.query(&[atom], labels)
    }

    /// The reader of a term that a macro's call writes.
    pub(crate) fn reader(&self) -> Reader<'_> {
        Reader { registry: self.registry, library: self.library, program_relations: &crate::program_relations::is_program_relation }
    }

    fn feature(&mut self, feature: &Feature) -> Result<Rows, String> {
        match feature {
            Feature::Nonempty(rel) => {
                let rows = self.rel(rel)?;
                let atom = rows.atom(&[]);
                Ok(self.query(&[atom], Vec::new()))
            }
            Feature::Cardinality(rel) => {
                let rows = self.rel(rel)?;
                self.cardinality(&rows)
            }
            Feature::ValueSet(rel, cols) => {
                let rows = self.rel(rel)?;
                let cols = self.resolved_all(&rows, cols);
                self.project(&rows, &cols)
            }
            Feature::Call(name, args) => self.call_written(name, args),
        }
    }

    /// The count of the rows of `rows`, over all its columns.
    pub(crate) fn cardinality(&mut self, rows: &Rows) -> Result<Rows, String> {
        let (marks, labels) = fresh_marks(rows);
        let head = if labels.is_empty() { "()".to_string() } else { format!("((:m {}))", labels.join(" ")) };
        let instance = self.fresh();
        self.forms.push(format!("(INIT {instance} Cardinality\n  (member {head}\n    {}))", rows.atom(&marks)));
        Ok(self.query(&[format!("({instance}.size (:N *N))")], vec!["N".to_string()]))
    }

    /// The relation `rel`: the relation of its forms, with the column of each
    /// pool in progress over `rel` under the hole's name.
    pub(crate) fn rel(&mut self, rel: &Rel) -> Result<Rows, String> {
        if let Some(empty) = self.empty_for(rel) {
            return Ok(empty);
        }
        let rows = self.rel_of(rel)?;
        Ok(self.under_holes(rel, rows))
    }

    fn rel_of(&mut self, rel: &Rel) -> Result<Rows, String> {
        match rel {
            Rel::Leaf(leaf) => self.leaf(leaf),
            Rel::Project(inner, cols) => {
                let rows = self.rel(inner)?;
                let cols = self.resolved_all(&rows, cols);
                self.project(&rows, &cols)
            }
            Rel::Select(inner, column, op, operand) => {
                let rows = self.rel(inner)?;
                let column = self.resolved(&rows, column);
                let operand = match operand {
                    Operand::Column(name) => Operand::Column(self.resolved(&rows, name)),
                    Operand::Zero => Operand::Zero,
                };
                self.select(&rows, &column, *op, &operand)
            }
            Rel::Join(left, right, pairs) => {
                let left = self.rel(left)?;
                let right = self.rel(right)?;
                let pairs = self.resolved_pairs(&left, &right, pairs);
                self.join(&left, &right, &pairs)
            }
            Rel::Antijoin(left, right, pairs) => {
                let left = self.rel(left)?;
                let right = self.rel(right)?;
                let pairs = self.resolved_pairs(&left, &right, pairs);
                self.antijoin(&left, &right, &pairs)
            }
            Rel::Union(left, right, pairs) => {
                let left = self.rel(left)?;
                let right = self.rel(right)?;
                let pairs = self.resolved_pairs(&left, &right, pairs);
                self.union(&left, &right, &pairs)
            }
            Rel::LibJoin(inner, name, bindings) => {
                let rows = self.rel(inner)?;
                let bindings: Vec<(String, Column)> = bindings.iter().map(|(lib, column)| (lib.clone(), self.resolved(&rows, column))).collect();
                self.lib_join(&rows, name, &bindings)
            }
            Rel::Component(name, bindings, port) => self.component(name, bindings, port),
            Rel::Pool { hole, over, kind, body } => self.pool(hole, over, kind, body),
            Rel::Call(name, args) => self.call_written(name, args),
        }
    }

    fn grid(&self, per_input: &str, lifted: &str) -> Rows {
        if self.task_wide {
            Rows { relation: lifted.to_string(), columns: vec![Col::plain("E"), Col::plain("P"), Col::plain("Col")] }
        } else {
            Rows { relation: per_input.to_string(), columns: vec![Col::plain("P"), Col::plain("Col")] }
        }
    }

    fn leaf(&mut self, leaf: &Leaf) -> Result<Rows, String> {
        match leaf {
            Leaf::Input => Ok(self.grid("input", "ex_input")),
            Leaf::Output => Ok(self.grid("output", "ex_output")),
            Leaf::ExInput => Ok(Rows { relation: "ex_input".to_string(), columns: vec![Col::plain("E"), Col::plain("P"), Col::plain("Col")] }),
            Leaf::ExOutput => Ok(Rows { relation: "ex_output".to_string(), columns: vec![Col::plain("E"), Col::plain("P"), Col::plain("Col")] }),
            Leaf::Table(name) => self.table(name),
            Leaf::Lib(name) => {
                let columns = self.lib_columns(name).ok_or_else(|| format!("`{name}` is no lib relation"))?;
                Ok(Rows { relation: name.clone(), columns: columns.iter().map(|column| Col::plain(spelled(&column.name))).collect() })
            }
            Leaf::Proposer(name) => {
                let Some(LibEntry::Proposer(proposer)) = self.registry.entry(&LibName(name.as_str().into())) else {
                    return Err(format!("`{name}` is no proposer"));
                };
                let columns: Vec<Col> = proposer.columns.iter().map(|column| Col::plain(spelled(&column.name))).collect();
                let relation = self.fresh();
                // One value: every row over the whole task, or no rows.
                let set = if columns.len() == 1 { " (SET)" } else { "" };
                self.forms.push(format!("(DET {relation} {name}{set})"));
                Ok(Rows { relation, columns })
            }
            Leaf::Program(name) => {
                let fact = arclog::program::ProgramFact::of_name(name).ok_or_else(|| format!("`{name}` is no program relation"))?;
                Ok(Rows { relation: name.clone(), columns: fact.columns().iter().map(|column| Col::plain(*column)).collect() })
            }
        }
    }

    fn lib_columns(&self, name: &str) -> Option<&[LibColumn]> {
        match self.registry.entry(&LibName(name.into()))? {
            LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(&relation.columns),
            _ => None,
        }
    }

    /// A table as this expression reads it: in its lifted form, with a column
    /// `E`, where it is per input and the expression task-wide. A lifted read
    /// cannot read a table's own column named `E`, so a copy holds that column
    /// under `E_2`.
    fn table(&mut self, name: &str) -> Result<Rows, String> {
        let schema = self.tables.table(name).ok_or_else(|| format!("the state has no table `{name}`"))?;
        let mut rows = Rows { relation: name.to_string(), columns: schema.columns.iter().map(|column| Col { name: column.name.clone(), path: column.path.clone() }).collect() };
        if !(self.task_wide && schema.per_input) {
            return Ok(rows);
        }
        if rows.columns.iter().any(|column| column.name == "E") {
            let mut taken = vec!["E".to_string()];
            let labels: Vec<String> = rows.columns.iter().map(|column| unique(&label_of(&column.name), &mut taken)).collect();
            let marks: Vec<(usize, Mark)> = labels.iter().cloned().enumerate().map(|(index, label)| (index, Mark::Fresh(label))).collect();
            let copy = self.fresh();
            self.forms.push(format!("(RULE {copy} {})", rows.atom(&marks)));
            rows = Rows { relation: copy, columns: labels.into_iter().map(Col::plain).collect() };
        }
        rows.columns.insert(0, Col::plain("E"));
        Ok(rows)
    }

    pub(crate) fn project(&mut self, rows: &Rows, cols: &[Column]) -> Result<Rows, String> {
        let mut taken = Vec::new();
        let mut marks = Vec::new();
        let mut labels = Vec::new();
        for name in cols {
            let index = rows.index(name)?;
            if marks.iter().any(|(held, _): &(usize, Mark)| *held == index) {
                return Err(format!("`project` names `{name}` twice"));
            }
            let label = unique(&label_of(name), &mut taken);
            marks.push((index, Mark::Fresh(label.clone())));
            labels.push(label);
        }
        let atom = rows.atom(&marks);
        Ok(self.query(&[atom], labels))
    }

    pub(crate) fn select(&mut self, rows: &Rows, column: &str, op: Op, operand: &Operand) -> Result<Rows, String> {
        let at = rows.index(column)?;
        let mut taken = Vec::new();
        let labels: Vec<String> = rows.columns.iter().map(|column| unique(&label_of(&column.name), &mut taken)).collect();
        let mut marks: Vec<(usize, Mark)> = labels.iter().cloned().enumerate().map(|(index, label)| (index, Mark::Fresh(label))).collect();
        let mut kept: Vec<String> = labels.clone();
        let mut conjuncts = Vec::new();
        match (op, operand) {
            // With `=`, the second column equals the first, so one label stands at both.
            (Op::Eq, Operand::Column(other)) => {
                let second = rows.index(other)?;
                if second != at {
                    marks[second].1 = Mark::Join(labels[at].clone());
                    kept.retain(|label| *label != labels[second]);
                }
                conjuncts.push(rows.atom(&marks));
            }
            // With `=` and `0`, the column's value is known, so the site holds `0`.
            (Op::Eq, Operand::Zero) => {
                marks[at].1 = Mark::Zero;
                kept.retain(|label| *label != labels[at]);
                conjuncts.push(rows.atom(&marks));
            }
            (op, Operand::Column(other)) => {
                let second = rows.index(other)?;
                conjuncts.push(rows.atom(&marks));
                conjuncts.push(format!("({} {} {})", op.text(), labels[at], labels[second]));
            }
            (op, Operand::Zero) => {
                conjuncts.push(rows.atom(&marks));
                conjuncts.push(format!("({} {} 0)", op.text(), labels[at]));
            }
        }
        Ok(self.query(&conjuncts, kept))
    }

    pub(crate) fn join(&mut self, left: &Rows, right: &Rows, pairs: &[(Column, Column)]) -> Result<Rows, String> {
        let mut taken = Vec::new();
        let (left_marks, mut labels, left_labels) = left_reads(left, &mut taken);
        let mut right_marks = Vec::new();
        for (index, column) in right.columns.iter().enumerate() {
            let partners: Vec<&(Column, Column)> = pairs.iter().filter(|(_, r)| *r == column.name).collect();
            match partners[..] {
                [] => {
                    let label = unique(&label_of(&column.name), &mut taken);
                    right_marks.push((index, Mark::Fresh(label.clone())));
                    labels.push(label);
                }
                [(l, _)] => right_marks.push((index, Mark::Join(left_labels[left.index(l)?].clone()))),
                _ => return Err(format!("the pairs of a `join` name the right column `{}` twice", column.name)),
            }
        }
        for (_, r) in pairs {
            right.index(r)?;
        }
        let conjuncts = [left.atom(&left_marks), right.atom(&right_marks)];
        Ok(self.query(&conjuncts, labels))
    }

    pub(crate) fn antijoin(&mut self, left: &Rows, right: &Rows, pairs: &[(Column, Column)]) -> Result<Rows, String> {
        let mut taken = Vec::new();
        let (left_marks, labels, left_labels) = left_reads(left, &mut taken);
        let mut right_marks = Vec::new();
        for (l, r) in pairs {
            right_marks.push((right.index(r)?, Mark::Join(left_labels[left.index(l)?].clone())));
        }
        let conjuncts = [left.atom(&left_marks), format!("(NOT {})", right.atom(&right_marks))];
        Ok(self.query(&conjuncts, labels))
    }

    pub(crate) fn union(&mut self, left: &Rows, right: &Rows, pairs: &[(Column, Column)]) -> Result<Rows, String> {
        let mut taken = Vec::new();
        let (left_marks, labels, left_labels) = left_reads(left, &mut taken);
        if pairs.len() != left.columns.len() || pairs.len() != right.columns.len() {
            return Err("the pairs of a `union` name every column of both relations".to_string());
        }
        let mut right_marks = Vec::new();
        for (l, r) in pairs {
            let index = right.index(r)?;
            if right_marks.iter().any(|(held, _): &(usize, Mark)| *held == index) {
                return Err(format!("the pairs of a `union` name the right column `{r}` twice"));
            }
            right_marks.push((index, Mark::Join(left_labels[left.index(l)?].clone())));
        }
        let body = format!("(OR ({}) ({}))", left.atom(&left_marks), right.atom(&right_marks));
        Ok(self.query(&[body], labels))
    }

    pub(crate) fn lib_join(&mut self, rows: &Rows, name: &str, bindings: &[(String, Column)]) -> Result<Rows, String> {
        let columns = self.lib_columns(name).ok_or_else(|| format!("`{name}` is no lib relation"))?.to_vec();
        let mut taken = Vec::new();
        let (marks, mut labels, row_labels) = left_reads(rows, &mut taken);
        let lib = Rows { relation: name.to_string(), columns: columns.iter().map(|column| Col::plain(spelled(&column.name))).collect() };
        let mut lib_marks = Vec::new();
        for (index, column) in lib.columns.iter().enumerate() {
            let bound: Vec<&(String, Column)> = bindings.iter().filter(|(l, _)| *l == column.name).collect();
            match bound[..] {
                [] => {
                    let label = unique(&label_of(&column.name), &mut taken);
                    lib_marks.push((index, Mark::Fresh(label.clone())));
                    labels.push(label);
                }
                [(_, c)] => lib_marks.push((index, Mark::Join(row_labels[rows.index(c)?].clone()))),
                _ => return Err(format!("`lib-join` binds the column `{}` twice", column.name)),
            }
        }
        for (l, _) in bindings {
            lib.index(l)?;
        }
        let conjuncts = [rows.atom(&marks), lib.atom(&lib_marks)];
        Ok(self.query(&conjuncts, labels))
    }

    /// One output port of a component: the `INIT` form that the bindings
    /// write, and the `QUERY` that labels each column of the port.
    pub(crate) fn component(&mut self, name: &str, bindings: &[Binding], port: &str) -> Result<Rows, String> {
        let registry = self.registry;
        let lib_name = LibName(name.into());
        let component_of: &Component = component(registry, &lib_name).ok_or_else(|| format!("`{name}` is no component"))?;
        let output: &Port = component_of.outputs.iter().find(|output| output.name.0.as_ref() == port).ok_or_else(|| format!("`{name}` has no output `{port}`"))?;
        let mut bound: Vec<BoundInput<'_>> = Vec::new();
        for binding in bindings {
            let input: &InputPort = component_of.inputs.iter().find(|input| input.port.name.0.as_ref() == binding.input).ok_or_else(|| format!("`{name}` has no input `{}`", binding.input))?;
            if input.reads_outputs {
                return Err(format!("the input `{}` of `{name}` reads the instance's outputs, so a binding for it is a program", binding.input));
            }
            let rows = self.rel(&binding.relation)?;
            let binding = Binding {
                input: binding.input.clone(),
                relation: binding.relation.clone(),
                key: self.resolved_all(&rows, &binding.key),
                fields: binding.fields.iter().map(|field| match field {
                    Field::One(name) => Field::One(self.resolved(&rows, name)),
                    Field::Record(names) => Field::Record(self.resolved_all(&rows, names)),
                }).collect(),
            };
            bound.push(BoundInput { input, rows, binding });
        }
        let instance = self.fresh();
        let (form, parameters, key_labels) = component_form(name, component_of, &instance, &bound)?;
        self.forms.push(form);
        // The columns of the port, under the first binding's names.
        let read = Rows {
            relation: format!("{instance}.{port}"),
            columns: port_columns(output, &key_labels, &parameters),
        };
        let mut taken = Vec::new();
        let mut marks = Vec::new();
        let mut labels = Vec::new();
        for (index, column) in read.columns.iter().enumerate() {
            let label = unique(&label_of(&column.name), &mut taken);
            marks.push((index, Mark::Fresh(label.clone())));
            labels.push(label);
        }
        let atom = read.atom(&marks);
        Ok(self.query(&[atom], labels))
    }
}

/// The labels of a read of every column of `left`, added to `taken`: the
/// marks, the labels that become columns, and the label of each column.
fn left_reads(left: &Rows, taken: &mut Vec<String>) -> (Vec<(usize, Mark)>, Vec<String>, Vec<String>) {
    let labels: Vec<String> = left.columns.iter().map(|column| unique(&label_of(&column.name), taken)).collect();
    let marks = labels.iter().cloned().enumerate().map(|(index, label)| (index, Mark::Fresh(label))).collect();
    (marks, labels.clone(), labels)
}

/// The marks of a read of every column of `rows`, and the labels.
fn fresh_marks(rows: &Rows) -> (Vec<(usize, Mark)>, Vec<String>) {
    let mut taken = Vec::new();
    let (marks, labels, _) = left_reads(rows, &mut taken);
    (marks, labels)
}

/// An input of a component, with the relation that writes it.
struct BoundInput<'b> {
    input: &'b InputPort,
    rows: Rows,
    binding: Binding,
}

/// The name of the type parameter at `column`, where its name in the registry
/// is in lower case: the columns such a parameter holds take the names of the
/// columns that its first binding writes.
fn parameter_of(column: &LibColumn) -> Option<&str> {
    let ColumnType::Parameter(parameter) = &column.ty else { return None };
    spelled(&column.name).starts_with(|c: char| c.is_ascii_lowercase()).then_some(&parameter.name)
}

/// The names of the fields of each type parameter, as its first binding wrote
/// them.
type Parameters = Vec<(String, Vec<String>)>;

/// The fields of each column of an input other than `key`, each column by its
/// index in the port, in the registry's order.
fn input_fields<'b>(input: &'b InputPort, binding: &Binding) -> Result<Vec<(&'b LibColumn, Vec<String>)>, String> {
    let columns: Vec<&LibColumn> = input.port.columns.iter().filter(|column| !is_key(column)).collect();
    let flat = |field: &Field| match field {
        Field::One(name) => vec![name.clone()],
        Field::Record(names) => names.clone(),
    };
    match columns[..] {
        [] if binding.fields.is_empty() => Ok(Vec::new()),
        [] => Err(format!("the input `{}` has no column but `key`, so it takes no field", binding.input)),
        // One column: the fields are that column's, and several make a record.
        [column] => Ok(vec![(column, binding.fields.iter().flat_map(flat).collect())]),
        _ if binding.fields.len() != columns.len() => Err(format!("the input `{}` has {} columns other than `key`, and each field fills one", binding.input, columns.len())),
        _ => Ok(columns.iter().copied().zip(binding.fields.iter().map(flat)).collect()),
    }
}

/// The site of `column` in an input's head: the type parameter's column with
/// its labels, each under the first binding's name where the parameter has
/// several columns, or the column with its one label.
fn head_site(column: &LibColumn, labels: &[String], parameters: &Parameters) -> Result<Option<String>, String> {
    let name = spelled(&column.name);
    if labels.is_empty() {
        return Ok(None);
    }
    let Some(parameter) = parameter_of(column) else {
        return match labels {
            [label] => Ok(Some(format!("(:{name} {label})"))),
            _ => Err(format!("the column `{name}` takes one field")),
        };
    };
    let names = &parameters.iter().find(|(held, _)| held == parameter).expect("a binding that writes a parameter's column names it").1;
    if names.len() != labels.len() {
        return Err(format!("the type parameter of `{name}` takes {} fields, as its first binding wrote it, and this binding writes {}", names.len(), labels.len()));
    }
    if let [label] = labels {
        return Ok(Some(format!("(:{name} {label})")));
    }
    let fields: Vec<String> = names.iter().zip(labels).map(|(field, label)| format!("(:{field} {label})")).collect();
    Ok(Some(format!("(:{name} {})", fields.join(" "))))
}

/// The `INIT` form of `bound`, the names of each type parameter's fields, and
/// the labels of the key.
fn component_form(name: &str, declared: &Component, instance: &str, bound: &[BoundInput<'_>]) -> Result<(String, Parameters, Vec<String>), String> {
    // The first binding that has key columns names the key.
    let mut key_labels: Vec<String> = Vec::new();
    if let Some(first) = bound.iter().find(|b| !b.binding.key.is_empty()) {
        let mut taken = Vec::new();
        for column in &first.binding.key {
            first.rows.index(column)?;
            key_labels.push(unique(&label_of(column), &mut taken));
        }
    }
    for b in bound {
        if b.binding.key.is_empty() {
            continue;
        }
        if !b.input.port.columns.iter().any(is_key) {
            return Err(format!("the input `{}` has no `key` column, so it takes no key columns", b.binding.input));
        }
        if b.binding.key.len() != key_labels.len() {
            return Err("the bindings of a component take key columns of one count".to_string());
        }
    }
    // The key clause reads the key columns of each binding that has them.
    let mut branches = Vec::new();
    for (position, b) in bound.iter().filter(|b| !b.binding.key.is_empty()).enumerate() {
        let mut taken = key_labels.clone();
        let mut marks = Vec::new();
        for (column, label) in b.binding.key.iter().zip(&key_labels) {
            let index = b.rows.index(column)?;
            if marks.iter().any(|(held, _): &(usize, Mark)| *held == index) {
                return Err(format!("the key names `{column}` twice"));
            }
            marks.push((index, if position == 0 { Mark::Key(label.clone()) } else { Mark::Join(label.clone()) }));
        }
        // A body that reads a per-input table with no site on `E` makes the
        // instance per input.
        keep_example(&b.rows, &mut marks, &mut taken, position);
        branches.push(b.rows.atom(&marks));
    }
    let key_body = match &branches[..] {
        [] => None,
        [one] => Some(format!("({one})")),
        several => Some(format!("((OR {}))", several.iter().map(|branch| format!("({branch})")).collect::<Vec<_>>().join(" "))),
    };
    // Each input's body, its labels, and the first names of each parameter.
    let mut parameters: Parameters = Vec::new();
    let mut inside: Vec<(usize, String)> = Vec::new();
    let mut after: Vec<(usize, String)> = Vec::new();
    for b in bound {
        let keyed = !b.binding.key.is_empty();
        let held: Vec<String> = if keyed { key_labels.clone() } else { Vec::new() };
        let mut taken = held.clone();
        let mut marks: Vec<(usize, Mark)> = Vec::new();
        if keyed {
            for (column, label) in b.binding.key.iter().zip(&key_labels) {
                marks.push((b.rows.index(column)?, Mark::Join(label.clone())));
            }
        }
        let mut heads = Vec::new();
        for (column, fields) in input_fields(b.input, &b.binding)? {
            let mut labels = Vec::new();
            for field in &fields {
                let index = b.rows.index(field)?;
                let label = match marks.iter().find(|(held, _)| *held == index) {
                    Some((_, Mark::Join(label) | Mark::Fresh(label))) => label.clone(),
                    Some(_) => unreachable!("a body's marks are fresh or joined"),
                    None => {
                        let label = unique(&label_of(field), &mut taken);
                        marks.push((index, Mark::Fresh(label.clone())));
                        label
                    }
                };
                labels.push(label);
            }
            if let Some(parameter) = parameter_of(column) {
                if !parameters.iter().any(|(held, _)| held == parameter) {
                    parameters.push((parameter.to_string(), labels.clone()));
                }
            }
            heads.extend(head_site(column, &labels, &parameters)?);
        }
        keep_example(&b.rows, &mut marks, &mut taken, 0);
        let order = declared.inputs.iter().position(|input| input.port.name == b.input.port.name).expect("a binding's input is one of the component's");
        let text = format!("({} ({})\n      {})", b.binding.input, heads.join(" "), b.rows.atom(&marks));
        if keyed { inside.push((order, text)) } else { after.push((order, text)) }
    }
    inside.sort_by_key(|(order, _)| *order);
    after.sort_by_key(|(order, _)| *order);
    let inside: Vec<String> = inside.into_iter().map(|(_, text)| text).collect();
    let after: Vec<String> = after.into_iter().map(|(_, text)| text).collect();
    let mut form = format!("(INIT {instance} {name}");
    if let Some(body) = key_body {
        form.push_str(&format!("\n  (key {body}\n    {})", inside.join("\n    ")));
    }
    for input in after {
        form.push_str(&format!("\n  {input}"));
    }
    form.push(')');
    Ok((form, parameters, key_labels))
}

/// Adds a site on `E` that makes a label local to the body, where `rows` has
/// an Example column and `marks` holds none.
fn keep_example(rows: &Rows, marks: &mut Vec<(usize, Mark)>, taken: &mut Vec<String>, position: usize) {
    let Ok(index) = rows.index("E") else { return };
    if marks.iter().any(|(held, _)| *held == index) {
        return;
    }
    let label = if position == 0 { unique("E", taken) } else { unique(&format!("E_{}", position + 1), taken) };
    marks.push((index, Mark::Fresh(label)));
}

/// The columns of `output` as a `QUERY` reads them: the key's fields, then the
/// port's other columns. A column of a type parameter takes the names its
/// first binding wrote, and each other column keeps the registry's name.
fn port_columns(output: &Port, key_labels: &[String], parameters: &Parameters) -> Vec<Col> {
    let mut columns: Vec<Col> = Vec::new();
    let mut taken: Vec<String> = Vec::new();
    if output.columns.iter().any(is_key) {
        for label in key_labels {
            let name = unique(label, &mut taken);
            columns.push(Col { name, path: vec!["key".to_string(), label.clone()] });
        }
    }
    for column in output.columns.iter().filter(|column| !is_key(column)) {
        let own = spelled(&column.name);
        match parameter_of(column) {
            None => columns.push(Col { name: unique(&own, &mut taken), path: vec![own] }),
            Some(parameter) => {
                let Some((_, fields)) = parameters.iter().find(|(held, _)| held == parameter) else { continue };
                match &fields[..] {
                    [one] => columns.push(Col { name: unique(one, &mut taken), path: vec![own.clone()] }),
                    fields => {
                        for field in fields {
                            columns.push(Col { name: unique(field, &mut taken), path: vec![own.clone(), field.clone()] });
                        }
                    }
                }
            }
        }
    }
    columns
}
