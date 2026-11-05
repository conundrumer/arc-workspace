//! The enumeration of feature expressions: every term of the grammar of
//! `work/feature-spec/feature-spec.md#the-generating-set` at a size, at every
//! binding whose types can meet. The checker decides which of them are
//! features, so what this leaves out is only what it would refuse.
//!
//! A space is the leaves that an expression can read, per input or task-wide.
//! Terms of one size come from the terms of the smaller sizes. A component's
//! terms come last at their size, by their count of bound inputs, so the
//! terms that are few come first.

use std::ops::ControlFlow;

use arclog::program::ColumnName;
use arclog::registry::{is_key, Column as LibColumn, ColumnType, Component, ComponentKind, InputPort, LibEntry, LibName, Macro, ProposerKind, Registry};
use arclog::resolver::registry_columns::component;
use arclog::types::ValueType;

use crate::expand::{columns_of, Col};
use crate::expression::{Binding, Feature, Field, Kind, Leaf, Op, Operand, Rel};
use crate::pool::{kind_type, Frame};
use crate::schema::Tables;

/// A relation term with its columns.
#[derive(Clone, Debug)]
pub struct Typed {
    pub rel: Rel,
    pub columns: Vec<Col>,
    pub size: usize,
}

/// What a walk over terms visits.
pub type Visit<'v> = dyn FnMut(Typed) -> ControlFlow<()> + 'v;

/// The leaves of an expression and what its operators may bind.
pub struct Space<'a> {
    pub registry: &'a Registry,
    pub tables: &'a dyn Tables,
    /// Whether the terms are read task-wide.
    pub task_wide: bool,
    /// The tables that a leaf can name.
    pub table_names: Vec<String>,
    /// Whether a leaf can name a program relation.
    pub program_relations: bool,
    /// The kinds that a pool can range over.
    pub kinds: Vec<Kind>,
    /// The most inputs that a component's binding writes, where a caller limits
    /// them; the grammar limits them to the component's inputs.
    pub max_inputs: Option<usize>,
    /// The holes in scope, innermost last.
    pub frames: Vec<Frame>,
    /// For a sample: a salt, and the bindings of a component's first input per
    /// million that a term of several inputs starts from. The walk then skips
    /// the terms it leaves out, where a sample of the terms it visits would
    /// still enumerate them.
    pub thin: Option<(String, u32)>,
}

/// Whether the text `text` falls in the sample of `rate` in a million.
pub fn sampled(text: &str, salt: &str, rate: u32) -> bool {
    let digest = arclog::hash::digest_text(&format!("{salt}/{text}"));
    let bits = u32::from_str_radix(&digest[..7], 16).unwrap_or(0);
    bits % 1_000_000 < rate
}

fn written(name: &ColumnName) -> String {
    match name {
        ColumnName::Written(text) => text.to_string(),
        ColumnName::Slot(slot) => format!("c{slot}"),
    }
}

/// Whether two columns can stand at one label. A type the expansion does not
/// know can, and the checker decides.
fn meets(a: &Option<ValueType>, b: &Option<ValueType>) -> bool {
    match (a, b) {
        (Some(a), Some(b)) => a.meets(b),
        _ => true,
    }
}

fn is_number(ty: &Option<ValueType>) -> bool {
    matches!(ty, None | Some(ValueType::Int | ValueType::Nat))
}

fn has_zero(ty: &Option<ValueType>) -> bool {
    ty.as_ref().is_none_or(ValueType::has_zero)
}

/// Each subset of `items`, in the order of the masks, the empty one first.
fn subsets<T: Clone>(items: &[T]) -> Vec<Vec<T>> {
    let count = items.len().min(16);
    (0u32..1 << count).map(|mask| (0..count).filter(|at| mask & (1 << at) != 0).map(|at| items[at].clone()).collect()).collect()
}

/// The value types that a pool can range over.
pub fn value_kinds() -> Vec<Kind> {
    ["Int", "Nat", "Color", "Box", "Position", "Offset", "Ident", "C4", "D4", "Dir", "DiagDir", "Dir8", "Axis", "DiagAxis", "Axis4", "Sym", "Sense", "LibName", "Example"]
        .into_iter()
        .map(|name| Kind::Type(name.to_string()))
        .collect()
}

impl Space<'_> {
    /// `rel` with its columns, where the expansion can write it.
    pub fn typed(&self, rel: Rel) -> Option<Typed> {
        let columns = columns_of(&rel, self.tables, self.registry, self.task_wide, &self.frames).ok()?;
        let size = rel.size();
        Some(Typed { rel, columns, size })
    }

    /// The name of the column `column` in a term: a hole, where it stands for
    /// one in scope.
    fn reference(&self, column: &Col) -> String {
        self.frames.iter().rev().find(|frame| frame.name() == column.name).map_or_else(|| column.name.clone(), |frame| frame.hole.clone())
    }

    /// The lib relations that an expression can name, sorted.
    fn lib_relations(&self) -> Vec<(String, &[LibColumn], bool)> {
        let mut found = Vec::new();
        for name in self.registry.names() {
            let relation = match self.registry.entry(name) {
                Some(LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. })) => relation,
                _ => continue,
            };
            // `pose_difference` takes Pose values.
            if relation.columns.iter().any(|column| column.ty.fixed().is_none()) {
                continue;
            }
            found.push((name.0.to_string(), &relation.columns[..], relation.modes.is_empty()));
        }
        found.sort_by(|a, b| a.0.cmp(&b.0));
        found
    }

    /// The leaves of this space, sorted by their text.
    pub fn leaves(&self) -> Vec<Typed> {
        let mut leaves: Vec<Leaf> = self.table_names.iter().filter(|name| self.task_wide || !self.tables.table(name).is_some_and(|schema| schema.has_example)).map(|name| Leaf::Table(name.clone())).collect();
        if self.task_wide {
            leaves.extend([Leaf::ExInput, Leaf::ExOutput]);
        } else {
            leaves.extend([Leaf::Input, Leaf::Output]);
        }
        for (name, _, no_mode) in self.lib_relations() {
            if no_mode {
                leaves.push(Leaf::Lib(name));
            }
        }
        if self.task_wide {
            let mut proposers = Vec::new();
            for name in self.registry.names() {
                if let Some(LibEntry::Proposer(proposer)) = self.registry.entry(name) {
                    if !matches!(proposer.kind, ProposerKind::Native { domain: true }) {
                        proposers.push(name.0.to_string());
                    }
                }
            }
            proposers.sort();
            leaves.extend(proposers.into_iter().map(Leaf::Proposer));
        }
        if self.program_relations {
            leaves.extend(arclog::program::ProgramFact::ALL.into_iter().map(|fact| Leaf::Program(fact.name().to_string())));
        }
        let mut typed: Vec<Typed> = leaves.into_iter().filter_map(|leaf| self.typed(Rel::Leaf(leaf))).collect();
        typed.sort_by_key(|leaf| leaf.rel.to_string());
        typed
    }

    /// Each root over `typed`.
    pub fn roots(&self, typed: &Typed, visit: &mut dyn FnMut(Feature) -> ControlFlow<()>) -> ControlFlow<()> {
        visit(Feature::Nonempty(typed.rel.clone()))?;
        visit(Feature::Cardinality(typed.rel.clone()))?;
        let names: Vec<String> = typed.columns.iter().map(|column| self.reference(column)).collect();
        for columns in subsets(&names) {
            if !columns.is_empty() {
                visit(Feature::ValueSet(typed.rel.clone(), columns))?;
            }
        }
        ControlFlow::Continue(())
    }

    /// Each term of size `size`, from `lower`, the terms of each smaller size.
    pub fn generate(&self, lower: &[Vec<Typed>], size: usize, visit: &mut Visit<'_>) -> ControlFlow<()> {
        if size == 0 {
            for leaf in self.leaves() {
                visit(leaf)?;
            }
            return ControlFlow::Continue(());
        }
        self.unary(lower, size, visit)?;
        self.binary(lower, size, visit)?;
        self.pools(lower, size, visit)?;
        self.components(lower, size, visit)
    }

    fn emit(&self, rel: Rel, visit: &mut Visit<'_>) -> ControlFlow<()> {
        match self.typed(rel) {
            Some(typed) => visit(typed),
            None => ControlFlow::Continue(()),
        }
    }

    /// The terms of `project`, `select` and `lib-join`.
    fn unary(&self, lower: &[Vec<Typed>], size: usize, visit: &mut Visit<'_>) -> ControlFlow<()> {
        let Some(inner) = lower.get(size - 1) else { return ControlFlow::Continue(()) };
        for typed in inner {
            let names: Vec<String> = typed.columns.iter().map(|column| self.reference(column)).collect();
            // A `project` of every column gives the relation itself.
            for columns in subsets(&names) {
                if !columns.is_empty() && columns.len() < names.len() {
                    self.emit(Rel::Project(Box::new(typed.rel.clone()), columns), visit)?;
                }
            }
            self.selects(typed, visit)?;
            self.lib_joins(typed, visit)?;
        }
        ControlFlow::Continue(())
    }

    fn selects(&self, typed: &Typed, visit: &mut Visit<'_>) -> ControlFlow<()> {
        for (at, column) in typed.columns.iter().enumerate() {
            let name = self.reference(column);
            for (other_at, other) in typed.columns.iter().enumerate() {
                if at == other_at || !meets(&column.ty, &other.ty) {
                    continue;
                }
                // Two comparisons of one pair of columns in either order have one
                // expansion, under the name that comes first in text order.
                if self.reference(other) < name {
                    continue;
                }
                let operand = Operand::Column(self.reference(other));
                for op in Op::ALL {
                    if matches!(op, Op::Eq | Op::Ne) || (is_number(&column.ty) && is_number(&other.ty)) {
                        self.emit(Rel::Select(Box::new(typed.rel.clone()), name.clone(), op, operand.clone()), visit)?;
                    }
                }
            }
            if has_zero(&column.ty) {
                for op in Op::ALL {
                    if matches!(op, Op::Eq | Op::Ne) || is_number(&column.ty) {
                        self.emit(Rel::Select(Box::new(typed.rel.clone()), name.clone(), op, Operand::Zero), visit)?;
                    }
                }
            }
        }
        ControlFlow::Continue(())
    }

    fn lib_joins(&self, typed: &Typed, visit: &mut Visit<'_>) -> ControlFlow<()> {
        for (name, columns, _) in self.lib_relations() {
            let modes = match self.registry.algebra_relation(&LibName(name.as_str().into())) {
                Some(relation) => &relation.modes[..],
                None => &[],
            };
            // Each lib column is bound to a column of the relation or is fresh.
            let mut bindings: Vec<Vec<(String, String)>> = vec![Vec::new()];
            for lib in columns {
                let ty = lib.ty.fixed().cloned();
                let mut next = Vec::new();
                for binding in &bindings {
                    next.push(binding.clone());
                    for column in typed.columns.iter().filter(|column| meets(&ty, &column.ty)) {
                        let mut bound = binding.clone();
                        bound.push((written(&lib.name), self.reference(column)));
                        next.push(bound);
                    }
                }
                bindings = next;
            }
            for binding in bindings {
                let bound_mode = modes.is_empty() || modes.iter().any(|mode| mode.bound.iter().all(|column| binding.iter().any(|(lib, _)| *lib == written(column))));
                if bound_mode {
                    self.emit(Rel::LibJoin(Box::new(typed.rel.clone()), name.clone(), binding), visit)?;
                }
            }
        }
        ControlFlow::Continue(())
    }

    /// The terms of `join`, `antijoin` and `union`.
    fn binary(&self, lower: &[Vec<Typed>], size: usize, visit: &mut Visit<'_>) -> ControlFlow<()> {
        for left_size in 0..size {
            let right_size = size - 1 - left_size;
            let (Some(lefts), Some(rights)) = (lower.get(left_size), lower.get(right_size)) else { continue };
            for left in lefts {
                for right in rights {
                    let in_order = left.rel.to_string() <= right.rel.to_string();
                    for pairs in self.pair_sets(left, right) {
                        // A swap of a join's sides gives the same rows.
                        if in_order {
                            self.emit(Rel::Join(Box::new(left.rel.clone()), Box::new(right.rel.clone()), pairs.clone()), visit)?;
                        }
                        self.emit(Rel::Antijoin(Box::new(left.rel.clone()), Box::new(right.rel.clone()), pairs), visit)?;
                    }
                    if in_order && !left.columns.is_empty() && left.columns.len() == right.columns.len() {
                        for pairs in self.matchings(left, right) {
                            self.emit(Rel::Union(Box::new(left.rel.clone()), Box::new(right.rel.clone()), pairs), visit)?;
                        }
                    }
                }
            }
        }
        ControlFlow::Continue(())
    }

    /// Each set of pairs of a binary operator: each right column pairs with at
    /// most one left column whose type it can meet.
    fn pair_sets(&self, left: &Typed, right: &Typed) -> Vec<Vec<(String, String)>> {
        let mut sets: Vec<Vec<(String, String)>> = vec![Vec::new()];
        for r in &right.columns {
            let mut next = Vec::new();
            for set in &sets {
                next.push(set.clone());
                for l in left.columns.iter().filter(|l| meets(&l.ty, &r.ty)) {
                    let mut with = set.clone();
                    with.push((self.reference(l), self.reference(r)));
                    next.push(with);
                }
            }
            sets = next;
        }
        sets
    }

    /// Each way that the pairs of a `union` name every column of both.
    fn matchings(&self, left: &Typed, right: &Typed) -> Vec<Vec<(String, String)>> {
        fn walk(space: &Space<'_>, left: &Typed, right: &Typed, at: usize, used: &mut Vec<bool>, held: &mut Vec<(String, String)>, out: &mut Vec<Vec<(String, String)>>) {
            if at == left.columns.len() {
                out.push(held.clone());
                return;
            }
            for (other, column) in right.columns.iter().enumerate() {
                if used[other] || !meets(&left.columns[at].ty, &column.ty) {
                    continue;
                }
                used[other] = true;
                held.push((space.reference(&left.columns[at]), space.reference(column)));
                walk(space, left, right, at + 1, used, held, out);
                held.pop();
                used[other] = false;
            }
        }
        let mut out = Vec::new();
        walk(self, left, right, 0, &mut vec![false; right.columns.len()], &mut Vec::new(), &mut out);
        out
    }

    /// The terms of `pool`: a hole over a relation of a smaller size, of each
    /// kind, and a body over it that names the hole and ends in a `project` or
    /// a `component`.
    fn pools(&self, lower: &[Vec<Typed>], size: usize, visit: &mut Visit<'_>) -> ControlFlow<()> {
        if size < 2 {
            return ControlFlow::Continue(());
        }
        let hole = format!("?{}", ["x", "y", "z", "w"][self.frames.len().min(3)]);
        for over_size in 0..size.saturating_sub(1) {
            let body_size = size - 1 - over_size;
            if body_size == 0 {
                continue;
            }
            let Some(overs) = lower.get(over_size) else { continue };
            for over in overs {
                for kind in &self.kinds {
                    let mut root = kind;
                    while let Kind::LineageRoot(inner, _) = root {
                        root = inner;
                    }
                    let Kind::Type(type_name) = root else { continue };
                    let Some(ty) = kind_type(type_name) else { continue };
                    if ty == ValueType::Example && !self.task_wide {
                        continue;
                    }
                    let frame = Frame { hole: hole.clone(), over: over.rel.clone(), column: hole.trim_start_matches('?').to_uppercase(), empty: None, open: Some(ty) };
                    let mut frames = self.frames.clone();
                    frames.push(frame);
                    let inner = Space {
                        registry: self.registry,
                        tables: self.tables,
                        task_wide: self.task_wide,
                        table_names: self.table_names.clone(),
                        program_relations: self.program_relations,
                        kinds: self.kinds.clone(),
                        max_inputs: self.max_inputs,
                        frames,
                        thin: self.thin.clone(),
                    };
                    // The body's terms, bottom up, with the hole among the relation's columns.
                    let mut held: Vec<Vec<Typed>> = Vec::new();
                    for at in 0..=body_size {
                        let mut terms = Vec::new();
                        let mut done = ControlFlow::Continue(());
                        if at == over_size {
                            if let Some(own) = inner.typed(over.rel.clone()) {
                                terms.push(own);
                            }
                        }
                        let ended = inner.generate(&held, at, &mut |term| {
                            if at == body_size && matches!(term.rel, Rel::Project(..) | Rel::Component(..)) && term.rel.to_string().contains(&hole) {
                                let pool = Rel::Pool { hole: hole.clone(), over: Box::new(over.rel.clone()), kind: kind.clone(), body: Box::new(term.rel.clone()) };
                                if let Some(typed) = self.typed(pool) {
                                    done = visit(typed);
                                    if done.is_break() {
                                        return ControlFlow::Break(());
                                    }
                                }
                            }
                            terms.push(term);
                            ControlFlow::Continue(())
                        });
                        done?;
                        ended?;
                        held.push(terms);
                    }
                }
            }
        }
        ControlFlow::Continue(())
    }

    /// The components that a term can name, sorted.
    fn component_names(&self) -> Vec<(String, &Component)> {
        let mut found: Vec<(String, &Component)> = self.registry.names().filter_map(|name| {
            let held = component(self.registry, name)?;
            (held.kind != ComponentKind::TaskStructure && !held.reads_outputs()).then(|| (name.0.to_string(), held))
        }).collect();
        found.sort_by(|a, b| a.0.cmp(&b.0));
        found
    }

    /// The terms of `component`, by their count of bound inputs.
    fn components(&self, lower: &[Vec<Typed>], size: usize, visit: &mut Visit<'_>) -> ControlFlow<()> {
        let components = self.component_names();
        let most = components.iter().map(|(_, held)| held.inputs.len()).max().unwrap_or(0);
        for count in 1..=most.min(self.max_inputs.unwrap_or(most)) {
            for (name, held) in &components {
                let inputs: Vec<&InputPort> = held.inputs.iter().collect();
                for chosen in subsets(&inputs).into_iter().filter(|chosen| chosen.len() == count) {
                    let mut state = Bindings { key: None, parameters: Vec::new(), held: Vec::new() };
                    self.bind(name, held, &chosen, 0, lower, size - 1, &mut state, visit)?;
                }
            }
        }
        ControlFlow::Continue(())
    }

    /// Each binding of the inputs `chosen` from `at` on, whose relations have
    /// `size` operators in all, after those that `state` holds.
    #[allow(clippy::too_many_arguments)]
    fn bind(&self, name: &str, held: &Component, chosen: &[&InputPort], at: usize, lower: &[Vec<Typed>], size: usize, state: &mut Bindings, visit: &mut Visit<'_>) -> ControlFlow<()> {
        let Some(input) = chosen.get(at) else {
            if size != 0 {
                return ControlFlow::Continue(());
            }
            for port in held.outputs.iter() {
                self.emit(Rel::Component(name.to_string(), state.held.clone(), port.name.0.to_string()), visit)?;
            }
            return ControlFlow::Continue(());
        };
        let last = at + 1 == chosen.len();
        for own in 0..=size {
            if last && own != size {
                continue;
            }
            let Some(relations) = lower.get(own) else { continue };
            for relation in relations {
                for (binding, key, parameters) in self.input_bindings(input, relation, state) {
                    if let Some((salt, rate)) = self.thin.as_ref().filter(|_| at == 0 && chosen.len() > 1) {
                        if !sampled(&binding.to_string(), salt, *rate) {
                            continue;
                        }
                    }
                    let before_key = state.key.clone();
                    let before_parameters = state.parameters.clone();
                    if state.key.is_none() && !key.is_empty() {
                        state.key = Some(key);
                    }
                    for (parameter, types) in parameters {
                        if !state.parameters.iter().any(|(held, _)| *held == parameter) {
                            state.parameters.push((parameter, types));
                        }
                    }
                    state.held.push(binding);
                    let done = self.bind(name, held, chosen, at + 1, lower, size - own, state, visit);
                    state.held.pop();
                    state.key = before_key;
                    state.parameters = before_parameters;
                    done?;
                }
            }
        }
        ControlFlow::Continue(())
    }

    /// Each binding of `input` from `relation` that agrees with `state`: its
    /// key columns, its fields, the key's types and each parameter's.
    fn input_bindings(&self, input: &InputPort, relation: &Typed, state: &Bindings) -> Vec<(Binding, Vec<Option<ValueType>>, Vec<(String, Vec<Option<ValueType>>)>)> {
        let has_key = input.port.columns.iter().any(is_key);
        let columns: Vec<&LibColumn> = input.port.columns.iter().filter(|column| !is_key(column)).collect();
        let all: Vec<&Col> = relation.columns.iter().collect();
        // The key columns: any subset, or those that a key already bound has
        // the types of.
        let mut keys: Vec<Vec<&Col>> = Vec::new();
        if has_key {
            match &state.key {
                None => keys.extend(subsets(&all)),
                Some(types) => {
                    keys.push(Vec::new());
                    keys.extend(selections(&all, types));
                }
            }
        } else {
            keys.push(Vec::new());
        }
        // The fields of each column.
        let mut field_sets: Vec<(Vec<Vec<&Col>>, Vec<(String, Vec<Option<ValueType>>)>)> = vec![(Vec::new(), Vec::new())];
        for column in &columns {
            let mut next = Vec::new();
            for (fields, parameters) in &field_sets {
                match &column.ty {
                    ColumnType::Parameter(parameter) if written(&column.name).starts_with(|c: char| c.is_ascii_lowercase()) => {
                        let shape = state.parameters.iter().chain(parameters.iter()).find(|(held, _)| **held == *parameter.name).map(|(_, types)| types.clone());
                        let choices = match &shape {
                            Some(types) => selections(&all, types),
                            None => subsets(&all),
                        };
                        for choice in choices {
                            let mut with = fields.clone();
                            with.push(choice.clone());
                            let mut bound = parameters.clone();
                            if shape.is_none() {
                                bound.push((parameter.name.to_string(), choice.iter().map(|column| column.ty.clone()).collect()));
                            }
                            next.push((with, bound));
                        }
                    }
                    declared => {
                        let ty = match declared {
                            ColumnType::Parameter(parameter) => parameter.bound.clone(),
                            other => other.fixed().cloned(),
                        };
                        for choice in all.iter().filter(|column| meets(&ty, &column.ty)) {
                            let mut with = fields.clone();
                            with.push(vec![*choice]);
                            next.push((with, parameters.clone()));
                        }
                    }
                }
            }
            field_sets = next;
        }
        let mut out = Vec::new();
        for key in &keys {
            for (fields, parameters) in &field_sets {
                let binding = Binding {
                    input: input.port.name.0.to_string(),
                    relation: relation.rel.clone(),
                    key: key.iter().map(|column| self.reference(column)).collect(),
                    fields: match &fields[..] {
                        // One column: the fields are that column's.
                        [one] => one.iter().map(|column| Field::One(self.reference(column))).collect(),
                        several => several
                            .iter()
                            .map(|field| match &field[..] {
                                [one] => Field::One(self.reference(one)),
                                many => Field::Record(many.iter().map(|column| self.reference(column)).collect()),
                            })
                            .collect(),
                    },
                };
                out.push((binding, key.iter().map(|column| column.ty.clone()).collect(), parameters.clone()));
            }
        }
        out
    }
}

/// What the bindings before an input fix.
struct Bindings {
    key: Option<Vec<Option<ValueType>>>,
    parameters: Vec<(String, Vec<Option<ValueType>>)>,
    held: Vec<Binding>,
}

/// Each ordered choice of distinct columns of `all` whose types meet `types`.
fn selections<'c>(all: &[&'c Col], types: &[Option<ValueType>]) -> Vec<Vec<&'c Col>> {
    let mut out: Vec<Vec<&'c Col>> = vec![Vec::new()];
    for ty in types {
        let mut next = Vec::new();
        for held in &out {
            for column in all.iter().filter(|column| meets(ty, &column.ty) && !held.iter().any(|own| own.name == column.name)) {
                let mut with = held.clone();
                with.push(*column);
                next.push(with);
            }
        }
        out = next;
    }
    out
}
