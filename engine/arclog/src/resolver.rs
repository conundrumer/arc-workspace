//! Name resolution of a case program, and the dependency graph it gives. A
//! relation that no block of the case derives resolves to an undefined
//! relation.
//!
//! The registry and resolver stage writes the bodies.

use crate::diagnostic::WithDiagnostics;
use crate::hash::StableHash;
use crate::program::path::NodePath;
use crate::program::{
    ColumnName, InstanceName, Node, PortName, Program, ProgramRelation, RelationName, RigidDetName,
};
use crate::registry::{LibName, Registry};

/// Whether name resolution expands each lib macro, a lib name defined from
/// other lib names, into its definition. A program runs in either form.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MacroExpansion {
    /// Each macro stays an atom of its lib name.
    Keep,
    /// The atom of a macro gives way to the macro's definition, with the
    /// label at each of the atom's sites in the place of its column's label
    /// in the definition. Where the meet of a label's type, from the label's
    /// sites outside a part of the expansion, and the types of its sites in that
    /// part is empty, that part holds nothing: a part is the body that takes the
    /// atom's place, a branch of an `OR`, or a list of an `IF`, wherever it
    /// stands in that body. Each macro's column types are its definition's,
    /// a relation macro's columns and modes and a cell instance's outputs,
    /// as [`crate::registry::macro_column_types`] gives them, so a program
    /// that passes the checks under `Keep` passes them under `Expand`.
    Expand,
}

/// A node of the dependency graph: its kind and the name scope of its
/// declaration, so that two relations of one name that two `DEMO_RULE`
/// forms declare are two nodes.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct DependencyNode {
    pub kind: DependencyKind,
    pub scope: crate::program::NameScope,
}

/// The kind of a node of the dependency graph: a fact relation, a clause
/// relation, an instance input or output, a parameter, a chosen relation, a
/// `RIGID_DET` assembly or a `DEMONSTRATED` relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum DependencyKind {
    Fact(crate::program::FactRelation),
    /// A relation a clause derives, an instance relation on a `RULE_OR_DET`
    /// line included.
    Clause(ProgramRelation),
    /// An input of an instance.
    InstanceInput { instance: InstanceName, input: PortName },
    /// An output of an instance.
    InstanceOutput { instance: InstanceName, output: PortName },
    /// A parameter: a `DET` relation with no `ONE` mark, read as one node and
    /// never through its body, as a `DET` of the concept program is read in
    /// each case, with the values that `DET` keeps for it. A parameter that
    /// several blocks of the case determine is one node, whose values are
    /// those every determination admits. Each read of the parameter's own
    /// `DET` bodies is an edge into the node, so a `DET` that reads a
    /// relation which depends on its own parameter makes a cycle, which the
    /// checker refuses.
    Parameter(ProgramRelation),
    /// A chosen relation: a `CHOOSE` form's, or a clause's with `ONE` marks,
    /// a `DET` with `(ONE)` included, which is a chosen relation at the task
    /// level. An open parameter, a `DET`
    /// that ends in `(ONE)`, that several blocks of the case determine is
    /// one node, whose values are those every determination admits, as a
    /// [`DependencyKind::Parameter`] is.
    Chosen(RelationName),
    /// A `RIGID_DET` form: one node for its assemblies, one assembly, or,
    /// for a keyed form, one per key row, as `docs/arclog/rigid.md#form`
    /// gives.
    RigidAssembly(RigidDetName),
    /// A `DEMONSTRATED` relation.
    Demonstrated(RelationName),
    /// An instance of a component with inputs that read its outputs, as
    /// `Unfold`'s `step`, `skip` and `take` do, with those inputs and its
    /// outputs: one node. The registry marks those inputs,
    /// [`crate::registry::InputPort::reads_outputs`], so the resolver names
    /// no component.
    RecursiveInstance(InstanceName),
}

/// The index of a node in a [`DependencyGraph`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct GraphNodeIndex(pub u32);

/// The dependency graph of a case program: each read is an edge from the
/// node read to the node that reads it.
#[derive(Clone, Debug, Default)]
pub struct DependencyGraph {
    pub nodes: Box<[DependencyNode]>,
    /// For each node, the nodes it reads.
    pub reads: Box<[Box<[GraphNodeIndex]>]>,
}

impl DependencyGraph {
    /// A cycle of the graph, as the nodes on it, or `None` where the graph is
    /// acyclic.
    pub fn find_cycle(&self) -> Option<Vec<GraphNodeIndex>> {
        const NEW: u8 = 0;
        const OPEN: u8 = 1;
        const CLOSED: u8 = 2;
        let mut state = vec![NEW; self.nodes.len()];
        for root in 0..self.nodes.len() {
            if state[root] != NEW {
                continue;
            }
            state[root] = OPEN;
            let mut stack: Vec<(usize, usize)> = vec![(root, 0)];
            while let Some(&(node, next)) = stack.last() {
                let Some(&GraphNodeIndex(read)) = self.reads[node].get(next) else {
                    state[node] = CLOSED;
                    stack.pop();
                    continue;
                };
                stack.last_mut().expect("the stack holds `node`").1 += 1;
                let read = read as usize;
                match state[read] {
                    NEW => {
                        state[read] = OPEN;
                        stack.push((read, 0));
                    }
                    OPEN => {
                        let start = stack.iter().position(|&(open, _)| open == read).expect("an open node stands on the stack");
                        let mut cycle: Vec<GraphNodeIndex> = stack[start..].iter().map(|&(n, _)| GraphNodeIndex(n as u32)).collect();
                        cycle.sort_by_key(|index| index.0);
                        return Some(cycle);
                    }
                    _ => {}
                }
            }
        }
        None
    }
}

/// What a name read in a case program resolves to.
#[derive(Clone, Debug)]
pub enum Resolution {
    /// A node of the case program's dependency graph.
    Node(GraphNodeIndex),
    /// A name of the lib.
    Lib(LibName),
    /// A relation that no block of the case derives: the case is undefined
    /// on each input where a clause reads it.
    Undefined(ProgramRelation),
    /// A name that resolves to nothing and is no relation a block could
    /// derive: a scope error, which the resolver reports.
    Unresolved,
}

/// A column of a derived relation, resolved to its canonical position: the
/// position of its label in the canonical labeling of the clause, as
/// [`crate::program::canonical::CanonicalLabeling`] gives it. The resolver
/// turns each column name that a read gives into its position.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ColumnPosition(pub u16);

/// The signature of a name a form reads: the canonical form of what the
/// name resolves to, its columns and their types. Two signatures are equal
/// where those canonical forms are, so two reads whose hashes collide have
/// unequal signatures.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Signature(pub crate::program::canonical::CanonicalForm);

/// The resolved content of a node of a case program: its canonical form,
/// with each name it reads standing for the resolved content of what it
/// resolves to. Two contents are equal when their hashes match and then
/// their canonical forms do, whatever file or decode they came from.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct ResolvedContent {
    form: crate::program::canonical::CanonicalForm,
}

impl ResolvedContent {
    /// The hash of the content's canonical form.
    pub fn content_hash(&self) -> StableHash {
        self.form.hash
    }
}

/// A case program after name resolution.
#[derive(Clone, Debug)]
pub struct ResolvedProgram {
    pub program: Node<Program>,
    pub graph: DependencyGraph,
    /// The path of the form of each node of the graph, by its index.
    forms: Box<[NodePath]>,
    resolutions: crate::hash::StableHashMap<NodePath, Resolution>,
    signatures: crate::hash::StableHashMap<NodePath, Signature>,
    positions: crate::hash::StableHashMap<NodePath, ColumnPosition>,
    groups: crate::hash::StableHashMap<NodePath, crate::relations::ColumnGroup>,
    proposer_columns: crate::hash::StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
    names: names::Names,
}

impl ResolvedProgram {
    /// What the name read at `path` resolves to. Each path that a method of
    /// `ResolvedProgram` takes walks as [`crate::program::path::node_at`]
    /// gives.
    pub fn resolution(&self, path: &NodePath) -> Option<&Resolution> {
        self.resolutions.get(path)
    }

    /// The position, in the rows of the relation its atom reads, of the
    /// column that the site at `site` names. A site on a field of a record,
    /// such as `(:P P2)` in `(:key (:P P2))`, names that field's column of
    /// the record's column group, so it is told apart from a column of the
    /// same name, `(:P P2)` beside it.
    ///
    /// A [`crate::program::SiteArg::NamedLabel`] at `site` maps to the column
    /// of the field its name gives where its site reads a record, and to the
    /// site's own column where it does not, so each field of
    /// `(:key P_intile *Col)` has its own position. The value gives the
    /// field, so the mapping needs no layout.
    pub fn column_position(&self, site: &NodePath) -> Option<ColumnPosition> {
        self.positions.get(site).copied()
    }

    /// The column group that the site at `site` reads, where the site is on
    /// a column of a record, the key's or a type parameter's. A
    /// [`crate::program::SiteArg::NamedLabel`] at `site` maps to a column as
    /// [`ResolvedProgram::column_position`] gives.
    pub fn column_group(&self, site: &NodePath) -> Option<crate::relations::ColumnGroup> {
        self.groups.get(site).copied()
    }

    /// The signature of the name read at `path`.
    pub fn signature(&self, path: &NodePath) -> Option<&Signature> {
        self.signatures.get(path)
    }

    /// The path of the form that gives `node` of the graph, so that the cycle
    /// check reports each form on a cycle.
    pub fn form_of(&self, node: GraphNodeIndex) -> &NodePath {
        &self.forms[node.0 as usize]
    }

    /// The resolved content of the node at `path`, or `None` where `path`
    /// names no node. The empty path names the whole program, whose content
    /// is that of its forms, with no order and no names.
    pub fn content(&self, path: &NodePath) -> Option<ResolvedContent> {
        self.names.content(&self.program, path).map(|form| ResolvedContent { form })
    }

    /// The name of the stored parameter's column that each column of the
    /// proposer at `index` of the clause at `clause` stands for, in the
    /// proposer's column order. A `DET_OR_RULE` line maps a proposer's
    /// columns by that order onto the stored parameter's columns, and name
    /// resolution gives each the stored parameter's name.
    pub fn proposer_columns(&self, clause: &NodePath, index: usize) -> Option<&[ColumnName]> {
        self.proposer_columns.get(&(clause.clone(), index)).map(|columns| &columns[..])
    }
}

/// The concept program's resolution, which the `DET` forms that a case
/// takes from the concept program read through: each of those forms, at its
/// path in the case program, resolves its reads in `concept`, so it reads the
/// concept program's derivation in every case, and the case reads its
/// parameter as one node.
#[derive(Clone, Copy, Debug)]
pub struct ConceptReads<'a> {
    pub concept: &'a ResolvedProgram,
    /// The paths in the case program of the concept program's `DET` forms,
    /// as [`crate::solver::Case::concept_determinations`] gives them.
    pub determinations: &'a [NodePath],
}

/// Resolves the names of `case`, a case program that `crate::solver` gives,
/// or a synthesized program. `concept` is `None` for a synthesized program
/// and for the concept case. `derived` holds the relations that some block
/// of the solver derives, as [`crate::solver::Solver::derived_relations`]
/// gives, or a synthesized program's own: a name among them that no block of
/// the case derives is [`Resolution::Undefined`], and a name among none is
/// [`Resolution::Unresolved`].
///
/// Gives a diagnostic of the scope at each name that resolves to nothing and
/// is no relation a block could derive, which resolves to
/// [`Resolution::Unresolved`], so that every other check still runs over
/// the case.
pub fn resolve(
    case: &Node<Program>,
    concept: Option<ConceptReads<'_>>,
    derived: &crate::hash::StableHashSet<ProgramRelation>,
    registry: &Registry,
    macros: MacroExpansion,
) -> WithDiagnostics<ResolvedProgram> {
    match macros {
        MacroExpansion::Keep | MacroExpansion::Expand => build::resolve(case, concept, derived, registry),
    }
}

/// The columns of a relation's rows, as the sites of a read name them.
mod columns {
    use std::sync::Arc;

    use super::ColumnPosition;
    use crate::hash::{StableHashMap, StableHashSet};
    use crate::program::{
        ColumnName, DeclaredName, Demonstrated, Instance, InstanceInput, InstanceName, KeyBody, Node, OutputOwner, OutputStep,
        RelationName, RelationRef, RigidDet, RigidDetName, Site, SiteArg,
    };
    use crate::registry::{Column, ColumnType, Component, LibEntry, LibName, Macro, Port, Proposer, Registry, TypeParameter};
    use crate::relations::{ColumnGroup, ColumnIndex};

    use crate::read::spelling::KEY;

    /// The column of a `RIGID_DET` output that holds the pose,
    /// `docs/arclog/rigid.md#semantics`.
    const POSE: &str = "Pose";
    /// The Example column of a lifted read, `docs/arclog/arclog.md#program`.
    pub(super) const EXAMPLE: &str = "E";
    /// The input of a `DEMONSTRATED` form whose head gives the relation's
    /// columns after the key's, `docs/arclog/arclog.md#demonstrated`.
    const VALUE: &str = "value";

    fn written(name: &str) -> ColumnName {
        ColumnName::Written(name.into())
    }

    /// One column of a relation as a site names it: a column of one row
    /// position, or a record, one row position per field.
    #[derive(Clone, PartialEq, Eq, Debug)]
    pub(super) enum Slot {
        Column(ColumnName),
        Record { name: ColumnName, fields: Box<[ColumnName]> },
    }

    impl Slot {
        fn name(&self) -> &ColumnName {
            match self {
                Slot::Column(name) | Slot::Record { name, .. } => name,
            }
        }

        fn width(&self) -> u16 {
            match self {
                Slot::Column(_) => 1,
                Slot::Record { fields, .. } => fields.len() as u16,
            }
        }

        /// The slot of the column `name` of a head site's port: a record
        /// where `record` gives its fields.
        fn of(name: &ColumnName, record: Option<&[ColumnName]>) -> Slot {
            match record {
                Some(fields) => Slot::Record { name: name.clone(), fields: fields.into() },
                None => Slot::Column(name.clone()),
            }
        }
    }

    /// Where a column path stands in a relation's rows.
    #[derive(Clone, Copy, PartialEq, Eq, Debug)]
    pub(super) enum Place {
        Column(ColumnPosition),
        /// A record's columns, which a site on the record reads.
        Group(ColumnGroup),
        /// A field of a record.
        Field(ColumnPosition, ColumnGroup),
    }

    /// The columns of a relation, in the order of its rows.
    #[derive(Clone, PartialEq, Eq, Debug, Default)]
    pub(super) struct Columns(pub(super) Box<[Slot]>);

    impl Columns {
        pub(super) fn of_names(names: impl IntoIterator<Item = ColumnName>) -> Columns {
            Columns(names.into_iter().map(Slot::Column).collect())
        }

        pub(super) fn names(&self) -> impl Iterator<Item = &ColumnName> + '_ {
            self.0.iter().map(Slot::name)
        }

        /// The place of the column at `path`: a column's name, then, on a
        /// record, a field's. A path past a column of one row position names
        /// that column, as the name of a bare label at a type parameter
        /// bound to one label does.
        pub(super) fn place(&self, path: &[ColumnName]) -> Option<Place> {
            let (first, rest) = path.split_first()?;
            let mut start = 0u16;
            for slot in self.0.iter() {
                if slot.name() == first {
                    return match slot {
                        Slot::Column(_) => Some(Place::Column(ColumnPosition(start))),
                        Slot::Record { fields, .. } => {
                            let group = ColumnGroup { start: ColumnIndex(start), len: slot.width() };
                            match rest.first() {
                                None => Some(Place::Group(group)),
                                Some(field) => {
                                    let index = fields.iter().position(|f| f == field)?;
                                    Some(Place::Field(ColumnPosition(start + index as u16), group))
                                }
                            }
                        }
                    };
                }
                start += slot.width();
            }
            None
        }

        /// The columns of the lifted relation, with the Example column
        /// first, as a `DET` reads a `RULE` relation.
        pub(super) fn lifted(&self) -> Columns {
            Columns(std::iter::once(Slot::Column(written(EXAMPLE))).chain(self.0.iter().cloned()).collect())
        }

        /// Writes the columns: each name, and each record's fields.
        pub(super) fn write(&self, out: &mut crate::program::canonical::CanonicalWriter) {
            super::names::write_len(out, self.0.len());
            for slot in self.0.iter() {
                match slot {
                    Slot::Column(name) => {
                        out.write(&[0]);
                        super::names::write_column_name(out, name);
                    }
                    Slot::Record { name, fields } => {
                        out.write(&[1]);
                        super::names::write_column_name(out, name);
                        super::names::write_len(out, fields.len());
                        for field in fields.iter() {
                            super::names::write_column_name(out, field);
                        }
                    }
                }
            }
        }
    }

    fn of_columns(columns: &[Column]) -> Columns {
        Columns::of_names(columns.iter().map(|column| column.name.clone()))
    }

    /// The columns of a lib relation or a proposer that an atom reads.
    pub(super) fn lib_columns(registry: &Registry, name: &LibName) -> Option<Columns> {
        match registry.entry(name)? {
            LibEntry::Relation(relation) | LibEntry::Macro(Macro::Relation { relation, .. }) => Some(of_columns(&relation.columns)),
            LibEntry::Proposer(Proposer::Native { columns }) => Some(of_columns(columns)),
            LibEntry::Proposer(Proposer::Arclog { columns, .. }) => Some(Columns::of_names(columns.iter().cloned())),
            LibEntry::Component(_) | LibEntry::Macro(Macro::CellInstance { .. }) => None,
        }
    }

    /// The columns of a proposer or a fixed derivation that a `DET` names,
    /// in the proposer's order.
    pub(super) fn proposer_columns(registry: &Registry, name: &LibName) -> Option<Box<[ColumnName]>> {
        match registry.entry(name) {
            Some(LibEntry::Proposer(Proposer::Native { columns })) => Some(columns.iter().map(|c| c.name.clone()).collect()),
            Some(LibEntry::Proposer(Proposer::Arclog { columns, .. })) => Some(columns.clone()),
            _ => registry.derivation(name).map(|derivation| derivation.columns.iter().map(|c| c.name.clone()).collect()),
        }
    }

    /// Whether `name` is a proposer or a fixed derivation that a `DET` can
    /// name.
    pub(super) fn is_proposer(registry: &Registry, name: &LibName) -> bool {
        matches!(registry.entry(name), Some(LibEntry::Proposer(_))) || registry.derivation(name).is_some()
    }

    /// The component an `INIT` form names: a construction, a detector, a
    /// task-structure component or a cell instance.
    pub(super) fn component<'r>(registry: &'r Registry, name: &LibName) -> Option<&'r Component> {
        match registry.entry(name)? {
            LibEntry::Component(component) | LibEntry::Macro(Macro::CellInstance { component, .. }) => Some(component),
            LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(Macro::Relation { .. }) => None,
        }
    }

    /// The fields of the record that the head site `site` projects onto
    /// its column's type parameter, or `None` where it projects one label.
    fn projection(site: &Site) -> Option<Box<[ColumnName]>> {
        match &site.value.args[..] {
            [SiteArg::Label(_) | SiteArg::NamedLabel { .. }] => None,
            args => Some(
                args.iter()
                    .filter_map(|arg| match arg {
                        SiteArg::NamedLabel { name, .. } => Some(name.clone()),
                        SiteArg::Field(field) => Some(field.column.clone()),
                        SiteArg::Label(_) => None,
                    })
                    .collect(),
            ),
        }
    }

    fn key_fields(key: &KeyBody) -> Box<[ColumnName]> {
        key.columns.iter().map(|column| column.name.clone()).collect()
    }

    /// The inputs an `INIT` or a `DEMONSTRATED` form writes: the keyed
    /// inputs, then the others.
    pub(super) fn written_inputs<'a>(
        key: Option<&'a Node<crate::program::KeyClause>>,
        inputs: &'a [Node<InstanceInput>],
    ) -> impl Iterator<Item = &'a InstanceInput> + Clone {
        key.into_iter().flat_map(|key| key.value().inputs.iter()).chain(inputs.iter()).map(|input| input.value())
    }

    /// The records that an `INIT` form binds the type parameters of its
    /// component to: the key clause binds the parameter of the `key` column
    /// to a record of its `^` labels, and the first projection onto each
    /// other parameter binds it, as `docs/arclog/arclog.md#instance` gives. A
    /// parameter that it leaves out is bound to one label's type, or, for an
    /// instance with no key clause, to `Unit`.
    pub(super) struct Bindings(StableHashMap<TypeParameter, Box<[ColumnName]>>);

    pub(super) fn bindings(instance: &Instance, component: &Component) -> Bindings {
        let mut records = StableHashMap::default();
        let mut bound = StableHashSet::default();
        if let Some(key) = &instance.key {
            let parameter = component.inputs.iter().flat_map(|input| input.port.columns.iter()).find_map(|column| match &column.ty {
                ColumnType::Parameter(parameter) if column.name == written(KEY) => Some(parameter),
                _ => None,
            });
            if let Some(parameter) = parameter {
                records.insert(parameter.clone(), key_fields(&key.value().key));
                bound.insert(parameter.clone());
            }
        }
        for input in written_inputs(instance.key.as_ref(), &instance.inputs) {
            let Some(port) = component.inputs.iter().find(|port| port.port.name == input.name) else { continue };
            for site in input.head.iter() {
                let Some(column) = port.port.columns.iter().find(|column| column.name == site.column) else { continue };
                let ColumnType::Parameter(parameter) = &column.ty else { continue };
                if bound.insert(parameter.clone()) {
                    if let Some(fields) = projection(site) {
                        records.insert(parameter.clone(), fields);
                    }
                }
            }
        }
        Bindings(records)
    }

    /// The columns of `port` of an instance whose binding is `bindings`.
    pub(super) fn port_columns(port: &Port, bindings: &Bindings) -> Columns {
        Columns(
            port.columns
                .iter()
                .map(|column| match &column.ty {
                    ColumnType::Parameter(parameter) => Slot::of(&column.name, bindings.0.get(parameter).map(|f| &f[..])),
                    _ => Slot::Column(column.name.clone()),
                })
                .collect(),
        )
    }

    fn key_slot(key: Option<&KeyBody>) -> Slot {
        Slot::of(&written(KEY), key.map(key_fields).as_deref())
    }

    /// The columns of a `DEMONSTRATED` form's relation: the key's, then
    /// those the `value` head names, `docs/arclog/arclog.md#demonstrated`.
    pub(super) fn demonstrated_columns(form: &Demonstrated) -> Columns {
        let key = key_slot(form.key.as_ref().map(|key| &key.value().key));
        let value = written_inputs(form.key.as_ref(), &form.inputs).find(|input| *input.name.0 == *VALUE);
        let heads = value.into_iter().flat_map(|input| input.head.iter()).map(|site| Slot::of(&site.column, projection(site).as_deref()));
        Columns(std::iter::once(key).chain(heads).collect())
    }

    /// The path after the form's name of the output of a `RIGID_DET` form
    /// for the part that reads `relation`: `&marker.glyph` for a part that
    /// reads `&glyph`, `&marker.bbox.box` for one that reads `&bbox.box`.
    fn part_steps(relation: &RelationRef) -> Option<Vec<OutputStep>> {
        let (owner, rest): (&DeclaredName, &[OutputStep]) = match relation {
            RelationRef::Declared(RelationName(name)) => (name, &[]),
            RelationRef::Output(output) => match &output.of {
                OutputOwner::Instance(InstanceName(name)) | OutputOwner::RigidDet(RigidDetName(name)) => (name, &output.path[..]),
            },
            RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => return None,
        };
        Some(std::iter::once(OutputStep::Part(owner.clone())).chain(rest.iter().cloned()).collect())
    }

    /// Each output of a `RIGID_DET` form, by its path after the form's
    /// name, with its columns, as `docs/arclog/rigid.md#semantics` gives:
    /// the key's, `:Pose` and the part's for a part, and the key's, the
    /// instance's and `:Pose` for `.pose`.
    pub(super) fn rigid_outputs(form: &RigidDet) -> Vec<(Arc<[OutputStep]>, Columns)> {
        let key: Option<Slot> = form.key.as_ref().map(|key| key_slot(Some(key)));
        let pose = Slot::Column(written(POSE));
        let mut outputs: Vec<(Arc<[OutputStep]>, Columns)> = form
            .parts
            .iter()
            .filter_map(|part| {
                let part = part.value();
                let steps = part_steps(&part.relation)?;
                let sites = part.sites.iter().map(|site| Slot::Column(site.column.clone()));
                Some((steps.into(), Columns(key.iter().cloned().chain([pose.clone()]).chain(sites).collect())))
            })
            .collect();
        let instance = form.instance.iter().flat_map(|instance| instance.columns.iter()).map(|column| Slot::Column(column.name.clone()));
        outputs.push((Arc::from([OutputStep::Pose]), Columns(key.into_iter().chain(instance).chain([pose]).collect())));
        outputs
    }
}

/// The names of a case program after resolution, and the resolved content
/// they write: the [`NameWriter`](crate::program::canonical::NameWriter) of
/// the resolver.
mod names {
    use std::sync::Arc;

    use super::columns::{Columns, Place};
    use super::GraphNodeIndex;
    use crate::hash::StableHashMap;
    use crate::program::canonical::{AsWritten, Canonical, CanonicalForm, CanonicalWriter, NameWriter, SearchBudget};
    use crate::program::path::{NodePath, NodeRef};
    use crate::program::{
        Body, ColumnName, DeclaredName, NameScope, Node, OutputOwner, OutputStep, Program, RelationRef,
    };
    use crate::registry::LibName;

    pub(super) fn write_len(out: &mut CanonicalWriter, len: usize) {
        out.write(&u32::try_from(len).expect("a list of fewer than 2^32 members").to_le_bytes());
    }

    fn write_text(out: &mut CanonicalWriter, text: &str) {
        write_len(out, text.len());
        out.write(text.as_bytes());
    }

    fn write_declared(out: &mut CanonicalWriter, name: &DeclaredName) {
        match name {
            DeclaredName::Written(text) => {
                out.write(&[0]);
                write_text(out, text);
            }
            DeclaredName::Slot(slot) => {
                out.write(&[1]);
                out.write(&slot.to_le_bytes());
            }
        }
    }

    pub(super) fn write_column_name(out: &mut CanonicalWriter, name: &ColumnName) {
        match name {
            ColumnName::Written(text) => {
                out.write(&[0]);
                write_text(out, text);
            }
            ColumnName::Slot(slot) => {
                out.write(&[1]);
                out.write(&slot.to_le_bytes());
            }
        }
    }

    pub(super) fn write_port(out: &mut CanonicalWriter, port: &crate::program::PortName) {
        out.write(&[0]);
        write_text(out, &port.0);
    }

    /// Writes the path after the form's name of an output that `relation`
    /// reads, which tells apart the outputs of one node.
    pub(super) fn write_steps(out: &mut CanonicalWriter, relation: &RelationRef) {
        let RelationRef::Output(output) = relation else { return };
        write_len(out, output.path.len());
        for step in output.path.iter() {
            match step {
                OutputStep::Port(port) => write_port(out, port),
                OutputStep::Part(part) => {
                    out.write(&[1]);
                    write_declared(out, part);
                }
                OutputStep::Pose => out.write(&[2]),
            }
        }
    }

    /// The form of `parts` sorted, after the mark `kind` and before `tail`,
    /// so the content of a node of several forms has no order.
    pub(super) fn combined(kind: u8, parts: impl IntoIterator<Item = Arc<[u8]>>, tail: &[u8]) -> CanonicalForm {
        let mut parts: Vec<Arc<[u8]>> = parts.into_iter().collect();
        parts.sort();
        let mut out = CanonicalWriter::default();
        out.write(&[kind]);
        write_len(&mut out, parts.len());
        for part in &parts {
            write_len(&mut out, part.len());
            out.write(part);
        }
        out.write(tail);
        out.finish()
    }

    /// The mark of each kind of name or column a resolved content writes.
    #[derive(Clone, Copy)]
    #[repr(u8)]
    enum Mark {
        /// The relation the form being written declares, or one of its
        /// columns.
        Own,
        /// A name as the file writes it: a fact, a lib name, or a name that
        /// resolves to no node.
        Written,
        /// The resolved content of a node.
        Content,
        /// A node whose content is not yet written, on a cycle.
        Open,
        Position,
        Group,
    }

    /// The relation that the form being written declares: a relation, or the
    /// owner of the outputs of an `INIT` or a `RIGID_DET` form.
    #[derive(Clone, PartialEq, Eq, Debug)]
    pub(super) enum Own {
        Relation(RelationRef),
        Owner(OutputOwner),
    }

    impl Own {
        /// The relation that the form at `node` declares.
        pub(super) fn of(node: NodeRef<'_>) -> Option<Own> {
            use crate::program::{InstanceName, ProgramRelation, RelationName, RigidDetName};
            let declared = |name: &RelationName| Own::Relation(RelationRef::Declared(name.clone()));
            match node {
                NodeRef::Clause(clause) => Some(Own::Relation(match &clause.derives {
                    ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
                    ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
                })),
                NodeRef::Choose(choose) => Some(declared(&choose.name)),
                NodeRef::Demonstrated(demonstrated) => Some(declared(&demonstrated.name)),
                NodeRef::Instance(instance) => Some(Own::Owner(OutputOwner::Instance(InstanceName::clone(&instance.name)))),
                NodeRef::RigidDet(rigid) => Some(Own::Owner(OutputOwner::RigidDet(RigidDetName::clone(&rigid.name)))),
                _ => None,
            }
        }

        fn holds(&self, relation: &RelationRef) -> bool {
            match self {
                Own::Relation(own) => own == relation,
                Own::Owner(owner) => matches!(relation, RelationRef::Output(output) if output.of == *owner),
            }
        }
    }

    /// What a relation name resolves to in one scope: its node, and its
    /// columns, where they are known before the node's content.
    #[derive(Clone, Debug)]
    pub(super) struct Target {
        pub(super) node: GraphNodeIndex,
        pub(super) columns: ColumnsOf,
    }

    #[derive(Clone, Debug)]
    pub(super) enum ColumnsOf {
        Fixed(Columns),
        /// The columns of the clause or the `CHOOSE` form of the node, in
        /// the canonical positions of their labels.
        OfNode,
    }

    /// The names of a case program after resolution: what each name of each
    /// scope resolves to, the content and the columns of each node, and the
    /// columns of each lib name the program reads.
    #[derive(Clone, Debug, Default)]
    pub(super) struct Names {
        pub(super) scopes: StableHashMap<NameScope, StableHashMap<RelationRef, Target>>,
        pub(super) contents: Vec<Option<CanonicalForm>>,
        pub(super) node_columns: Vec<Option<Columns>>,
        pub(super) lib: StableHashMap<LibName, Columns>,
        /// The content of each form that resolves in the concept program,
        /// as [`super::ConceptReads`] gives, by its path.
        pub(super) fixed: StableHashMap<NodePath, CanonicalForm>,
    }

    impl Names {
        /// The target of `relation` read in `scope`: its declaration in
        /// `scope`, or in the program's.
        pub(super) fn find(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Target> {
            let in_scope = |scope: &NameScope| self.scopes.get(scope).and_then(|names| names.get(relation));
            in_scope(scope).or_else(|| in_scope(&NameScope::Program))
        }

        /// The columns of `relation` read in `scope`, where they are known.
        pub(super) fn columns(&self, scope: &NameScope, relation: &RelationRef) -> Option<&Columns> {
            if let RelationRef::Lib(name) = relation {
                return self.lib.get(name);
            }
            let target = self.find(scope, relation)?;
            match &target.columns {
                ColumnsOf::Fixed(columns) => Some(columns),
                ColumnsOf::OfNode => self.node_columns.get(target.node.0 as usize)?.as_ref(),
            }
        }

        /// The resolved content of the node at `path` of `program`.
        pub(super) fn content(&self, program: &Node<Program>, path: &NodePath) -> Option<CanonicalForm> {
            if path.0.is_empty() {
                let forms: Option<Vec<Arc<[u8]>>> = (0..program.value().forms.len())
                    .map(|index| self.content(program, &NodePath(Box::new([crate::program::path::PathStep(index as u32)]))).map(|form| form.bytes))
                    .collect();
                return Some(combined(0, forms?, &[]));
            }
            if let Some(form) = self.fixed.get(path) {
                return Some(form.clone());
            }
            let mut node = NodeRef::Program(program.value());
            let mut scope = NameScope::Program;
            let mut own = None;
            let mut atom = None;
            for (depth, step) in path.0.iter().enumerate() {
                node = *node.children().get(step.0 as usize)?;
                match node {
                    NodeRef::DemoRule(_) => scope = NameScope::DemoRule(NodePath(path.0[..=depth].into())),
                    NodeRef::Conjunct(crate::program::Conjunct::Atom(found) | crate::program::Conjunct::Not(crate::program::Negated::Atom(found))) => {
                        atom = Some(found.value())
                    }
                    NodeRef::Atom(found) => atom = Some(found),
                    _ => {}
                }
                own = Own::of(node).or(own);
            }
            let writer = Writer { names: self, scope: &scope, own: own.as_ref() };
            written(node, atom, &writer)
        }
    }

    /// The canonical form of `node` through `writer`. A site or a bare label
    /// is written as the atom `atom` that holds it, with that site alone.
    pub(super) fn written(node: NodeRef<'_>, atom: Option<&crate::program::Atom>, writer: &Writer<'_>) -> Option<CanonicalForm> {
        let mut out = CanonicalWriter::default();
        let search = &mut SearchBudget::new();
        let out_ = &mut out;
        match node {
            NodeRef::Program(value) => value.write_canonical(out_, search, writer),
            NodeRef::Claim(value) => value.write_canonical(out_, search, writer),
            NodeRef::Clause(value) => value.write_canonical(out_, search, writer),
            NodeRef::Instance(value) => value.write_canonical(out_, search, writer),
            NodeRef::KeyClause(value) => value.write_canonical(out_, search, writer),
            NodeRef::InstanceInput(value) => value.write_canonical(out_, search, writer),
            NodeRef::Choose(value) => value.write_canonical(out_, search, writer),
            NodeRef::RigidDet(value) => value.write_canonical(out_, search, writer),
            NodeRef::Demonstrated(value) => value.write_canonical(out_, search, writer),
            NodeRef::DemoRule(value) => value.write_canonical(out_, search, writer),
            NodeRef::Alts(value) => value.write_canonical(out_, search, writer),
            NodeRef::Alt(value) => value.write_canonical(out_, search, writer),
            NodeRef::Body(value) => value.write_canonical(out_, search, writer),
            NodeRef::Atom(value) => value.write_canonical(out_, search, writer),
            NodeRef::Conjunct(conjunct) => Body { conjuncts: Arc::from([conjunct.clone()]) }.write_canonical(out_, search, writer),
            NodeRef::Site(_) | NodeRef::Label(_) => {
                let atom = atom?;
                let site = match node {
                    NodeRef::Site(site) => site.clone(),
                    _ => atom.sites.iter().find(|site| site.value.args.iter().any(|arg| holds_label(node, arg)))?.clone(),
                };
                crate::program::Atom { relation: atom.relation.clone(), sites: Arc::from([site]) }.write_canonical(out_, search, writer)
            }
        }
        Some(out.finish())
    }

    /// Whether `arg` is the bare label at `node`.
    fn holds_label(node: NodeRef<'_>, arg: &crate::program::SiteArg) -> bool {
        use crate::program::SiteArg;
        match (node, arg) {
            (NodeRef::Label(found), SiteArg::Label(label) | SiteArg::NamedLabel { label, .. }) => std::ptr::eq(found, label),
            _ => false,
        }
    }

    /// The resolver's name writer: each name a node reads as the resolved
    /// content of what it resolves to in `scope`, and each column a read
    /// names as its position.
    pub(super) struct Writer<'n> {
        pub(super) names: &'n Names,
        pub(super) scope: &'n NameScope,
        pub(super) own: Option<&'n Own>,
    }

    impl Writer<'_> {
        fn own(&self, relation: &RelationRef) -> Option<&Own> {
            self.own.filter(|own| own.holds(relation))
        }
    }

    impl NameWriter for Writer<'_> {
        fn write_name(&self, relation: &RelationRef, out: &mut CanonicalWriter) {
            if self.own(relation).is_some() {
                out.write(&[Mark::Own as u8]);
                write_steps(out, relation);
                return;
            }
            let target = match relation {
                RelationRef::Declared(_) | RelationRef::Output(_) => self.names.find(self.scope, relation),
                RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
            };
            match target.map(|target| &self.names.contents[target.node.0 as usize]) {
                Some(Some(content)) => {
                    out.write(&[Mark::Content as u8]);
                    out.write(&content.hash.0.to_le_bytes());
                    write_steps(out, relation);
                }
                Some(None) => {
                    out.write(&[Mark::Open as u8]);
                    AsWritten.write_name(relation, out);
                }
                None => {
                    out.write(&[Mark::Written as u8]);
                    AsWritten.write_name(relation, out);
                }
            }
        }

        /// Writes a column of the form's own relation by a mark that no
        /// labeling sets, since the labeling gives that column's position.
        fn write_column(&self, relation: &RelationRef, column: &[ColumnName], out: &mut CanonicalWriter) {
            match self.own(relation) {
                Some(Own::Relation(_)) => return out.write(&[Mark::Own as u8]),
                Some(Own::Owner(_)) => {
                    out.write(&[Mark::Own as u8]);
                    return AsWritten.write_column(relation, column, out);
                }
                None => {}
            }
            match self.names.columns(self.scope, relation).and_then(|columns| columns.place(column)) {
                Some(Place::Column(position) | Place::Field(position, _)) => {
                    out.write(&[Mark::Position as u8]);
                    out.write(&position.0.to_le_bytes());
                }
                Some(Place::Group(group)) => {
                    out.write(&[Mark::Group as u8]);
                    out.write(&group.start.0.to_le_bytes());
                    out.write(&group.len.to_le_bytes());
                }
                None => {
                    out.write(&[Mark::Written as u8]);
                    AsWritten.write_column(relation, column, out);
                }
            }
        }
    }
}

/// The passes of [`resolve`]: the declarations of each scope, the reads and
/// the graph, the content and the columns of each node, then the columns of
/// each site.
mod build {
    use std::collections::BTreeSet;
    use std::sync::Arc;

    use super::columns::{self, Columns, Place};
    use super::names::{combined, write_port, write_steps, ColumnsOf, Names, Own, Target, Writer};
    use super::{
        ColumnPosition, ConceptReads, DependencyGraph, DependencyKind, DependencyNode, GraphNodeIndex, ResolvedProgram,
        Resolution, Signature,
    };
    use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity, WithDiagnostics};
    use crate::hash::{StableHashMap, StableHashSet};
    use crate::program::canonical::{canonical_labeling, relation_of, AsWritten, CanonicalWriter, LabelScope, NameWriter, SearchBudget};
    use crate::program::path::{node_at, NodePath, NodeRef};
    use crate::program::{
        Atom, Choose, Clause, ClauseKeyword, ColumnName, Conjunct, DeclaredName, FactRelation, Form, Instance, InstanceName,
        NameScope, Negated, Node, OutputName, OutputOwner, OutputStep, PortName, Program, ProgramRelation, RelationName,
        RelationRef,
    };
    use crate::registry::{Component, Registry};
    use crate::relations::ColumnGroup;

    /// The nodes of one `INIT` form: the node that reads each input it
    /// writes, the node of each output, and its component.
    struct InstanceNodes<'r> {
        inputs: Vec<(PortName, GraphNodeIndex)>,
        outputs: Vec<(PortName, GraphNodeIndex)>,
        columns: StableHashMap<PortName, Columns>,
        component: &'r Component,
    }

    impl InstanceNodes<'_> {
        fn input(&self, name: &PortName) -> Option<GraphNodeIndex> {
            self.inputs.iter().find(|(port, _)| port == name).map(|(_, node)| *node)
        }

        fn every(&self) -> Vec<GraphNodeIndex> {
            let nodes: BTreeSet<u32> = self.inputs.iter().chain(self.outputs.iter()).map(|(_, node)| node.0).collect();
            nodes.into_iter().map(GraphNodeIndex).collect()
        }
    }

    struct Builder<'a> {
        case: &'a Node<Program>,
        registry: &'a Registry,
        derived: &'a StableHashSet<ProgramRelation>,
        nodes: Vec<DependencyNode>,
        index: StableHashMap<DependencyNode, GraphNodeIndex>,
        /// The paths of the forms of each node.
        forms: Vec<Vec<NodePath>>,
        reads: Vec<BTreeSet<u32>>,
        /// The node of each form that gives one node.
        form_node: StableHashMap<NodePath, GraphNodeIndex>,
        instances: StableHashMap<(NameScope, InstanceName), InstanceNodes<'a>>,
        names: Names,
        /// The path in the concept program of each form that resolves there.
        concept_forms: StableHashMap<NodePath, NodePath>,
        /// The columns of each relation that a form resolving in the concept
        /// program derives, as the concept program gives them.
        concept_columns: StableHashMap<NodePath, Option<Columns>>,
        atoms: Vec<(NodePath, &'a Atom, NameScope)>,
        clauses: Vec<(NodePath, &'a Clause)>,
        resolutions: StableHashMap<NodePath, Resolution>,
        signatures: StableHashMap<NodePath, Signature>,
        positions: StableHashMap<NodePath, ColumnPosition>,
        groups: StableHashMap<NodePath, ColumnGroup>,
        proposer_columns: StableHashMap<(NodePath, usize), Box<[ColumnName]>>,
        diagnostics: Vec<Diagnostic>,
    }

    pub(super) fn resolve(
        case: &Node<Program>,
        concept: Option<ConceptReads<'_>>,
        derived: &StableHashSet<ProgramRelation>,
        registry: &Registry,
    ) -> WithDiagnostics<ResolvedProgram> {
        let mut builder = Builder {
            case,
            registry,
            derived,
            nodes: Vec::new(),
            index: StableHashMap::default(),
            forms: Vec::new(),
            reads: Vec::new(),
            form_node: StableHashMap::default(),
            instances: StableHashMap::default(),
            names: Names::default(),
            concept_forms: StableHashMap::default(),
            concept_columns: StableHashMap::default(),
            atoms: Vec::new(),
            clauses: Vec::new(),
            resolutions: StableHashMap::default(),
            signatures: StableHashMap::default(),
            positions: StableHashMap::default(),
            groups: StableHashMap::default(),
            proposer_columns: StableHashMap::default(),
            diagnostics: Vec::new(),
        };
        for fact in [FactRelation::Input, FactRelation::ExInput, FactRelation::ExOutput] {
            let node = builder.node(DependencyKind::Fact(fact), &NameScope::Program, None);
            let columns = Columns::of_names(registry.fact_columns(fact).iter().map(|column| column.name.clone()));
            builder.target(&NameScope::Program, RelationRef::Fact(fact), Target { node, columns: ColumnsOf::Fixed(columns) });
        }
        if let Some(concept) = concept {
            builder.take_concept(concept);
        }
        let forms = &case.value().forms;
        let mut pending = Vec::new();
        for (index, form) in forms.iter().enumerate() {
            builder.declare(form, top(index), &NameScope::Program, &mut pending);
        }
        for (scope, relation, target) in pending {
            builder.target(&scope, relation, target);
        }
        for (index, form) in forms.iter().enumerate() {
            builder.read_form(form, top(index), &NameScope::Program);
        }
        builder.contents();
        builder.sites();
        builder.proposers();
        if let Some(concept) = concept {
            builder.copy_concept(concept);
        }
        builder.finish()
    }

    fn top(index: usize) -> NodePath {
        NodePath(Box::new([crate::program::path::PathStep(index as u32)]))
    }

    /// `path` with its prefix `from` replaced by `to`, where `from` is a
    /// prefix of it.
    fn rebase(path: &NodePath, from: &NodePath, to: &NodePath) -> Option<NodePath> {
        path.0.strip_prefix(&from.0[..]).map(|rest| to.join(&NodePath(rest.into())))
    }

    /// The tag of each kind of node in its content.
    fn kind_tag(kind: &DependencyKind) -> u8 {
        match kind {
            DependencyKind::Fact(_) => 1,
            DependencyKind::Clause(_) => 2,
            DependencyKind::InstanceInput { .. } => 3,
            DependencyKind::InstanceOutput { .. } => 4,
            DependencyKind::Parameter(_) => 5,
            DependencyKind::Chosen(_) => 6,
            DependencyKind::RigidAssembly(_) => 7,
            DependencyKind::Demonstrated(_) => 8,
            DependencyKind::RecursiveInstance(_) => 9,
        }
    }

    /// The node kind of a clause: a chosen relation where it has `ONE`
    /// marks, a parameter where it is a `DET` with none, and a clause
    /// relation otherwise.
    fn clause_kind(clause: &Clause) -> DependencyKind {
        match (&clause.derives, clause.ones.is_empty(), clause.keyword) {
            (ProgramRelation::Declared(name), false, _) => DependencyKind::Chosen(name.clone()),
            (relation, _, ClauseKeyword::Det) => DependencyKind::Parameter(relation.clone()),
            (relation, _, _) => DependencyKind::Clause(relation.clone()),
        }
    }

    fn prediction() -> RelationRef {
        let name = format!("{}prediction", crate::read::spelling::DECLARED_MARK);
        RelationRef::Declared(RelationName(DeclaredName::Written(name.into())))
    }

    impl<'a> Builder<'a> {
        /// The node of `kind` in `scope`, made on its first use, with the
        /// form at `form` among its forms.
        fn node(&mut self, kind: DependencyKind, scope: &NameScope, form: Option<&NodePath>) -> GraphNodeIndex {
            let key = DependencyNode { kind, scope: scope.clone() };
            let node = match self.index.get(&key) {
                Some(node) => *node,
                None => {
                    let node = GraphNodeIndex(self.nodes.len() as u32);
                    self.index.insert(key.clone(), node);
                    self.nodes.push(key);
                    self.forms.push(Vec::new());
                    self.reads.push(BTreeSet::new());
                    node
                }
            };
            if let Some(form) = form {
                self.forms[node.0 as usize].push(form.clone());
            }
            node
        }

        fn target(&mut self, scope: &NameScope, relation: RelationRef, target: Target) {
            self.names.scopes.entry(scope.clone()).or_default().insert(relation, target);
        }

        fn read(&mut self, reader: GraphNodeIndex, read: GraphNodeIndex) {
            self.reads[reader.0 as usize].insert(read.0);
        }

        fn unresolved(&mut self, path: &NodePath, name: &str) -> Resolution {
            self.diagnostics.push(Diagnostic {
                kind: DiagnosticKind::Check(crate::check::CheckId::Scope),
                severity: Severity::Error,
                message: format!("`{name}` names nothing visible here").into(),
                location: Location::Path(path.clone()),
                cases: Box::default(),
            });
            Resolution::Unresolved
        }

        /// Finds in the concept program each `DET` form that the case takes
        /// from it.
        fn take_concept(&mut self, concept: ConceptReads<'_>) {
            let concept_forms = &concept.concept.program.value().forms;
            for path in concept.determinations {
                let Some(Form::Clause(clause)) = path.0.first().and_then(|step| self.case.value().forms.get(step.0 as usize)) else { continue };
                let Some(index) = concept_forms.iter().position(|form| matches!(form, Form::Clause(other) if other == clause)) else { continue };
                let concept_path = top(index);
                let Some(content) = concept.concept.content(&concept_path) else { continue };
                let relation = relation_of(&clause.value().derives);
                let columns = concept.concept.names.columns(&NameScope::Program, &relation).cloned();
                self.names.fixed.insert(path.clone(), content.form);
                self.concept_columns.insert(path.clone(), columns);
                self.concept_forms.insert(path.clone(), concept_path);
            }
        }

        /// Copies from the concept program what each form that resolves
        /// there resolves to, apart from its nodes, which are the concept
        /// program's.
        fn copy_concept(&mut self, concept: ConceptReads<'_>) {
            let concept = concept.concept;
            let mut forms: Vec<(&NodePath, &NodePath)> = self.concept_forms.iter().collect();
            forms.sort();
            for (path, concept_path) in forms {
                for (at, resolution) in &concept.resolutions {
                    if matches!(resolution, Resolution::Node(_)) {
                        continue;
                    }
                    if let Some(at) = rebase(at, concept_path, path) {
                        self.resolutions.insert(at, resolution.clone());
                    }
                }
                for (at, signature) in &concept.signatures {
                    if let Some(at) = rebase(at, concept_path, path) {
                        self.signatures.insert(at, signature.clone());
                    }
                }
                for (at, position) in &concept.positions {
                    if let Some(at) = rebase(at, concept_path, path) {
                        self.positions.insert(at, *position);
                    }
                }
                for (at, group) in &concept.groups {
                    if let Some(at) = rebase(at, concept_path, path) {
                        self.groups.insert(at, *group);
                    }
                }
                for ((at, index), columns) in &concept.proposer_columns {
                    if let Some(at) = rebase(at, concept_path, path) {
                        self.proposer_columns.insert((at, *index), columns.clone());
                    }
                }
            }
        }

        /// Declares what `form` at `path` declares in `scope`. The relations
        /// that a clause, a `CHOOSE` or a `DEMONSTRATED` form declares go to
        /// `pending`, so that a clause on an output of an instance, such as
        /// a `RULE_OR_DET` line on `&ring.value`, stands for that output.
        fn declare(&mut self, form: &'a Form, path: NodePath, scope: &NameScope, pending: &mut Vec<(NameScope, RelationRef, Target)>) {
            match form {
                Form::Claim(claim) => {
                    for (index, form) in claim.value().forms.iter().enumerate() {
                        self.declare(form, path.child(index as u32), scope, pending);
                    }
                }
                Form::Alts(_) => {}
                Form::Clause(clause) => {
                    let clause = clause.value();
                    let node = self.node(clause_kind(clause), scope, Some(&path));
                    self.form_node.insert(path.clone(), node);
                    pending.push((scope.clone(), relation_of(&clause.derives), Target { node, columns: ColumnsOf::OfNode }));
                    if !self.concept_forms.contains_key(&path) {
                        self.clauses.push((path, clause));
                    }
                }
                Form::Choose(choose) => {
                    let name = &choose.value().name;
                    let node = self.node(DependencyKind::Chosen(name.clone()), scope, Some(&path));
                    self.form_node.insert(path, node);
                    pending.push((scope.clone(), RelationRef::Declared(name.clone()), Target { node, columns: ColumnsOf::OfNode }));
                }
                Form::Demonstrated(demonstrated) => {
                    let demonstrated = demonstrated.value();
                    let node = self.node(DependencyKind::Demonstrated(demonstrated.name.clone()), scope, Some(&path));
                    self.form_node.insert(path.clone(), node);
                    let columns = ColumnsOf::Fixed(columns::demonstrated_columns(demonstrated));
                    pending.push((scope.clone(), RelationRef::Declared(demonstrated.name.clone()), Target { node, columns }));
                    let before = u32::from(demonstrated.key.is_some()) + demonstrated.inputs.len() as u32;
                    for (index, rule) in demonstrated.rules.iter().enumerate() {
                        let rule_path = path.child(before + index as u32);
                        let rule_scope = NameScope::DemoRule(rule_path.clone());
                        for (index, form) in rule.value().forms.iter().enumerate() {
                            self.declare(form, rule_path.child(index as u32), &rule_scope, pending);
                        }
                    }
                }
                Form::RigidDet(rigid) => {
                    let rigid = rigid.value();
                    let node = self.node(DependencyKind::RigidAssembly(rigid.name.clone()), scope, Some(&path));
                    self.form_node.insert(path, node);
                    for (steps, columns) in columns::rigid_outputs(rigid) {
                        let relation = RelationRef::Output(OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path: steps });
                        self.target(scope, relation, Target { node, columns: ColumnsOf::Fixed(columns) });
                    }
                }
                Form::Instance(instance) => self.declare_instance(instance.value(), path, scope),
            }
        }

        /// Declares the nodes of an `INIT` form: one node for an instance
        /// whose inputs read its outputs, and otherwise a node per input it
        /// writes and per output, each output reading every input.
        fn declare_instance(&mut self, instance: &'a Instance, path: NodePath, scope: &NameScope) {
            let Some(component) = columns::component(self.registry, &instance.component) else {
                let resolution = self.unresolved(&path, &instance.component.0);
                self.resolutions.insert(path, resolution);
                return;
            };
            self.resolutions.insert(path.clone(), Resolution::Lib(instance.component.clone()));
            let name = &instance.name;
            let written: Vec<_> = columns::written_inputs(instance.key.as_ref(), &instance.inputs).collect();
            let mut inputs = Vec::new();
            let mut outputs = Vec::new();
            if component.inputs.iter().any(|input| input.reads_outputs) {
                let node = self.node(DependencyKind::RecursiveInstance(name.clone()), scope, Some(&path));
                inputs.extend(written.iter().map(|input| (input.name.clone(), node)));
                outputs.extend(component.outputs.iter().map(|output| (output.name.clone(), node)));
            } else {
                for input in &written {
                    let kind = DependencyKind::InstanceInput { instance: name.clone(), input: input.name.clone() };
                    inputs.push((input.name.clone(), self.node(kind, scope, Some(&path))));
                }
                for output in component.outputs.iter() {
                    let kind = DependencyKind::InstanceOutput { instance: name.clone(), output: output.name.clone() };
                    let node = self.node(kind, scope, Some(&path));
                    for (_, input) in &inputs {
                        self.read(node, *input);
                    }
                    outputs.push((output.name.clone(), node));
                }
            }
            let bindings = columns::bindings(instance, component);
            let mut port_columns = StableHashMap::default();
            let relation = |port: &PortName| {
                RelationRef::Output(OutputName { of: OutputOwner::Instance(name.clone()), path: Arc::from([OutputStep::Port(port.clone())]) })
            };
            for input in component.inputs.iter() {
                let columns = columns::port_columns(&input.port, &bindings);
                let read = inputs.iter().find(|(port, _)| *port == input.port.name);
                if let Some((port, node)) = read.filter(|(port, _)| !component.outputs.iter().any(|output| output.name == *port)) {
                    self.target(scope, relation(port), Target { node: *node, columns: ColumnsOf::Fixed(columns.clone()) });
                }
                port_columns.insert(input.port.name.clone(), columns);
            }
            for (output, (port, node)) in component.outputs.iter().zip(&outputs) {
                let columns = columns::port_columns(output, &bindings);
                self.target(scope, relation(port), Target { node: *node, columns: ColumnsOf::Fixed(columns.clone()) });
                port_columns.insert(port.clone(), columns);
            }
            self.instances.insert((scope.clone(), name.clone()), InstanceNodes { inputs, outputs, columns: port_columns, component });
        }

        /// Resolves the reads of `form` at `path` in `scope`, and adds each
        /// to the graph as an edge from the node read to the node that reads
        /// it.
        fn read_form(&mut self, form: &'a Form, path: NodePath, scope: &NameScope) {
            match form {
                Form::Claim(claim) => {
                    for (index, form) in claim.value().forms.iter().enumerate() {
                        self.read_form(form, path.child(index as u32), scope);
                    }
                }
                Form::Alts(_) => {}
                Form::Clause(clause) => {
                    if self.concept_forms.contains_key(&path) {
                        return;
                    }
                    let clause = clause.value();
                    let node = self.form_node[&path];
                    for proposer in clause.proposers.iter() {
                        if !columns::is_proposer(self.registry, proposer) {
                            self.unresolved(&path, &proposer.0);
                        }
                    }
                    self.read_below(NodeRef::Body(clause.body.value()), path.child(0), scope, &[node]);
                    self.read_instance_line(clause, node, scope);
                }
                Form::Instance(instance) => {
                    let instance = instance.value();
                    let Some(nodes) = self.instances.get(&(scope.clone(), instance.name.clone())) else { return };
                    let every = nodes.every();
                    let reader = |input: &PortName| nodes.input(input).expect("a node of each input the form writes");
                    let mut readers: Vec<(NodeRef<'a>, NodePath, Vec<GraphNodeIndex>)> = Vec::new();
                    let mut before = 0;
                    if let Some(key) = &instance.key {
                        let key = key.value();
                        let key_path = path.child(0);
                        readers.push((NodeRef::Body(key.key.body.value()), key_path.child(0), every.clone()));
                        for (index, input) in key.inputs.iter().enumerate() {
                            readers.push((NodeRef::InstanceInput(input.value()), key_path.child(1 + index as u32), vec![reader(&input.value().name)]));
                        }
                        before = 1;
                    }
                    for (index, input) in instance.inputs.iter().enumerate() {
                        readers.push((NodeRef::InstanceInput(input.value()), path.child(before + index as u32), vec![reader(&input.value().name)]));
                    }
                    for (node, at, readers) in readers {
                        self.read_below(node, at, scope, &readers);
                    }
                }
                Form::Choose(_) | Form::RigidDet(_) => {
                    let node = self.form_node[&path];
                    self.read_below(NodeRef::from(form), path, scope, &[node]);
                }
                Form::Demonstrated(demonstrated) => {
                    let demonstrated = demonstrated.value();
                    let node = self.form_node[&path];
                    let mut before = 0;
                    if let Some(key) = &demonstrated.key {
                        self.read_below(NodeRef::KeyClause(key.value()), path.child(0), scope, &[node]);
                        before = 1;
                    }
                    for (index, input) in demonstrated.inputs.iter().enumerate() {
                        self.read_below(NodeRef::InstanceInput(input.value()), path.child(before + index as u32), scope, &[node]);
                    }
                    let before = before + demonstrated.inputs.len() as u32;
                    for (index, rule) in demonstrated.rules.iter().enumerate() {
                        let rule_path = path.child(before + index as u32);
                        let rule_scope = NameScope::DemoRule(rule_path.clone());
                        for (index, form) in rule.value().forms.iter().enumerate() {
                            self.read_form(form, rule_path.child(index as u32), &rule_scope);
                        }
                        let prediction = self.names.scopes.get(&rule_scope).and_then(|names| names.get(&prediction())).map(|target| target.node);
                        if let Some(prediction) = prediction {
                            self.read(node, prediction);
                        }
                    }
                }
            }
        }

        /// Adds the edges of a clause on a port of an instance: the
        /// instance reads a clause on one of its inputs, as a
        /// `DET_OR_RULE` line on `&canvas.extent`, and a clause on one of its
        /// outputs, as a `RULE_OR_DET` line on `&ring.value`, reads that
        /// output.
        fn read_instance_line(&mut self, clause: &Clause, node: GraphNodeIndex, scope: &NameScope) {
            let ProgramRelation::Output(output) = &clause.derives else { return };
            let (OutputOwner::Instance(name), [OutputStep::Port(port)]) = (&output.of, &output.path[..]) else { return };
            let Some(nodes) = self.instances.get(&(scope.clone(), name.clone())) else { return };
            let edges: Vec<(GraphNodeIndex, GraphNodeIndex)> = if nodes.component.inputs.iter().any(|input| input.port.name == *port) {
                nodes.outputs.iter().map(|(_, output)| (*output, node)).collect()
            } else {
                nodes.outputs.iter().filter(|(name, _)| name == port).map(|(_, output)| (node, *output)).collect()
            };
            for (reader, read) in edges {
                if reader != read {
                    self.read(reader, read);
                }
            }
        }

        /// Resolves each atom below `node`, at `path`, as read by each node
        /// of `readers`.
        fn read_below(&mut self, node: NodeRef<'a>, path: NodePath, scope: &NameScope, readers: &[GraphNodeIndex]) {
            match node {
                NodeRef::Conjunct(Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom))) => self.read_atom(atom.value(), path, scope, readers),
                NodeRef::Atom(atom) => self.read_atom(atom, path, scope, readers),
                NodeRef::DemoRule(_) => {}
                _ => {
                    for (index, child) in node.children().into_iter().enumerate() {
                        self.read_below(child, path.child(index as u32), scope, readers);
                    }
                }
            }
        }

        fn read_atom(&mut self, atom: &'a Atom, path: NodePath, scope: &NameScope, readers: &[GraphNodeIndex]) {
            let resolution = self.resolve_name(scope, &atom.relation, &path);
            if let Resolution::Node(read) = resolution {
                for &reader in readers {
                    let recursive = matches!(self.nodes[reader.0 as usize].kind, DependencyKind::RecursiveInstance(_));
                    if !(recursive && reader == read) {
                        self.read(reader, read);
                    }
                }
            }
            self.resolutions.insert(path.clone(), resolution);
            self.atoms.push((path, atom, scope.clone()));
        }

        fn resolve_name(&mut self, scope: &NameScope, relation: &RelationRef, path: &NodePath) -> Resolution {
            let name = || crate::write::relation_ref(relation);
            let program_relation = match relation {
                RelationRef::Lib(lib) => {
                    if self.registry.entry(lib).is_none() {
                        return self.unresolved(path, &name());
                    }
                    if let Some(columns) = columns::lib_columns(self.registry, lib) {
                        self.names.lib.insert(lib.clone(), columns);
                    }
                    return Resolution::Lib(lib.clone());
                }
                RelationRef::DefinedPort(_) => return self.unresolved(path, &name()),
                RelationRef::Fact(_) => None,
                RelationRef::Declared(declared) => Some(ProgramRelation::Declared(declared.clone())),
                RelationRef::Output(output) => Some(ProgramRelation::Output(output.clone())),
            };
            if let Some(target) = self.names.find(scope, relation) {
                return Resolution::Node(target.node);
            }
            match program_relation {
                Some(program_relation) if self.derived.contains(&program_relation) => Resolution::Undefined(program_relation),
                _ => self.unresolved(path, &name()),
            }
        }

        /// The content and the columns of each node, each node after the
        /// nodes it reads, where no cycle holds it.
        fn contents(&mut self) {
            self.names.contents = vec![None; self.nodes.len()];
            self.names.node_columns = vec![None; self.nodes.len()];
            let mut visited = vec![false; self.nodes.len()];
            for node in 0..self.nodes.len() {
                self.content_of(node, &mut visited);
            }
        }

        fn content_of(&mut self, node: usize, visited: &mut Vec<bool>) {
            if std::mem::replace(&mut visited[node], true) {
                return;
            }
            let reads: Vec<u32> = self.reads[node].iter().copied().collect();
            for read in reads {
                self.content_of(read as usize, visited);
            }
            let (content, columns) = self.node_content(node);
            self.names.contents[node] = Some(content);
            self.names.node_columns[node] = columns;
        }

        /// The content of `node`: its kind and its forms, each written
        /// through the resolver's name writer, with no order; and its
        /// columns, those of its form of least content, where its columns
        /// come from its form.
        fn node_content(&self, node: usize) -> (crate::program::canonical::CanonicalForm, Option<Columns>) {
            let DependencyNode { kind, scope } = &self.nodes[node];
            let mut tail = CanonicalWriter::default();
            match kind {
                DependencyKind::Fact(fact) => AsWritten.write_name(&RelationRef::Fact(*fact), &mut tail),
                DependencyKind::InstanceInput { input: port, .. } | DependencyKind::InstanceOutput { output: port, .. } => {
                    write_port(&mut tail, port)
                }
                _ => {}
            }
            let tail = tail.finish().bytes;
            let mut parts: Vec<(Arc<[u8]>, Option<Columns>)> = Vec::new();
            for path in &self.forms[node] {
                let form = node_at(NodeRef::Program(self.case.value()), path).expect("the path of a form of the case");
                let own = Own::of(form);
                let writer = Writer { names: &self.names, scope, own: own.as_ref() };
                let bytes = match self.names.fixed.get(path) {
                    Some(content) => content.bytes.clone(),
                    None => super::names::written(form, None, &writer).expect("a form has a canonical form").bytes,
                };
                let columns = match form {
                    NodeRef::Clause(clause) => match self.concept_columns.get(path) {
                        Some(columns) => columns.clone(),
                        None => self.clause_columns(clause, scope, &writer),
                    },
                    NodeRef::Choose(choose) => Some(choose_columns(choose, &writer)),
                    _ => None,
                };
                parts.push((bytes, columns));
            }
            parts.sort_by(|a, b| a.0.cmp(&b.0));
            let columns = parts.iter().find_map(|(_, columns)| columns.clone());
            (combined(kind_tag(kind), parts.into_iter().map(|(bytes, _)| bytes), &tail), columns)
        }

        /// The columns of the relation a clause derives: its labels in their
        /// canonical positions; or, with no columns of its own, its first
        /// proposer's, or the output's of an instance it stands for.
        fn clause_columns(&self, clause: &Clause, scope: &NameScope, writer: &Writer<'_>) -> Option<Columns> {
            if !clause.columns.is_empty() {
                let labeling = canonical_labeling(LabelScope::Clause(clause), writer, &mut SearchBudget::new());
                return Some(ordered(&clause.columns, &labeling));
            }
            if let Some(proposer) = clause.proposers.first() {
                return columns::proposer_columns(self.registry, proposer).map(|names| Columns::of_names(names.into_vec()));
            }
            if let ProgramRelation::Output(OutputName { of: OutputOwner::Instance(name), path }) = &clause.derives {
                if let [OutputStep::Port(port)] = &path[..] {
                    return self.instances.get(&(scope.clone(), name.clone())).and_then(|nodes| nodes.columns.get(port)).cloned();
                }
            }
            Some(Columns::default())
        }

        /// The position and the group of each site of each atom read, and
        /// the signature of each name read.
        fn sites(&mut self) {
            let atoms = std::mem::take(&mut self.atoms);
            for (path, atom, scope) in &atoms {
                let mut columns = self.names.columns(scope, &atom.relation).cloned();
                let reads_example = atom.sites.iter().any(|site| site.column == ColumnName::Written(columns::EXAMPLE.into()));
                let declared = matches!(atom.relation, RelationRef::Declared(_) | RelationRef::Output(_));
                if let Some(found) = columns.as_ref().filter(|found| declared && reads_example && found.place(&[ColumnName::Written(columns::EXAMPLE.into())]).is_none()) {
                    columns = Some(found.lifted());
                }
                if let Some(columns) = &columns {
                    for (index, site) in atom.sites.iter().enumerate() {
                        self.place_site(columns, site, path.child(index as u32));
                    }
                }
                let signature = self.signature(&self.resolutions[path], &atom.relation, columns.as_ref());
                self.signatures.insert(path.clone(), signature);
            }
        }

        fn place_site(&mut self, columns: &Columns, site: &crate::program::Site, path: NodePath) {
            use crate::program::SiteArg;
            match columns.place(std::slice::from_ref(&site.column)) {
                Some(Place::Column(position)) => {
                    for (index, arg) in site.value.args.iter().enumerate() {
                        if let SiteArg::NamedLabel { .. } = arg {
                            self.positions.insert(path.child(index as u32), position);
                        }
                    }
                    self.positions.insert(path, position);
                }
                Some(Place::Group(group)) => {
                    for (index, arg) in site.value.args.iter().enumerate() {
                        let field = match arg {
                            SiteArg::NamedLabel { name, .. } => name,
                            SiteArg::Field(field) => &field.column,
                            SiteArg::Label(_) => continue,
                        };
                        if let Some(Place::Field(position, group)) = columns.place(&[site.column.clone(), field.clone()]) {
                            self.positions.insert(path.child(index as u32), position);
                            self.groups.insert(path.child(index as u32), group);
                        }
                    }
                    self.groups.insert(path, group);
                }
                Some(Place::Field(..)) | None => {}
            }
        }

        /// The signature of a read of `relation` that resolves to
        /// `resolution`: the content of what it resolves to, and its
        /// columns.
        fn signature(&self, resolution: &Resolution, relation: &RelationRef, columns: Option<&Columns>) -> Signature {
            let mut out = CanonicalWriter::default();
            match resolution {
                Resolution::Node(node) => {
                    out.write(&[0]);
                    let content = self.names.contents[node.0 as usize].as_ref().expect("the content of each node");
                    out.write(&content.hash.0.to_le_bytes());
                    write_steps(&mut out, relation);
                }
                Resolution::Lib(_) => out.write(&[1]),
                Resolution::Undefined(_) => out.write(&[2]),
                Resolution::Unresolved => out.write(&[3]),
            }
            if !matches!(resolution, Resolution::Node(_)) {
                AsWritten.write_name(relation, &mut out);
            }
            match columns {
                Some(columns) => {
                    out.write(&[1]);
                    columns.write(&mut out);
                }
                None => out.write(&[0]),
            }
            Signature(out.finish())
        }

        /// The stored parameter's column that each column of each proposer
        /// of each clause stands for, by position: the clause's columns in
        /// the order it gives them, or, with none, its first proposer's.
        fn proposers(&mut self) {
            for (path, clause) in std::mem::take(&mut self.clauses) {
                let first = clause.proposers.first().and_then(|proposer| columns::proposer_columns(self.registry, proposer));
                let stored: Box<[ColumnName]> = if clause.columns.is_empty() {
                    first.unwrap_or_default()
                } else {
                    clause.columns.iter().map(|column| column.name.clone()).collect()
                };
                for (index, proposer) in clause.proposers.iter().enumerate() {
                    if let Some(own) = columns::proposer_columns(self.registry, proposer) {
                        let mapped = own.iter().zip(stored.iter()).map(|(_, name)| name.clone()).collect();
                        self.proposer_columns.insert((path.clone(), index), mapped);
                    }
                }
            }
        }

        fn finish(self) -> WithDiagnostics<ResolvedProgram> {
            let graph = DependencyGraph {
                nodes: self.nodes.into(),
                reads: self.reads.into_iter().map(|reads| reads.into_iter().map(GraphNodeIndex).collect()).collect(),
            };
            let forms = self.forms.into_iter().map(|forms| forms.into_iter().next().unwrap_or_default()).collect();
            WithDiagnostics {
                value: ResolvedProgram {
                    program: self.case.clone(),
                    graph,
                    forms,
                    resolutions: self.resolutions,
                    signatures: self.signatures,
                    positions: self.positions,
                    groups: self.groups,
                    proposer_columns: self.proposer_columns,
                    names: self.names,
                },
                diagnostics: self.diagnostics,
            }
        }
    }

    /// `columns` in the order of their labels' positions in `labeling`.
    fn ordered(columns: &[crate::program::RelationColumn], labeling: &crate::program::canonical::CanonicalLabeling) -> Columns {
        let position = |label| labeling.positions.iter().find(|(found, _)| *found == label).map(|(_, position)| *position);
        let mut ordered: Vec<(Option<u32>, &ColumnName)> = columns.iter().map(|column| (position(column.label), &column.name)).collect();
        ordered.sort_by_key(|(position, _)| *position);
        Columns::of_names(ordered.into_iter().map(|(_, name)| name.clone()))
    }

    /// The columns of a chosen relation: the row's, in the order of the
    /// `for` clause, then the candidate's, in their canonical positions,
    /// `docs/arclog/constraints.md#choose`.
    fn choose_columns(choose: &Choose, writer: &Writer<'_>) -> Columns {
        let labeling = canonical_labeling(LabelScope::Choose(choose), writer, &mut SearchBudget::new());
        let rows = choose.rows.iter().flat_map(|rows| rows.columns.iter()).map(|column| column.name.clone());
        let candidate = ordered(&choose.candidate_columns, &labeling);
        Columns::of_names(rows.chain(candidate.names().cloned()))
    }
}
