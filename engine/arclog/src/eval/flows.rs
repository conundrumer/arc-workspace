//! Where the values of a relation's columns come from, over the case
//! program's dependency graph: the sources of each column of a relation.
//!
//! The sources of a column are the union over every form that gives the
//! column, every clause and every branch of an `OR` or an `IF`. A source
//! names the relation that a positive atom of a body reads, and the column
//! of it that the atom's site stands on, with the path of the atom.
//!
//! The facts of a body that the sources rest on, the atoms and the column
//! each variable stands at, the branches of each `OR` and `IF`, each `=`, and
//! each key read, are those of the [`ClauseIr`] that the evaluator joins for
//! that body, which the walk gets from the function of the module that
//! evaluates the form. [`IrPaths`] gives the path of each atom of the IR.

use std::collections::BTreeMap;
use std::sync::Arc;

use super::ir::{atom_modes, Argument, AtomSource, ClauseIr, CompiledBody, IrNode, IrPaths, NodePaths, Operand, Union, Variable, VariableInfo};
use super::{demonstrated, driver, picks, rigid};
use crate::check::CheckedProgram;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{Atom, ColumnName, Conjunct, ConstraintOp, FactRelation, OutputOwner, OutputStep, RelationRef};
use crate::registry::{key_fill, ColumnType, Registry};
use crate::resolver::given::{node_relation, Given, GivenLabel};
use crate::resolver::registry_columns;
use crate::resolver::{DependencyKind, GraphNodeIndex, ResolvedProgram, Resolution};
use crate::types::ValueType;

/// How a source gives the column's values.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum SourceKind {
    /// The column holds the source column's values.
    Copy = 0,
    /// The column holds values that the engine computes from the source
    /// column's.
    Computed = 1,
    /// The column is bound to `0`.
    Constant = 2,
    /// A lib name gives the values with no program relation read: a
    /// proposer's or a component's default rows.
    LibName = 3,
}

/// The column of the relation a source reads.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SourceColumn {
    /// The source gives no column: a constant, or a lib name.
    None,
    /// The row position of the column.
    Position(u16),
    /// The Example of the entry that the source's table holds.
    Example,
}

/// One source of a column.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct ColumnSource {
    pub kind: SourceKind,
    /// The relation read: `ex_input` for a read of `input`, the lib name
    /// of a [`SourceKind::LibName`] source, and `None` for a constant.
    pub relation: Option<RelationRef>,
    pub column: SourceColumn,
    /// The path of the source's row position in the columns of the relation
    /// read, as [`ResolvedProgram::row_paths`] gives it, where that relation
    /// is a program node: the position in the order the table of the
    /// relation was exported with, where a later form reordered its columns.
    pub row: Option<Box<[ColumnName]>>,
    /// The path of the atom that reads the source, empty where none does.
    pub atom: NodePath,
}

impl ColumnSource {
    fn without_atom(kind: SourceKind, relation: Option<RelationRef>) -> Self {
        ColumnSource { kind, relation, column: SourceColumn::None, row: None, atom: NodePath::default() }
    }

    fn computed(mut self) -> Self {
        self.kind = SourceKind::Computed;
        self
    }
}

/// The clause that the evaluator joins for a body, with the paths of its
/// nodes, and what holds them.
enum Held {
    Body(Arc<CompiledBody>),
    Shared(Arc<ClauseIr>, Arc<IrPaths>),
    Own(ClauseIr, IrPaths),
}

impl Held {
    fn parts(&self) -> (&ClauseIr, &IrPaths) {
        match self {
            Held::Body(body) => (&body.clause, &body.paths),
            Held::Shared(clause, paths) => (clause, paths),
            Held::Own(clause, paths) => (clause, paths),
        }
    }

    /// The held clause of a compile, none where it faults.
    fn of<E>(found: Result<(ClauseIr, IrPaths), E>) -> Option<Held> {
        found.ok().map(|(clause, paths)| Held::Own(clause, paths))
    }
}

/// One alternative of a body: the atoms and `=` comparisons that hold
/// together in it, and the `OR` nodes it has not yet chosen a branch of.
#[derive(Clone)]
struct Alt<'c> {
    /// The type of each variable of the clause.
    variables: &'c [VariableInfo],
    nodes: Vec<(&'c IrNode, &'c NodePaths)>,
    pending: Vec<(&'c Union, &'c [IrPaths])>,
}

impl<'c> Alt<'c> {
    fn of(clause: &'c ClauseIr, paths: &'c IrPaths) -> Self {
        let mut alt = Alt { variables: &clause.variables, nodes: Vec::new(), pending: Vec::new() };
        alt.add(clause, paths);
        alt
    }

    /// Adds the nodes of `clause`, which `paths` gives the paths of: its
    /// atoms and `=` comparisons here, and each `OR` as pending. A `NOT` and
    /// a counterexample bind nothing.
    fn add(&mut self, clause: &'c ClauseIr, paths: &'c IrPaths) {
        for (node, at) in clause.nodes.iter().zip(paths.nodes.iter()) {
            match (node, at) {
                (IrNode::Atom(_) | IrNode::Lib(_), _) => self.nodes.push((node, at)),
                (IrNode::Comparison(comparison), _) if comparison.op == ConstraintOp::Eq => self.nodes.push((node, at)),
                (IrNode::Or(union), NodePaths::Branches(branches)) => self.pending.push((union, branches)),
                _ => {}
            }
        }
    }

    /// The alternatives of this one that choose a branch of each pending
    /// `OR` that touches the class of `variable`, as it grows.
    fn expand(&self, variable: Variable) -> Vec<Alt<'c>> {
        let (class, _) = self.class_of(variable);
        let Some(index) = self.pending.iter().position(|(union, _)| union.branches.iter().any(|branch| touches(branch, &class))) else {
            return vec![self.clone()];
        };
        let mut rest = self.clone();
        let (union, paths) = rest.pending.remove(index);
        let mut alternatives = Vec::new();
        for (branch, branch_paths) in union.branches.iter().zip(paths) {
            let mut chosen = rest.clone();
            chosen.add(branch, branch_paths);
            alternatives.extend(chosen.expand(variable));
        }
        alternatives
    }

    /// The variables that `=` comparisons join to `variable`, `variable`
    /// included, and whether one is joined to `0`.
    fn class_of(&self, variable: Variable) -> (Vec<Variable>, bool) {
        let mut class = vec![variable];
        let mut zero = false;
        let mut grown = true;
        while grown {
            grown = false;
            for (node, _) in &self.nodes {
                let IrNode::Comparison(comparison) = node else { continue };
                match comparison.second {
                    Operand::Zero => {
                        if class.contains(&comparison.first) && !zero {
                            zero = true;
                            grown = true;
                        }
                    }
                    Operand::Variable(second) => {
                        let (has_first, has_second) = (class.contains(&comparison.first), class.contains(&second));
                        if has_first != has_second {
                            class.push(if has_first { second } else { comparison.first });
                            grown = true;
                        }
                    }
                }
            }
        }
        (class, zero)
    }

    /// The reads of the atoms of this alternative that stand on a variable of
    /// `class`.
    fn hits(&self, class: &[Variable]) -> Vec<Hit<'c>> {
        let mut hits = Vec::new();
        for &(node, paths) in &self.nodes {
            let arguments = match node {
                IrNode::Atom(atom) => &atom.arguments,
                IrNode::Lib(atom) => &atom.arguments,
                _ => continue,
            };
            for (column, argument) in arguments.0.iter() {
                if matches!(argument, Argument::Variable(variable) if class.contains(variable)) {
                    let Argument::Variable(variable) = argument else { continue };
                    hits.push(Hit { node, paths, column: column.0, variable: *variable });
                }
            }
        }
        hits
    }
}

/// Whether `clause`, or a branch in it, has an argument of an atom on a
/// variable of `class`, or an `=` comparison of one.
fn touches(clause: &ClauseIr, class: &[Variable]) -> bool {
    let on = |arguments: &super::ir::Arguments| arguments.0.iter().any(|(_, argument)| matches!(argument, Argument::Variable(variable) if class.contains(variable)));
    clause.nodes.iter().any(|node| match node {
        IrNode::Atom(atom) => on(&atom.arguments),
        IrNode::Lib(atom) => on(&atom.arguments),
        IrNode::Comparison(comparison) if comparison.op == ConstraintOp::Eq => {
            class.contains(&comparison.first) || matches!(comparison.second, Operand::Variable(second) if class.contains(&second))
        }
        IrNode::Or(union) => union.branches.iter().any(|branch| touches(branch, class)),
        _ => false,
    })
}

/// An argument of an `Atom` or a `Lib` node that stands on a variable of a
/// class, with the node, its paths and the column it stands on.
struct Hit<'c> {
    node: &'c IrNode,
    paths: &'c NodePaths,
    column: u16,
    /// The variable that stands there.
    variable: Variable,
}

/// The walk over a body's IR for the sources of a variable, with the nodes
/// whose flows are being resolved above this body.
struct Walk<'p> {
    flows: &'p Flows<'p>,
    visiting: &'p [GraphNodeIndex],
}

impl<'p> Walk<'p> {
    /// The atom of the program text at the atom path of `paths`.
    fn atom_of<'a>(&self, paths: &'a NodePaths) -> Option<(&'a NodePath, &'p Atom)> {
        let NodePaths::Atom(path) = paths else { return None };
        let root = NodeRef::Program(self.flows.program.program.value());
        match node_at(root, path)? {
            NodeRef::Conjunct(Conjunct::Atom(atom)) => Some((path, atom.value())),
            NodeRef::Atom(atom) => Some((path, atom)),
            _ => None,
        }
    }

    /// Whether the column that `hit` reads holds values of the type of the
    /// variable that stands there, or of an orientation type that its cells
    /// lie within. The IR can join a variable to a column of another type,
    /// such as the key fields of a keyed input's read of another `INIT`
    /// form's output, which names a copy of no value.
    fn keeps_type(&self, alt: &Alt<'_>, hit: &Hit<'_>) -> bool {
        let (IrNode::Atom(atom), Some((path, _))) = (hit.node, self.atom_of(hit.paths)) else { return true };
        let AtomSource::Relation(relation) = &atom.source else { return true };
        if self.flows.program.reads_lifted(path) {
            return true;
        }
        let Some(column) = self.flows.checked.types.columns(relation).and_then(|columns| columns.get(usize::from(hit.column))) else { return true };
        let Some(info) = alt.variables.get(usize::from(hit.variable.0)) else { return true };
        let orientation = |ty: &ValueType| ty.moved_by_d4() && *ty != ValueType::Box;
        info.ty == *column || (orientation(&info.ty) && orientation(column))
    }

    /// The sources that the read of `hit`, an `Atom` or a `Lib` node, gives:
    /// one source, or, where the atom reads an input port of an instance,
    /// the sources of the port's column.
    fn read(&self, hit: &Hit<'_>) -> Vec<ColumnSource> {
        let Some((path, atom)) = self.atom_of(hit.paths) else { return Vec::new() };
        let program = self.flows.program;
        let lifted = program.reads_lifted(path);
        let position = hit.column;
        let (relation, column) = match &atom.relation {
            RelationRef::Fact(FactRelation::Input) => (RelationRef::Fact(FactRelation::ExInput), SourceColumn::Position(position + 1)),
            relation if lifted && position == 0 => (relation.clone(), SourceColumn::Example),
            relation if lifted => (relation.clone(), SourceColumn::Position(position - 1)),
            relation => (relation.clone(), SourceColumn::Position(position)),
        };
        let resolved = program.resolution(path);
        let row = match (resolved, column) {
            (Some(Resolution::Node(node)), SourceColumn::Position(position)) => program.row_paths(*node).and_then(|paths| paths.into_iter().nth(usize::from(position))),
            _ => None,
        };
        if let (Some(Resolution::Node(port)), SourceColumn::Position(position)) = (resolved, column) {
            if matches!(program.graph.nodes[port.0 as usize].kind, DependencyKind::InstanceInput { .. }) {
                return self.flows.port_sources(*port, position, &mut self.visiting.to_vec());
            }
        }
        vec![ColumnSource { kind: SourceKind::Copy, relation: Some(relation), column, row, atom: path.clone() }]
    }

    /// The sources of `variable` in `alt`, which `visiting` holds the
    /// variables being resolved above: the union over the alternatives of
    /// `alt` that choose a branch of each `OR` and `IF` that binds the
    /// variable's class. In each, a variable that stands at a site of a
    /// positive atom of a program relation or a fact gets a copy of each
    /// such column, and a variable bound to `0` is a constant. A variable
    /// that only lib atoms bind is computed from the variables at the columns
    /// of a mode of the atom that the alternative binds elsewhere, and
    /// otherwise copies the lib relation's column.
    fn sources(&self, variable: Variable, alt: &Alt<'_>, visiting: &mut Vec<Variable>) -> Vec<ColumnSource> {
        if visiting.contains(&variable) {
            return Vec::new();
        }
        let mut found: Vec<ColumnSource> = Vec::new();
        for chosen in alt.expand(variable) {
            add_distinct(&mut found, self.sources_in(variable, &chosen, visiting));
        }
        found
    }

    fn sources_in(&self, variable: Variable, alt: &Alt<'_>, visiting: &mut Vec<Variable>) -> Vec<ColumnSource> {
        let (class, zero) = alt.class_of(variable);
        let hits = alt.hits(&class);
        let mut program = Vec::new();
        let mut keys = Vec::new();
        let mut libs = Vec::new();
        for hit in &hits {
            match hit.node {
                IrNode::Lib(_) => libs.push(hit),
                IrNode::Atom(atom) if matches!(atom.source, AtomSource::Key(_)) => keys.push(hit),
                _ if self.keeps_type(alt, hit) => program.push(hit),
                _ => {}
            }
        }
        let mut found: Vec<ColumnSource> = Vec::new();
        if zero {
            found.push(ColumnSource::without_atom(SourceKind::Constant, None));
        }
        found.extend(program.iter().flat_map(|hit| self.read(hit)));
        let mut keyed = false;
        if !zero && program.is_empty() {
            for hit in keys {
                let (IrNode::Atom(atom), NodePaths::Key(paths)) = (hit.node, hit.paths) else { continue };
                let AtomSource::Key(read) = &atom.source else { continue };
                let Some(&column) = read.clause.columns.get(usize::from(hit.column)) else { continue };
                let sources = self.sources(column, &Alt::of(&read.clause, paths), visiting);
                keyed |= !sources.is_empty();
                found.extend(sources);
            }
        }
        if !zero && program.is_empty() && !keyed {
            let before = visiting.len();
            visiting.extend(class.iter().copied());
            for hit in libs {
                found.extend(self.lib_sources(hit, alt, visiting));
            }
            visiting.truncate(before);
        }
        let mut distinct = Vec::new();
        add_distinct(&mut distinct, found);
        distinct
    }

    /// The sources that the lib atom of `hit` gives the variable at its
    /// column: computed from the variables of each mode that holds and does
    /// not bind the column, and otherwise a copy of the lib relation's
    /// column.
    fn lib_sources(&self, hit: &Hit<'_>, alt: &Alt<'_>, visiting: &mut Vec<Variable>) -> Vec<ColumnSource> {
        let (IrNode::Lib(lib), Some((path, atom))) = (hit.node, self.atom_of(hit.paths)) else { return Vec::new() };
        let program = self.flows.program;
        let position_of = |column: &ColumnName| {
            let (index, _) = atom.sites.iter().enumerate().find(|(_, site)| &site.column == column)?;
            program.column_position(&path.child(index as u32)).map(|position| position.0)
        };
        let here = atom.sites.iter().find(|site| position_of(&site.column) == Some(hit.column)).map(|site| &site.column);
        let mut computed = Vec::new();
        let mut holds = false;
        for mode in atom_modes(self.flows.registry, atom) {
            if here.is_some_and(|column| mode.bound.contains(column)) {
                continue;
            }
            let mut from = Vec::new();
            let mut bound = true;
            for column in mode.bound.iter() {
                let Some(position) = position_of(column) else {
                    bound = false;
                    break;
                };
                for (_, argument) in lib.arguments.0.iter().filter(|(at, _)| at.0 == position) {
                    let Argument::Variable(variable) = argument else { continue };
                    let sources = self.sources(*variable, alt, visiting);
                    bound &= !sources.is_empty();
                    from.extend(sources);
                }
            }
            if bound {
                holds = true;
                computed.extend(from.into_iter().map(ColumnSource::computed));
            }
        }
        if holds { computed } else { self.read(hit) }
    }
}

/// The walk over the dependency graph: the program, the checked program
/// that gives the evaluator's IR of a body, and the registry.
struct Flows<'p> {
    checked: &'p CheckedProgram,
    program: &'p ResolvedProgram,
    registry: &'p Registry,
}

impl CheckedProgram {
    /// The sources of each row position of the relation of
    /// `node`, whose columns take `types`, that a read at `output` after the owner's name reads, in row
    /// order. Each is the
    /// union over the forms that give the node and, in each, over every
    /// clause and branch:
    ///
    /// - a column that a form labels: the label's class under `=` in the
    ///   IR of the body that binds it, each site of a positive atom on it a
    ///   copy of that atom's column, `0` a constant, and, where only lib
    ///   atoms bind it, the sources of the labels of a mode of the lib atom,
    ///   computed; a key label in the class, in a body of a keyed form that
    ///   binds the class at no site of a positive atom, gives the sources
    ///   that the key's body gives that label, as copies;
    /// - a part-site column of a `RIGID_DET` part output whose type a D4
    ///   element moves ([`ValueType::moved_by_d4`]): the sources of its
    ///   label, computed, since the column holds the part's values at each
    ///   pose;
    /// - a column of a type parameter that an `INIT` form binds: the sources
    ///   of the labels the form binds it to, and, on an output port of a
    ///   keyed instance, where a `from-key` input the instance leaves
    ///   unwritten stands on the parameter, the sources of the key position
    ///   that the engine's fill gives each row position;
    /// - another declared column of an instance or a `RIGID_DET` assembly:
    ///   every row position of each relation the node reads, computed, where
    ///   the column of an input port of an instance is replaced by its
    ///   sources;
    /// - a column with no source above and a proposer or a component to give
    ///   it: the lib name.
    ///
    /// The facts of a body, its atoms and their columns, the branches of its
    /// `OR` and `IF`, its `=` and its key reads, are those of the IR that the
    /// evaluator joins for it, so a body that does not compile gives no
    /// source.
    ///
    /// An output of an instance that reads its own outputs has no flow from
    /// them.
    ///
    /// A source that names a column of an input port of an instance is
    /// replaced by the sources of that port's column, through each chain of
    /// input ports, because the export makes no table for a port.
    pub fn column_flows(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>, types: &[ValueType], registry: &Registry) -> Vec<Vec<ColumnSource>> {
        let flows = Flows { checked: self, program: &self.program, registry };
        flows.flows_visiting(node, output, types.len(), types, &mut Vec::new())
    }
}

impl<'p> Flows<'p> {
    /// [`CheckedProgram::column_flows`], where `visiting` holds the nodes
    /// being resolved above `node`. A column of a position that `types`
    /// leaves out has a type no D4 element moves.
    fn flows_visiting(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>, width: usize, types: &[ValueType], visiting: &mut Vec<GraphNodeIndex>) -> Vec<Vec<ColumnSource>> {
        visiting.push(node);
        let mut flows: Vec<Vec<ColumnSource>> = vec![Vec::new(); width];
        let given: Vec<Given> = self.program.given(node, self.registry).into_iter().filter(|relation| output.zip(relation.output.as_deref()).is_none_or(|(read, own)| read == own)).collect();
        let mut held: BTreeMap<(usize, NodePath), Option<Held>> = BTreeMap::new();
        for (which, relation) in given.iter().enumerate() {
            let mut start = 0usize;
            for (index, slot) in relation.slots.iter().enumerate() {
                for GivenLabel { label, body, place } in &slot.labels {
                    let own = self.program.label_position(&relation.form, *label).map(|position| usize::from(position.0));
                    let Some(position) = own.or(*place) else { continue };
                    let body = held.entry((which, body.clone())).or_insert_with(|| self.held(relation, body));
                    let found = body.as_ref().map_or_else(Vec::new, |body| {
                        let (clause, paths) = body.parts();
                        let walk = Walk { flows: self, visiting };
                        paths.labels.iter().position(|held| held == label).map_or_else(Vec::new, |variable| {
                            walk.sources(Variable(variable as u16), &Alt::of(clause, paths), &mut Vec::new())
                        })
                    });
                    let moved = index >= relation.sites_from && types.get(position).is_some_and(ValueType::moved_by_d4);
                    if let Some(sources) = flows.get_mut(position) {
                        add_distinct(sources, if moved { found.into_iter().map(ColumnSource::computed).collect() } else { found });
                    }
                }
                if slot.declared.is_some() && slot.labels.is_empty() {
                    for position in start..start + slot.width {
                        if let Some(sources) = flows.get_mut(position) {
                            add_distinct(sources, self.declared_sources(node, visiting));
                        }
                    }
                }
                start += slot.width;
            }
        }
        for relation in &given {
            self.add_key_fill(relation, types, &mut flows);
        }
        if let DependencyKind::RecursiveInstance(instance) = &self.program.graph.nodes[node.0 as usize].kind {
            let own = |source: &ColumnSource| matches!(&source.relation, Some(RelationRef::Output(name)) if name.of == OutputOwner::Instance(instance.clone()));
            for sources in &mut flows {
                sources.retain(|source| !own(source));
            }
        }
        for sources in flows.iter_mut().filter(|sources| sources.is_empty()) {
            let lib = given.iter().flat_map(|relation| relation.lib.iter());
            sources.extend(lib.map(|name| ColumnSource::without_atom(SourceKind::LibName, Some(RelationRef::Lib(name.clone())))));
        }
        visiting.pop();
        flows
    }

    /// The IR that the evaluator joins for the body at `body`, a path below
    /// the form of `relation`, with the paths of its nodes; none where the
    /// form's body does not compile.
    fn held(&self, relation: &Given, body: &NodePath) -> Option<Held> {
        let form = &relation.form;
        let at = form.join(body);
        let root = NodeRef::Program(self.program.program.value());
        match node_at(root, form)? {
            NodeRef::Clause(clause) => driver::clause_body(self.checked, form, clause).ok().map(Held::Body),
            NodeRef::Choose(choose) => {
                if choose.rows.is_some() && *body == NodePath::default().child(0) {
                    picks::for_pathed(self.checked, form, choose).ok().flatten().map(|(clause, paths)| Held::Own(clause, paths))
                } else {
                    Held::of(picks::from_pathed(self.checked, form, choose))
                }
            }
            NodeRef::Demonstrated(demonstrated) => {
                let (clause, paths) = demonstrated::clause_at(self.checked, demonstrated, form, &at)?.ok()?;
                Some(Held::Shared(clause, paths))
            }
            NodeRef::Instance(instance) => {
                let component = registry_columns::component(self.registry, &instance.component)?;
                let shape = super::init_form::InstanceShape::of(self.checked, form, instance, component);
                let (clause, paths) = shape.clause_at(self.checked, form, component, &at)?.ok()?;
                Some(Held::Shared(clause, paths))
            }
            NodeRef::RigidDet(rigid) => {
                let steps = relation.output.as_deref()?;
                Held::of(rigid::output_clause(self.checked, form, rigid, steps.first()?))
            }
            _ => None,
        }
    }

    /// Adds to each row position of a column of `relation`, on a type
    /// parameter that a `from-key` input the instance leaves unwritten stands
    /// on, the flows at the key position that the fill gives it
    /// ([`key_fill`]). `types` are the row-position types of the relation;
    /// nothing is added where they are not all known.
    fn add_key_fill(&self, relation: &Given, types: &[ValueType], flows: &mut [Vec<ColumnSource>]) {
        if relation.filled.is_empty() || types.len() != flows.len() {
            return;
        }
        // The first row position and the width of each column of the port.
        let mut at = Vec::new();
        let mut start = 0usize;
        for slot in &relation.slots {
            at.push((slot.is_key, slot.declared.as_ref(), start..start + slot.width));
            start += slot.width;
        }
        let Some((_, _, key)) = at.iter().find(|(is_key, ..)| *is_key) else { return };
        for input in &relation.filled {
            let mut input_types = Vec::new();
            let mut targets = Vec::new();
            for ty in input {
                match ty {
                    ColumnType::Fixed(fixed) => input_types.push(fixed.clone()),
                    ColumnType::Parameter(_) => {
                        let Some((_, _, own)) = at.iter().find(|(is_key, declared, _)| !is_key && *declared == Some(ty)) else { return };
                        targets.extend(own.clone().map(|position| (position, input_types.len() + position - own.start)));
                        input_types.extend(types[own.clone()].iter().cloned());
                    }
                    _ => return,
                }
            }
            let Some(positions) = key_fill(&types[key.clone()], &input_types) else { continue };
            for (position, row) in targets {
                let found = flows[positions[row]].clone();
                add_distinct(&mut flows[position], found);
            }
        }
    }

    /// The sources of row position `position` of the input port `port`; none
    /// where `visiting` holds the port.
    fn port_sources(&self, port: GraphNodeIndex, position: u16, visiting: &mut Vec<GraphNodeIndex>) -> Vec<ColumnSource> {
        if visiting.contains(&port) {
            return Vec::new();
        }
        let Some((_, width)) = self.program.node_width(port) else { return Vec::new() };
        let mut flows = self.flows_visiting(port, None, width, &[], visiting);
        if usize::from(position) < flows.len() { flows.swap_remove(usize::from(position)) } else { Vec::new() }
    }

    /// Every row position of each relation that `node` reads, computed:
    /// the sources of a declared column of an instance or an assembly. A
    /// read of an input port of an instance gives the sources of the port's
    /// columns, computed, in place of the port.
    fn declared_sources(&self, node: GraphNodeIndex, visiting: &mut Vec<GraphNodeIndex>) -> Vec<ColumnSource> {
        let mut found = Vec::new();
        for &read in self.program.graph.reads[node.0 as usize].iter().filter(|&&read| read != node) {
            let graph_node = &self.program.graph.nodes[read.0 as usize];
            let Some(relation) = node_relation(&graph_node.kind) else { continue };
            let Some((_, width)) = self.program.node_width(read) else { continue };
            for position in 0..width {
                if matches!(graph_node.kind, DependencyKind::InstanceInput { .. }) {
                    found.extend(self.port_sources(read, position as u16, visiting).into_iter().map(ColumnSource::computed));
                    continue;
                }
                let (relation, position) = match relation {
                    RelationRef::Fact(FactRelation::Input) => (RelationRef::Fact(FactRelation::ExInput), position + 1),
                    ref other => (other.clone(), position),
                };
                found.push(ColumnSource { kind: SourceKind::Computed, relation: Some(relation), column: SourceColumn::Position(position as u16), row: None, atom: NodePath::default() });
            }
        }
        found
    }
}

/// Adds to `held` each of `sources` it does not hold, in order.
fn add_distinct(held: &mut Vec<ColumnSource>, sources: Vec<ColumnSource>) {
    for source in sources {
        if !held.contains(&source) {
            held.push(source);
        }
    }
}
