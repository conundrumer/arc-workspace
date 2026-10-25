//! Where the values of a relation's columns come from, over the case
//! program's dependency graph: the sources of each column, the depth of a
//! node, and the candidate keys of a relation.
//!
//! The sources of a column are the union over every form that gives the
//! column, every clause and every branch of an `OR` or an `IF`. A source
//! names the relation that a positive atom of a body reads, and the column
//! of it that the atom's site stands on, with the path of the atom.

use std::collections::BTreeMap;
use std::sync::Arc;

use super::column_sources::{Listing, Source};
use super::columns::{Columns, Place, Slot};
use super::registry_columns;
use super::{form_columns, ColumnPosition, DependencyKind, GraphNodeIndex, ResolvedProgram, Resolution};
use crate::eval::ir::atom_modes;
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    written_inputs, Atom, Body, ColumnName, Conjunct, ConstraintOp, FactRelation, LabelId, LabelUse, OutputName, OutputOwner, OutputStep, Operand, ProgramRelation,
    RelationRef, RigidDetPart, Site, SiteArg,
};
use crate::registry::{is_key, key_fill, ColumnType, LibName, Registry};
use crate::safety::list_of;
use crate::types::{each_site_label, use_label, ValueType};

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

/// The positive atoms of a body, with the label pairs its `=` constraints
/// join, `None` for a pair with `0`. The atoms are those of the body itself;
/// each `OR` and each `IF` of the body is a split, with one `Gathered` for
/// each branch of the `OR` and for the then and the else of the `IF`. An
/// atom under `NOT`, in the test of an `IF` or in an `ALL` binds nothing.
#[derive(Default)]
struct Gathered<'p> {
    atoms: Vec<(NodePath, &'p Atom)>,
    equal: Vec<(LabelId, Option<LabelId>)>,
    splits: Vec<Vec<Gathered<'p>>>,
}

impl<'p> Gathered<'p> {
    fn of_body(&mut self, body: &'p Body, at: &NodePath) {
        for (path, conjunct) in list_of(body, at) {
            match conjunct {
                Conjunct::Atom(atom) => self.atoms.push((path, atom.value())),
                Conjunct::Constraint(constraint) if constraint.op == ConstraintOp::Eq => {
                    let second = match constraint.second {
                        Operand::Zero => None,
                        Operand::Label(label) => Some(label.label),
                    };
                    self.equal.push((constraint.first.label, second));
                }
                Conjunct::Or(branches) => {
                    let mut split = Vec::new();
                    for (index, branch) in branches.iter().enumerate() {
                        let mut found = Gathered::default();
                        found.of_body(branch.value(), &path.child(index as u32));
                        split.push(found);
                    }
                    self.splits.push(split);
                }
                Conjunct::If { then, otherwise, .. } => {
                    let mut then_part = Gathered::default();
                    then_part.of_body(then.value(), &path.child(1));
                    let mut else_part = Gathered::default();
                    else_part.of_body(otherwise.value(), &path.child(2));
                    self.splits.push(vec![then_part, else_part]);
                }
                Conjunct::Not(_) | Conjunct::Constraint(_) | Conjunct::All { .. } => {}
            }
        }
    }

    /// Whether this part, or a split in it, has a site of a positive atom
    /// on a label of `class`, or an `=` pair of one.
    fn touches(&self, class: &[LabelId]) -> bool {
        let pair = self.equal.iter().any(|&(first, second)| class.contains(&first) || second.is_some_and(|second| class.contains(&second)));
        let atom = self.atoms.iter().any(|(_, atom)| {
            let mut found = false;
            for site in atom.sites.iter() {
                each_site_label(site, &mut Vec::new(), &mut |use_, _| found |= use_label(use_).is_some_and(|label| class.contains(&label)));
            }
            found
        });
        pair || atom || self.splits.iter().flatten().any(|part| part.touches(class))
    }
}

/// One alternative of a body: the atoms and `=` pairs that hold together
/// in it, and the splits it has not yet chosen a branch of.
#[derive(Clone)]
struct Alt<'p> {
    atoms: Vec<&'p (NodePath, &'p Atom)>,
    equal: Vec<(LabelId, Option<LabelId>)>,
    pending: Vec<&'p [Gathered<'p>]>,
}

impl<'p> Alt<'p> {
    fn of(body: &'p Gathered<'p>) -> Self {
        let mut alt = Alt { atoms: Vec::new(), equal: Vec::new(), pending: Vec::new() };
        alt.add(body);
        alt
    }

    fn add(&mut self, part: &'p Gathered<'p>) {
        self.atoms.extend(part.atoms.iter());
        self.equal.extend(part.equal.iter().copied());
        self.pending.extend(part.splits.iter().map(Vec::as_slice));
    }

    /// The alternatives of this one that choose a branch of each pending
    /// split that touches the class of `label`, as it grows.
    fn expand(&self, label: LabelId) -> Vec<Alt<'p>> {
        let (class, _) = self.class_of(label);
        let Some(index) = self.pending.iter().position(|split| split.iter().any(|part| part.touches(&class))) else {
            return vec![self.clone()];
        };
        let mut rest = self.clone();
        let split = rest.pending.remove(index);
        let mut alternatives = Vec::new();
        for part in split {
            let mut chosen = rest.clone();
            chosen.add(part);
            alternatives.extend(chosen.expand(label));
        }
        alternatives
    }

    /// The labels that `=` constraints join to `label`, `label` included,
    /// and whether one is joined to `0`.
    fn class_of(&self, label: LabelId) -> (Vec<LabelId>, bool) {
        let mut class = vec![label];
        let mut zero = false;
        let mut grown = true;
        while grown {
            grown = false;
            for &(first, second) in &self.equal {
                match second {
                    None => {
                        if class.contains(&first) && !zero {
                            zero = true;
                            grown = true;
                        }
                    }
                    Some(second) => {
                        let (has_first, has_second) = (class.contains(&first), class.contains(&second));
                        if has_first != has_second {
                            class.push(if has_first { second } else { first });
                            grown = true;
                        }
                    }
                }
            }
        }
        (class, zero)
    }
}

/// A site of a positive atom that stands on a label of a class.
struct Hit<'p> {
    path: &'p NodePath,
    atom: &'p Atom,
    column: &'p crate::program::ColumnName,
    position: Option<ColumnPosition>,
}

struct BodyFlows<'p> {
    program: &'p ResolvedProgram,
    registry: &'p Registry,
    /// The nodes whose flows are being resolved above this body.
    visiting: &'p [GraphNodeIndex],
}

impl<'p> BodyFlows<'p> {
    /// The labels at `site`, a site of the atom at `atom`, with the row
    /// position of the column each stands on.
    fn uses(&self, path: &NodePath, site: &Site, visit: &mut dyn FnMut(LabelUse, Option<ColumnPosition>)) {
        let at_site = self.program.column_position(path);
        for (index, arg) in site.value.args.iter().enumerate() {
            let child = path.child(index as u32);
            match arg {
                SiteArg::Label(use_) | SiteArg::NamedLabel { label: use_, .. } => visit(*use_, self.program.column_position(&child).or(at_site)),
                SiteArg::Field(field) => self.uses(&child, field, visit),
            }
        }
    }

    fn hits<'a>(&self, alt: &'a Alt<'p>, class: &[LabelId]) -> Vec<Hit<'a>> {
        let mut hits = Vec::new();
        for (path, atom) in alt.atoms.iter().map(|entry| (&entry.0, entry.1)) {
            if !matches!(self.program.resolution(path), Some(Resolution::Node(_) | Resolution::Lib(_) | Resolution::Undefined(_))) {
                continue;
            }
            for (index, site) in atom.sites.iter().enumerate() {
                self.uses(&path.child(index as u32), site, &mut |use_, position| {
                    if use_label(use_).is_some_and(|label| class.contains(&label)) {
                        hits.push(Hit { path, atom, column: &site.column, position });
                    }
                });
            }
        }
        hits
    }

    /// The sources that the read of `hit` gives: one source, or, where the
    /// atom reads an input port of an instance, the sources of the port's
    /// column, computed where `kind` is.
    fn read(&self, kind: SourceKind, hit: &Hit<'_>) -> Vec<ColumnSource> {
        let source = self.read_one(kind, hit);
        if let (Some(Resolution::Node(port)), SourceColumn::Position(position)) = (self.program.resolution(hit.path), source.column) {
            if matches!(self.program.graph.nodes[port.0 as usize].kind, DependencyKind::InstanceInput { .. }) {
                let found = self.program.port_sources(*port, position, self.registry, &mut self.visiting.to_vec());
                return if kind == SourceKind::Computed { found.into_iter().map(ColumnSource::computed).collect() } else { found };
            }
        }
        vec![source]
    }

    /// The source that names the column that the read of `hit` stands on.
    fn read_one(&self, kind: SourceKind, hit: &Hit<'_>) -> ColumnSource {
        let lifted = self.program.reads_lifted(hit.path);
        let (relation, column) = match (&hit.atom.relation, hit.position) {
            (relation, None) => (relation.clone(), SourceColumn::None),
            (RelationRef::Fact(FactRelation::Input), Some(position)) => (RelationRef::Fact(FactRelation::ExInput), SourceColumn::Position(position.0 + 1)),
            (relation, Some(ColumnPosition(0))) if lifted => (relation.clone(), SourceColumn::Example),
            (relation, Some(position)) if lifted => (relation.clone(), SourceColumn::Position(position.0 - 1)),
            (relation, Some(position)) => (relation.clone(), SourceColumn::Position(position.0)),
        };
        let row = match (self.program.resolution(hit.path), column) {
            (Some(Resolution::Node(node)), SourceColumn::Position(position)) => self.program.row_paths(*node).and_then(|paths| paths.into_iter().nth(usize::from(position))),
            _ => None,
        };
        ColumnSource { kind, relation: Some(relation), column, row, atom: hit.path.clone() }
    }

    /// The sources of `label` in `alt`, which `visiting` holds the labels
    /// being resolved above: the union over the alternatives of `alt` that
    /// choose a branch of each `OR` and `IF` that binds the label's class.
    /// In each, a label that stands at a site of a positive atom of a
    /// program relation or a fact gets a copy of each such column, and a
    /// label bound to `0` is a constant. A label that only lib atoms bind
    /// is computed from the labels at the columns of a mode of the atom
    /// that the alternative binds elsewhere, and otherwise copies the lib
    /// relation's column.
    fn sources(&self, label: LabelId, alt: &Alt<'p>, visiting: &mut Vec<LabelId>) -> Vec<ColumnSource> {
        if visiting.contains(&label) {
            return Vec::new();
        }
        let mut found: Vec<ColumnSource> = Vec::new();
        for chosen in alt.expand(label) {
            add_distinct(&mut found, self.sources_in(label, &chosen, visiting));
        }
        found
    }

    fn sources_in(&self, label: LabelId, alt: &Alt<'p>, visiting: &mut Vec<LabelId>) -> Vec<ColumnSource> {
        let (class, zero) = alt.class_of(label);
        let hits = self.hits(alt, &class);
        let (lib, program): (Vec<&Hit<'_>>, Vec<&Hit<'_>>) = hits.iter().partition(|hit| matches!(hit.atom.relation, RelationRef::Lib(_)));
        let mut found: Vec<ColumnSource> = Vec::new();
        if zero {
            found.push(ColumnSource::without_atom(SourceKind::Constant, None));
        }
        found.extend(program.iter().flat_map(|hit| self.read(SourceKind::Copy, hit)));
        if !zero && program.is_empty() {
            let before = visiting.len();
            visiting.extend(class.iter().copied());
            for hit in lib {
                found.extend(self.lib_sources(hit, alt, visiting));
            }
            visiting.truncate(before);
        }
        let mut distinct = Vec::new();
        add_distinct(&mut distinct, found);
        distinct
    }

    /// The sources that the lib atom of `hit` gives the label at its site:
    /// computed from the labels of each mode that holds and does not bind
    /// the site's column, and otherwise a copy of the lib relation's column.
    fn lib_sources(&self, hit: &Hit<'_>, alt: &Alt<'p>, visiting: &mut Vec<LabelId>) -> Vec<ColumnSource> {
        let mut computed = Vec::new();
        let mut holds = false;
        for mode in atom_modes(self.registry, hit.atom) {
            if mode.bound.contains(hit.column) {
                continue;
            }
            let mut from = Vec::new();
            let mut bound = true;
            for column in mode.bound.iter() {
                let Some(site) = hit.atom.sites.iter().find(|site| &site.column == column) else {
                    bound = false;
                    break;
                };
                let mut labels = Vec::new();
                each_site_label(site, &mut Vec::new(), &mut |use_, _| labels.extend(use_label(use_)));
                for label in labels {
                    let sources = self.sources(label, alt, visiting);
                    bound &= !sources.is_empty();
                    from.extend(sources);
                }
            }
            if bound {
                holds = true;
                computed.extend(from.into_iter().map(ColumnSource::computed));
            }
        }
        if holds {
            computed
        } else {
            self.read(SourceKind::Copy, hit)
        }
    }
}

/// The relation that a node of the graph stands for, where a read names
/// it.
fn node_relation(kind: &DependencyKind) -> Option<RelationRef> {
    let of = |relation: &ProgramRelation| match relation {
        ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
        ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
    };
    let port = |instance: &crate::program::InstanceName, port: &crate::program::PortName| {
        RelationRef::Output(OutputName { of: OutputOwner::Instance(instance.clone()), path: Arc::from([OutputStep::Port(port.clone())]) })
    };
    match kind {
        DependencyKind::Fact(fact) => Some(RelationRef::Fact(*fact)),
        DependencyKind::Clause(relation) | DependencyKind::Parameter(relation) => Some(of(relation)),
        DependencyKind::Chosen(name) | DependencyKind::Demonstrated(name) => Some(RelationRef::Declared(name.clone())),
        DependencyKind::InstanceInput { instance, input: name } | DependencyKind::InstanceOutput { instance, output: name } => Some(port(instance, name)),
        DependencyKind::RigidAssembly(_) | DependencyKind::RecursiveInstance(_) => None,
    }
}

/// A relation that a form gives a node: the form's path, the relation's
/// path after the form's name where the form gives several, and its listing.
struct Given {
    form: NodePath,
    output: Option<Arc<[OutputStep]>>,
    listing: Listing,
    /// The lib name that gives the relation's rows where the form reads no
    /// program relation: the proposers of a clause, or the component of an
    /// instance.
    lib: Vec<LibName>,
    /// The index in the listing of its first entry that a part site of a
    /// `RIGID_DET` assembly gives; the entries before are the key's and
    /// `:Pose`. Beyond the listing for any other relation.
    sites_from: usize,
    /// For an output port of a keyed instance, the declared types of the
    /// columns other than `key` of each `from-key` input that the instance
    /// writes no clause for, which the engine fills from the key.
    filled: Vec<Vec<ColumnType>>,
}

impl ResolvedProgram {
    /// The sources of each row position of the relation of
    /// `node`, whose columns take `types`, that a read at `output` after the owner's name reads, in row
    /// order. Each is the
    /// union over the forms that give the node and, in each, over every
    /// clause and branch:
    ///
    /// - a column that a form labels: the label's class under `=` in the
    ///   body that binds it, each site of a positive atom on it a copy of
    ///   that atom's column, `0` a constant, and, where only lib atoms bind
    ///   it, the sources of the labels of a mode of the lib atom, computed;
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
    /// An output of an instance that reads its own outputs has no flow from
    /// them.
    ///
    /// A source that names a column of an input port of an instance is
    /// replaced by the sources of that port's column, through each chain of
    /// input ports, because the export makes no table for a port.
    pub fn column_flows(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>, types: &[ValueType], registry: &Registry) -> Vec<Vec<ColumnSource>> {
        self.flows_visiting(node, output, types.len(), types, registry, &mut Vec::new())
    }

    /// [`Self::column_flows`], where `visiting` holds the nodes being
    /// resolved above `node`. A column of a position that `types` leaves
    /// out has a type no D4 element moves.
    fn flows_visiting(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>, width: usize, types: &[ValueType], registry: &Registry, visiting: &mut Vec<GraphNodeIndex>) -> Vec<Vec<ColumnSource>> {
        visiting.push(node);
        let mut flows: Vec<Vec<ColumnSource>> = vec![Vec::new(); width];
        let given: Vec<Given> = self.given(node, registry).into_iter().filter(|relation| output.zip(relation.output.as_deref()).is_none_or(|(read, own)| read == own)).collect();
        let root = NodeRef::Program(self.program.value());
        let mut gathered: BTreeMap<NodePath, Gathered<'_>> = BTreeMap::new();
        for relation in &given {
            for listed in &relation.listing.0 {
                for (_, source) in &listed.sources {
                    if let Source::Label { body, .. } = source {
                        let at = relation.form.join(body);
                        if !gathered.contains_key(&at) {
                            let mut found = Gathered::default();
                            match node_at(root, &at) {
                                Some(NodeRef::Body(body)) => found.of_body(body, &at),
                                Some(NodeRef::RigidDet(rigid)) => {
                                    for (index, part) in rigid.parts.iter().enumerate() {
                                        found.atoms.push((at.child(rigid.position(RigidDetPart::Part(index))), part.value()));
                                    }
                                }
                                _ => {}
                            }
                            gathered.insert(at, found);
                        }
                    }
                }
            }
        }
        for relation in &given {
            let columns = relation.listing.columns();
            let mut start = 0usize;
            for (index, listed) in relation.listing.0.iter().enumerate() {
                let slot_width = slot_width(&listed.slot);
                let labeled = listed.sources.iter().any(|(_, source)| matches!(source, Source::Label { .. }));
                for (path, source) in &listed.sources {
                    match source {
                        Source::Label { label, body } => {
                            let own = self.label_position(&relation.form, *label).map(|position| usize::from(position.0));
                            let Some(position) = own.or_else(|| place(&columns, path)) else { continue };
                            let at = relation.form.join(body);
                            let flow = BodyFlows { program: self, registry, visiting };
                            let found = flow.sources(*label, &Alt::of(&gathered[&at]), &mut Vec::new());
                            let moved = index >= relation.sites_from && types.get(position).is_some_and(ValueType::moved_by_d4);
                            if let Some(held) = flows.get_mut(position) {
                                add_distinct(held, if moved { found.into_iter().map(ColumnSource::computed).collect() } else { found });
                            }
                        }
                        Source::Declared(_) if !labeled => {
                            for position in start..start + slot_width {
                                if let Some(held) = flows.get_mut(position) {
                                    add_distinct(held, self.declared_sources(node, registry, visiting));
                                }
                            }
                        }
                        Source::Declared(_) => {}
                    }
                }
                start += slot_width;
            }
        }
        for relation in &given {
            self.add_key_fill(relation, types, &mut flows);
        }
        if let DependencyKind::RecursiveInstance(instance) = &self.graph.nodes[node.0 as usize].kind {
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
        for listed in &relation.listing.0 {
            let width = slot_width(&listed.slot);
            let declared = listed.sources.iter().find_map(|(_, source)| match source {
                Source::Declared(ty) => Some(ty),
                _ => None,
            });
            at.push((listed.slot.name() == &super::columns::key(), declared, start..start + width));
            start += width;
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
    fn port_sources(&self, port: GraphNodeIndex, position: u16, registry: &Registry, visiting: &mut Vec<GraphNodeIndex>) -> Vec<ColumnSource> {
        if visiting.contains(&port) {
            return Vec::new();
        }
        let node = &self.graph.nodes[port.0 as usize];
        let Some(relation) = node_relation(&node.kind) else { return Vec::new() };
        let Some(columns) = self.names.columns(&node.scope, &relation) else { return Vec::new() };
        let mut flows = self.flows_visiting(port, None, columns.row_names().len(), &[], registry, visiting);
        if usize::from(position) < flows.len() { flows.swap_remove(usize::from(position)) } else { Vec::new() }
    }

    /// Every row position of each relation that `node` reads, computed:
    /// the sources of a declared column of an instance or an assembly. A
    /// read of an input port of an instance gives the sources of the port's
    /// columns, computed, in place of the port.
    fn declared_sources(&self, node: GraphNodeIndex, registry: &Registry, visiting: &mut Vec<GraphNodeIndex>) -> Vec<ColumnSource> {
        let mut found = Vec::new();
        for &read in self.graph.reads[node.0 as usize].iter().filter(|&&read| read != node) {
            let Some(relation) = node_relation(&self.graph.nodes[read.0 as usize].kind) else { continue };
            let Some(columns) = self.names.columns(&self.graph.nodes[read.0 as usize].scope, &relation) else { continue };
            for position in 0..columns.row_names().len() {
                if matches!(self.graph.nodes[read.0 as usize].kind, DependencyKind::InstanceInput { .. }) {
                    found.extend(self.port_sources(read, position as u16, registry, visiting).into_iter().map(ColumnSource::computed));
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

    /// The relations that the forms of `node` give it, with their listings.
    fn given(&self, node: GraphNodeIndex, registry: &Registry) -> Vec<Given> {
        let root = NodeRef::Program(self.program.value());
        let mut given = Vec::new();
        for form in self.forms_of(node) {
            let Some(shape) = node_at(root, form) else { continue };
            let whole = |listing: Listing, lib: Vec<LibName>| Given { form: form.clone(), output: None, listing, lib, sites_from: usize::MAX, filled: Vec::new() };
            match shape {
                NodeRef::Clause(clause) => given.push(whole(form_columns::form_listing(shape), clause.proposers.to_vec())),
                NodeRef::Choose(_) => given.push(whole(form_columns::form_listing(shape), Vec::new())),
                NodeRef::Demonstrated(demonstrated) => given.push(whole(form_columns::demonstrated_listing(demonstrated), Vec::new())),
                NodeRef::RigidDet(rigid) => {
                    for (steps, listing) in form_columns::rigid_listings(rigid) {
                        let pose = listing.0.iter().position(|listed| listed.sources.iter().any(|(_, source)| matches!(source, Source::Declared(ColumnType::Pose))));
                        let sites_from = if steps.as_ref() == [OutputStep::Pose] { usize::MAX } else { pose.map_or(usize::MAX, |pose| pose + 1) };
                        given.push(Given { form: form.clone(), output: Some(steps), listing, lib: Vec::new(), sites_from, filled: Vec::new() });
                    }
                }
                NodeRef::Instance(instance) => {
                    let Some(component) = registry_columns::component(registry, &instance.component) else { continue };
                    let bindings = form_columns::bindings(instance, component);
                    let keyed = instance.key.is_some();
                    let written: Vec<_> = written_inputs(instance.key.as_ref(), &instance.inputs).collect();
                    let lib = vec![instance.component.clone()];
                    let filled: Vec<Vec<ColumnType>> = component
                        .inputs
                        .iter()
                        .filter(|own| keyed && own.from_key && own.port.columns.iter().any(is_key) && written.iter().all(|written| written.name != own.port.name))
                        .map(|own| own.port.columns.iter().filter(|column| !is_key(column)).map(|column| column.ty.clone()).collect())
                        .collect();
                    let mut port = |port: &crate::registry::Port, output: bool| {
                        let filled = if output { filled.clone() } else { Vec::new() };
                        let output = output.then(|| Arc::from([OutputStep::Port(port.name.clone())]));
                        given.push(Given { form: form.clone(), output, listing: form_columns::port_columns(port, &bindings, keyed), lib: lib.clone(), sites_from: usize::MAX, filled });
                    };
                    match &self.graph.nodes[node.0 as usize].kind {
                        DependencyKind::InstanceInput { input, .. } => {
                            for own in component.inputs.iter().filter(|own| own.port.name == *input) {
                                for written in written.iter().filter(|written| written.name == *input) {
                                    let listing = form_columns::input_columns(&own.port, &bindings, keyed, instance, written);
                                    given.push(Given { form: form.clone(), output: None, listing, lib: lib.clone(), sites_from: usize::MAX, filled: Vec::new() });
                                }
                            }
                        }
                        DependencyKind::InstanceOutput { output, .. } => {
                            for own in component.outputs.iter().filter(|own| own.name == *output) {
                                port(own, true);
                            }
                        }
                        DependencyKind::RecursiveInstance(_) => {
                            for own in component.outputs.iter() {
                                port(own, true);
                            }
                        }
                        _ => {}
                    }
                }
                _ => {}
            }
        }
        given
    }

    /// The depth of `node` in the dependency graph: 0 for a fact relation,
    /// and otherwise one more than the largest depth among the nodes it
    /// reads, 1 for a node that reads none. A lib relation is no node and
    /// adds nothing.
    pub fn depth(&self, node: GraphNodeIndex) -> u32 {
        let depths = self.depths.get_or_init(|| {
            let mut depths: Vec<Option<u32>> = vec![None; self.graph.nodes.len()];
            let mut open = vec![false; depths.len()];
            for start in 0..depths.len() {
                self.depth_of(start, &mut depths, &mut open);
            }
            depths.into_iter().map(|depth| depth.unwrap_or(0)).collect()
        });
        depths[node.0 as usize]
    }

    fn depth_of(&self, node: usize, depths: &mut [Option<u32>], open: &mut [bool]) -> u32 {
        if let Some(depth) = depths[node] {
            return depth;
        }
        if matches!(self.graph.nodes[node].kind, DependencyKind::Fact(_)) {
            depths[node] = Some(0);
            return 0;
        }
        open[node] = true;
        let mut deepest = 0;
        for &read in self.graph.reads[node].iter() {
            let read = read.0 as usize;
            if !open[read] {
                deepest = deepest.max(self.depth_of(read, depths, open));
            }
        }
        open[node] = false;
        depths[node] = Some(deepest + 1);
        deepest + 1
    }

    /// The candidate keys of the relation of `node` that the program text
    /// gives, each as the row positions of its columns in increasing order:
    /// the columns of each `ONE` mark of a clause, none for `(ONE)`, and
    /// the row's columns of a `CHOOSE` form.
    pub fn column_keys(&self, node: GraphNodeIndex) -> Vec<Vec<u16>> {
        let root = NodeRef::Program(self.program.value());
        let mut keys: Vec<Vec<u16>> = Vec::new();
        for form in self.forms_of(node) {
            let positions = |labels: &mut dyn Iterator<Item = LabelId>| {
                let mut key: Vec<u16> = labels.filter_map(|label| self.label_position(form, label)).map(|position| position.0).collect();
                key.sort_unstable();
                key
            };
            let found: Vec<Vec<u16>> = match node_at(root, form) {
                Some(NodeRef::Clause(clause)) => clause.ones.iter().map(|mark| positions(&mut mark.key.iter().copied())).collect(),
                Some(NodeRef::Choose(choose)) => choose.rows.iter().map(|rows| positions(&mut rows.columns.iter().map(|column| column.label))).collect(),
                _ => Vec::new(),
            };
            for key in found {
                if !keys.contains(&key) {
                    keys.push(key);
                }
            }
        }
        keys
    }
}

/// The number of row positions that `slot` takes.
fn slot_width(slot: &Slot) -> usize {
    match slot {
        Slot::Column(_) => 1,
        Slot::Record { fields, .. } => fields.len(),
    }
}

/// The row position of the column at `path` of `columns`.
fn place(columns: &Columns, path: &[crate::program::ColumnName]) -> Option<usize> {
    match columns.place(path)? {
        Place::Column(ColumnPosition(position)) | Place::Field(ColumnPosition(position), _) => Some(usize::from(position)),
        Place::Group(_) => None,
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
