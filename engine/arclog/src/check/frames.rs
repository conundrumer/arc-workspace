//! The grids that a label's values stand in, which the type rules with a
//! `same-frame` condition read ([`crate::registry::TypeRule`]).
//!
//! A [`Grid`] is the input or the output of one example: `Current` is the
//! example a per-input form runs on (`docs/arclog/arclog.md#program`: the
//! engine lifts every `RULE` relation and instance over the examples), and
//! `Label(E)` is the example that the label `E` holds. A grid holds of a
//! label where, in every row of the label's form, its value stands in that
//! grid. One grid has one extent, so two labels share a frame where a grid
//! holds of both.
//!
//! The sources of a label are, in a body, the sites that bind it, with the
//! sites of the labels an `=` makes equal to it, and every branch of an `OR`
//! or an `IF` that binds it is chosen in turn, as the frame flows of the
//! tables export take them
//! (`engine/arclog-tables/src/flows.rs`), with the example kept:
//!
//! - `input` gives `Grid(Input, Current)` at its `P`; `ex_input E` and
//!   `ex_output E` give `Grid(Input, Label(E))` and `Grid(Output, Label(E))`
//!   at their `P`, and none where `E` is no label.
//! - A read of a program relation's column gives that column's grids, with
//!   `Current` replaced by the label at the read's Example site, and each of
//!   the relation's Example columns by the label at that column. A lifted read
//!   whose Example site holds no label gives none of the grids that name
//!   `Current`.
//! - A read of an instance output's column gives, where
//!   [`crate::registry::Registry::output_frame`]'s rule makes no frame, the
//!   grids that hold, in the instance's bodies, of the label at each input
//!   column the rule names, with each key label replaced by the label at the
//!   reading site's key field. A rule that makes a frame gives none.
//! - A lib atom's computed column gives, where
//!   [`crate::registry::Registry::relation_frame`] makes no frame, the grids
//!   that hold of each label at a bound column the rule names, other than a
//!   label of type `Offset`. A site of a column that every mode of the atom's
//!   relation binds is no source. A constant is a source that gives none.
//!
//! A grid holds of a label where each of its sources gives it, or where the
//! type of each source's site is `Position` and one gives it: a value that is
//! a cell of two grids shows that they have one extent. The grids of a label
//! over the alternatives of its `OR` and `IF` branches are those that hold in
//! each. A source of a kind not listed, or past the work bound
//! ([`WORK_BOUND`]), gives none, so every omission leaves the label with
//! fewer grids.
//!
//! A column of a program relation has the grids that hold of its head label
//! in every form and clause that gives it, written over `Current` and the
//! relation's Example columns; a `CHOOSE`, `RIGID_DET`, `DEMO_RULE` or
//! demonstrated column has none. The type check reads them lazily from the
//! forms that give them, from the form's final types, and a read through a
//! cycle of forms gives none.
//!
//! The grids of a label read the types of the labels, from the last run of
//! the settle loop of [`super::inference::Inference::infer_new`]. A narrower
//! type only adds grids: a `Position` source joins grids, and an `Offset`
//! label drops out of a computed column's named labels.

use std::cell::{Cell, RefCell};

use super::inference::{cached_unless_cycle, field_label, Inference, ScopeBody, ScopeOwner, SiteReading, SiteUse};
use super::types::{scope_forms, PoseOr};
use crate::eval::ir::atom_modes;
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::{written_inputs, Atom, Body, ColumnName, Conjunct, ConstraintOp, FactRelation, Form, LabelId, Node, Operand, PortName, ProgramRelation, RelationRef, Site};
use crate::registry::{Column, FrameColumn, Mode};
use crate::resolver::columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution};
use crate::types::{column_label, typed, use_label, ValueType};

/// The number of alternatives that the walk of one label's grids chooses
/// among its `OR` and `IF` branches, past which the label has no grids.
const WORK_BOUND: usize = 512;

/// Whether a grid is an example's input or its output.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum GridKind {
    Input,
    Output,
}

/// A grid: the input or the output of the example `example`.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(super) struct Grid<E> {
    kind: GridKind,
    example: E,
}

/// The example of a grid in a form.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum Example {
    /// The example that a per-input form runs on.
    Current,
    /// The example that a label holds.
    Label(LabelId),
}

/// The example of a grid of a relation's column, over the relation's columns.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(super) enum ColumnExample {
    Current,
    /// The example that the relation's column of this name holds.
    Column(ColumnName),
    /// The example that the key column of this name of an instance's output
    /// holds.
    Key(ColumnName),
}

/// The grids that hold of a label.
type Grids = Vec<Grid<Example>>;

/// The grids of a relation's column.
type ColumnGrids = Vec<Grid<ColumnExample>>;

/// Whether two labels of a form stand in one grid, as the type rules'
/// `same-frame` condition reads it.
pub(super) trait SharedGrids {
    fn share(&self, a: LabelId, b: LabelId) -> bool;
}

/// The grids of the columns of the relations that one inference's forms
/// give, each read once.
#[derive(Debug, Default)]
pub(super) struct GridCache {
    /// A key is a clause, by its path, and a column.
    clauses: RefCell<StableHashMap<(NodePath, ColumnName), ColumnGrids>>,
    /// A key is an `INIT` form, by its path, an output and a column.
    outputs: RefCell<StableHashMap<(NodePath, PortName, ColumnName), ColumnGrids>>,
}

/// The grids in each of `sets`, none for no set.
fn intersect_all<E: Clone + PartialEq>(sets: impl IntoIterator<Item = Vec<Grid<E>>>) -> Vec<Grid<E>> {
    sets.into_iter().reduce(|a, b| a.into_iter().filter(|grid| b.contains(grid)).collect()).unwrap_or_default()
}

/// The grids in `a`, then those of `b` it lacks.
fn union<E: Clone + PartialEq>(mut a: Vec<Grid<E>>, b: Vec<Grid<E>>) -> Vec<Grid<E>> {
    for grid in b {
        if !a.contains(&grid) {
            a.push(grid);
        }
    }
    a
}

/// What gives a label values at one site, or in one branch.
struct Source {
    grids: Grids,
    /// Whether the site's type is `Position`.
    position: bool,
}

/// The grids that a label has, from its sources: those every source gives, or,
/// where each source's site is `Position`, those one gives.
fn combine(sources: Vec<Source>) -> Grids {
    let all_position = sources.iter().all(|source| source.position);
    let grids = sources.into_iter().map(|source| source.grids);
    if all_position {
        grids.reduce(union).unwrap_or_default()
    } else {
        intersect_all(grids)
    }
}

/// What a body binds once a branch of each `OR` and `IF` is chosen: its
/// positive atoms, its `=` comparisons and the forms not yet chosen.
#[derive(Clone, Default)]
struct Alternative<'b> {
    atoms: Vec<&'b Atom>,
    /// `(= first second)`, with `None` for `0`.
    equal: Vec<(LabelId, Option<LabelId>)>,
    pending: Vec<Pending<'b>>,
}

/// An `OR` or an `IF` that an alternative has not chosen a branch of.
#[derive(Clone)]
enum Pending<'b> {
    Or(&'b [Node<Body>]),
    If { test: &'b Body, then: &'b Body, otherwise: &'b Body },
}

impl<'b> Pending<'b> {
    /// The bodies of each choice: a branch of an `OR`, and the test with the
    /// then, or the else, of an `IF`.
    fn choices(&self) -> Vec<Vec<&'b Body>> {
        match self {
            Pending::Or(branches) => {
                let branches: &'b [Node<Body>] = branches;
                branches.iter().map(|branch| vec![branch.value()]).collect()
            }
            Pending::If { test, then, otherwise } => vec![vec![*test, *then], vec![*otherwise]],
        }
    }
}

impl<'b> Alternative<'b> {
    /// Adds what `body` binds: a `NOT` and an `ALL` bind nothing.
    fn add(&mut self, body: &'b Body) {
        for conjunct in body.conjuncts.iter() {
            match conjunct {
                Conjunct::Atom(atom) => self.atoms.push(atom.value()),
                Conjunct::Constraint(constraint) if constraint.op == ConstraintOp::Eq => {
                    let second = match constraint.second {
                        Operand::Label(label) => Some(label.label),
                        Operand::Zero => None,
                    };
                    self.equal.push((constraint.first.label, second));
                }
                Conjunct::Or(branches) => self.pending.push(Pending::Or(branches)),
                Conjunct::If { test, then, otherwise } => self.pending.push(Pending::If { test: test.value(), then: then.value(), otherwise: otherwise.value() }),
                Conjunct::Constraint(_) | Conjunct::Not(_) | Conjunct::All { .. } => {}
            }
        }
    }

    /// The labels that the `=` comparisons make equal to `label`, `label`
    /// included, and whether one is made equal to `0`.
    fn class_of(&self, label: LabelId) -> (Vec<LabelId>, bool) {
        let mut class = vec![label];
        let mut zero = false;
        let mut grown = true;
        while std::mem::take(&mut grown) {
            for (first, second) in &self.equal {
                match second {
                    None => {
                        if class.contains(first) && !zero {
                            zero = true;
                            grown = true;
                        }
                    }
                    Some(second) => {
                        let (has_first, has_second) = (class.contains(first), class.contains(second));
                        if has_first != has_second {
                            class.push(if has_first { *second } else { *first });
                            grown = true;
                        }
                    }
                }
            }
        }
        (class, zero)
    }
}

/// The grids of the labels of one form, from the types `reading` gives the
/// labels.
pub(super) struct FormGrids<'g, 'a> {
    inference: &'g Inference<'a>,
    /// The types of the form's labels, with no grids: the type of a site that
    /// a source stands at is read without them.
    reading: SiteReading<'g, 'a>,
    /// The form's labels, with the body each is bound in.
    scope: &'g ScopeBody<'a>,
    memo: RefCell<StableHashMap<LabelId, Grids>>,
    /// The label uses of each atom of the form.
    uses: StableHashMap<*const Atom, Vec<&'g SiteUse<'a>>>,
    /// The alternatives the walk of the label asked may still choose.
    work: Cell<usize>,
}

impl SharedGrids for FormGrids<'_, '_> {
    fn share(&self, a: LabelId, b: LabelId) -> bool {
        let (a, b) = (self.grids(a), self.grids(b));
        a.iter().any(|grid| b.contains(grid))
    }
}

impl<'g, 'a> FormGrids<'g, 'a> {
    /// The grids of the labels of the form that `scope` gives, read under
    /// `reading`.
    pub fn new(inference: &'g Inference<'a>, reading: SiteReading<'g, 'a>, scope: &'g ScopeBody<'a>) -> Self {
        let reading = SiteReading { grids: None, ..reading };
        let mut uses: StableHashMap<*const Atom, Vec<&'g SiteUse<'a>>> = StableHashMap::default();
        for site in &reading.walk.uses {
            if let Some(atom) = site.atom {
                uses.entry(atom as *const Atom).or_default().push(site);
            }
        }
        FormGrids { inference, reading, scope, memo: RefCell::default(), uses, work: Cell::new(WORK_BOUND) }
    }

    /// The grids that hold of `label`.
    pub fn grids(&self, label: LabelId) -> Grids {
        if let Some(found) = self.memo.borrow().get(&label) {
            return found.clone();
        }
        let found = self.in_body(self.scope.lists(&[label])[0], label);
        self.memo.borrow_mut().insert(label, found.clone());
        found
    }

    /// The grids that hold of `label` in the rows that `body` binds.
    pub fn in_body(&self, body: &'g Body, label: LabelId) -> Grids {
        self.work.set(WORK_BOUND);
        let mut alternative = Alternative::default();
        alternative.add(body);
        self.in_alternative(alternative, label, &mut Vec::new())
    }

    /// The label uses of `atom`.
    fn uses_of(&self, atom: &Atom) -> &[&'g SiteUse<'a>] {
        self.uses.get(&(atom as *const Atom)).map_or(&[], |uses| &uses[..])
    }

    /// Whether `body`, or a branch in it, binds a label of `class`: it holds a
    /// positive atom with a site on one, or an `=` comparison of one.
    fn touches(&self, body: &Body, class: &[LabelId]) -> bool {
        body.conjuncts.iter().any(|conjunct| match conjunct {
            Conjunct::Atom(atom) => self.uses_of(atom.value()).iter().any(|site| class.contains(&site.label)),
            Conjunct::Constraint(constraint) if constraint.op == ConstraintOp::Eq => {
                class.contains(&constraint.first.label) || matches!(constraint.second, Operand::Label(second) if class.contains(&second.label))
            }
            Conjunct::Or(branches) => branches.iter().any(|branch| self.touches(branch.value(), class)),
            Conjunct::If { test, then, otherwise } => [test, then, otherwise].iter().any(|part| self.touches(part.value(), class)),
            Conjunct::Constraint(_) | Conjunct::Not(_) | Conjunct::All { .. } => false,
        })
    }

    /// The alternatives of `alternative` that choose a branch of each form
    /// that touches the class of `label`, as the class grows, or `None` past
    /// the work bound.
    fn expand<'b>(&self, alternative: Alternative<'b>, label: LabelId) -> Option<Vec<Alternative<'b>>> {
        let (class, _) = alternative.class_of(label);
        let touching = |pending: &Pending<'b>| pending.choices().iter().flatten().any(|body| self.touches(body, &class));
        let Some(index) = alternative.pending.iter().position(touching) else { return Some(vec![alternative]) };
        let mut rest = alternative;
        let pending = rest.pending.remove(index);
        let mut expanded = Vec::new();
        for choice in pending.choices() {
            self.work.set(self.work.get().checked_sub(1)?);
            let mut chosen = rest.clone();
            for body in choice {
                chosen.add(body);
            }
            expanded.extend(self.expand(chosen, label)?);
        }
        Some(expanded)
    }

    /// The grids that hold of `label` in every alternative of `alternative`
    /// that chooses a branch of each form that binds it. `visiting` holds the
    /// labels whose grids are being read above.
    fn in_alternative(&self, alternative: Alternative<'_>, label: LabelId, visiting: &mut Vec<LabelId>) -> Grids {
        if visiting.contains(&label) {
            return Vec::new();
        }
        let Some(alternatives) = self.expand(alternative, label) else { return Vec::new() };
        intersect_all(alternatives.iter().map(|chosen| self.in_chosen(chosen, label, visiting)))
    }

    /// The grids that hold of `label` in `alternative`, whose forms are
    /// chosen: those of its sources.
    fn in_chosen(&self, alternative: &Alternative<'_>, label: LabelId, visiting: &mut Vec<LabelId>) -> Grids {
        let (class, zero) = alternative.class_of(label);
        let mut sources = Vec::new();
        if zero {
            sources.push(Source { grids: Vec::new(), position: false });
        }
        let before = visiting.len();
        visiting.extend(class.iter().copied());
        for atom in &alternative.atoms {
            for site in self.uses_of(atom).iter().filter(|site| class.contains(&site.label)) {
                sources.extend(self.source(atom, &site.column, alternative, visiting));
            }
        }
        visiting.truncate(before);
        combine(sources)
    }

    /// The source that the site of `atom` on the column path `path` is for the
    /// label that stands there, or `None` where the site binds no value.
    fn source(&self, atom: &Atom, path: &[ColumnName], alternative: &Alternative<'_>, visiting: &mut Vec<LabelId>) -> Option<Source> {
        if let RelationRef::DefinedPort(_) = atom.relation {
            return None;
        }
        let position = self.inference.site_type(self.reading, atom, path) == Some(ValueType::Position);
        let none = Source { grids: Vec::new(), position };
        let Some((inference, at)) = self.inference.atom_place(self.reading, atom) else { return Some(none) };
        let [column] = path else { return Some(none) };
        match inference.program().resolution(&at) {
            Some(Resolution::Lib(name)) => {
                let modes = atom_modes(inference.registry(), atom);
                if !modes.is_empty() && modes.iter().all(|mode| mode.bound.contains(column)) {
                    return None;
                }
                let grids = self.lib_grids(atom, name, column, modes, alternative, visiting);
                Some(Source { grids, position })
            }
            Some(Resolution::Node(node)) => Some(Source { grids: self.read_grids(inference, atom, &at, *node, column), position }),
            _ => Some(none),
        }
    }

    /// The grids that the read `atom` at `at`, of the relation of `node`,
    /// gives its site on `column`.
    fn read_grids(&self, inference: &Inference<'a>, atom: &Atom, at: &NodePath, node: GraphNodeIndex, column: &ColumnName) -> Grids {
        let graph_node = &inference.program().graph.nodes[node.0 as usize];
        let lifted = inference.program().reads_lifted(at);
        let own = |grids: ColumnGrids| -> Grids {
            let place = |grid: Grid<ColumnExample>| {
                let example = match grid.example {
                    ColumnExample::Current if lifted => Example::Label(column_label(atom, &columns::example())?),
                    ColumnExample::Current => Example::Current,
                    ColumnExample::Column(name) => Example::Label(column_label(atom, &name)?),
                    ColumnExample::Key(name) => Example::Label(field_label(atom, &columns::key(), &name)?),
                };
                Some(Grid { kind: grid.kind, example })
            };
            grids.into_iter().filter_map(place).collect()
        };
        match &graph_node.kind {
            DependencyKind::Fact(fact) => {
                if !inference.registry().fact_columns(*fact).iter().find(|own| own.name == *column).is_some_and(Column::has_frame) {
                    return Vec::new();
                }
                let example = || column_label(atom, &columns::example()).map(Example::Label);
                match fact {
                    FactRelation::Input => vec![Grid { kind: GridKind::Input, example: Example::Current }],
                    FactRelation::ExInput => example().map(|example| Grid { kind: GridKind::Input, example }).into_iter().collect(),
                    FactRelation::ExOutput => example().map(|example| Grid { kind: GridKind::Output, example }).into_iter().collect(),
                }
            }
            DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => own(inference.relation_column_grids(node, relation, column)),
            DependencyKind::InstanceOutput { output, .. } => own(inference.instance_output_grids(inference.program().form_of(node), output, column)),
            _ => Vec::new(),
        }
    }

    /// The grids that a lib atom `atom` of the relation `name`, whose `modes`
    /// are given, computes at `column`: those that hold of each label, other
    /// than one of type `Offset`, at a column that a mode which leaves
    /// `column` unbound binds, where the registry's frame rule names that
    /// column and makes no frame. A mode with a bound column that has no label
    /// is not used.
    fn lib_grids(&self, atom: &Atom, name: &crate::registry::LibName, column: &ColumnName, modes: &[Mode], alternative: &Alternative<'_>, visiting: &mut Vec<LabelId>) -> Grids {
        let registry = self.inference.registry();
        let computing = modes.iter().filter(|mode| !mode.bound.contains(column));
        let grids_of = |mode: &Mode, visiting: &mut Vec<LabelId>| -> Option<Grids> {
            let labels: Vec<(&ColumnName, LabelId)> = mode.bound.iter().map(|bound| Some((bound, column_label(atom, bound)?))).collect::<Option<_>>()?;
            let rule = registry.relation_frame(name, mode, column).filter(|rule| !rule.makes);
            let named = labels.iter().filter(|(bound, _)| rule.as_ref().is_some_and(|rule| rule.names(None, bound)));
            let from = named.filter(|(_, label)| typed(self.reading.labels, *label) != Some(ValueType::Offset));
            Some(intersect_all(from.map(|(_, label)| self.in_alternative(alternative.clone(), *label, visiting))))
        };
        intersect_all(computing.filter_map(|mode| grids_of(mode, visiting)))
    }
}

/// The label at `site`, where it holds one bare label.
fn site_label(site: &Site) -> Option<LabelId> {
    match &site.value.args[..] {
        [arg] => arg.label().and_then(use_label),
        _ => None,
    }
}

impl<'a> Inference<'a> {
    /// The grids of the column `column` of the relation `relation` of `node`,
    /// a relation of clauses: those that hold in every clause.
    pub(super) fn relation_column_grids(&self, node: GraphNodeIndex, relation: &ProgramRelation, column: &ColumnName) -> ColumnGrids {
        let scope = &self.program().graph.nodes[node.0 as usize].scope;
        let (scope_at, forms) = scope_forms(self.program().program.value(), scope);
        let clauses = forms.filter_map(|(index, form)| match form {
            Form::Clause(clause) if clause.value().derives == *relation => Some((index, clause.value())),
            _ => None,
        });
        intersect_all(clauses.map(|(index, clause)| self.clause_column_grids(&scope_at.child(index), clause, column)))
    }

    /// The grids that hold of the label at `column` of `clause`, the clause at
    /// `at`, written over the clause's columns.
    fn clause_column_grids(&self, at: &NodePath, clause: &crate::program::Clause, column: &ColumnName) -> ColumnGrids {
        let read = || {
            let head = clause.columns.iter().find(|own| own.name == *column)?.label;
            let inferred = self.infer(at)?;
            let ScopeOwner::Form(form) = inferred.owner else { return None };
            let scope = ScopeBody::of(form, self.registry());
            let grids = FormGrids::new(self, inferred.reading(PoseOr::Open), &scope);
            let placed = |grid: Grid<Example>| {
                let example = match grid.example {
                    Example::Current => ColumnExample::Current,
                    Example::Label(label) => ColumnExample::Column(clause.columns.iter().find(|own| own.label == label)?.name.clone()),
                };
                Some(Grid { kind: grid.kind, example })
            };
            Some(grids.grids(head).into_iter().filter_map(placed).collect())
        };
        let cache = &self.grid_cache().clauses;
        cached_unless_cycle(cache, (at.clone(), column.clone()), self.cycle_reads(), || read().unwrap_or_default())
    }

    /// The grids of the column `column` of the output `output` of the `INIT`
    /// form at `at`: those that hold of the labels at the input columns that
    /// the registry's frame rule of the column names, in the instance's bodies,
    /// written over the instance's key columns.
    pub(super) fn instance_output_grids(&self, at: &NodePath, output: &PortName, column: &ColumnName) -> ColumnGrids {
        let read = || {
            let inferred = self.infer(at)?;
            let ScopeOwner::Form(form @ Form::Instance(instance)) = inferred.owner else { return None };
            let instance = instance.value();
            let rule = self.registry().output_frame(&instance.component, output, column).filter(|rule| !rule.makes)?;
            let scope = ScopeBody::of(form, self.registry());
            let grids = FormGrids::new(self, inferred.reading(PoseOr::Open), &scope);
            let in_input = |named: &FrameColumn| {
                let input = written_inputs(instance.key.as_ref(), &instance.inputs).find(|input| Some(&input.name) == named.input.as_ref())?;
                let head = input.head.iter().find(|site| site.column == named.column).and_then(site_label)?;
                Some(grids.in_body(input.body.value(), head))
            };
            let named: Vec<Grids> = rule.of.iter().map(in_input).collect::<Option<_>>()?;
            let key_columns: Vec<_> = instance.key.iter().flat_map(|key| key.value().key.columns.iter()).collect();
            let placed = |grid: Grid<Example>| {
                let example = match grid.example {
                    Example::Current => ColumnExample::Current,
                    Example::Label(label) => ColumnExample::Key(key_columns.iter().find(|own| own.label == label)?.name.clone()),
                };
                Some(Grid { kind: grid.kind, example })
            };
            Some(intersect_all(named).into_iter().filter_map(placed).collect())
        };
        let cache = &self.grid_cache().outputs;
        cached_unless_cycle(cache, (at.clone(), output.clone(), column.clone()), self.cycle_reads(), || read().unwrap_or_default())
    }
}
