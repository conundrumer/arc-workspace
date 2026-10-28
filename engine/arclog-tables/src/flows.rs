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
//! that body, which the walk gets from [`CheckedProgram::body_ir`].
//! [`IrPaths`] gives the path of each atom of the IR.
//!
//! A source also gives the frames its column's values stand in
//! ([`SourceFrame`]), which `columns` resolves where it knows the tables of
//! the case. A source of a program relation or a fact gives the frame of the
//! column it reads. A source computed through a lib atom, or declared by an
//! instance's output, gives what the registry's frame rule for the column
//! gives it ([`FrameRule`]), so a chain of lib atoms nests the made frames.
//! A constant and a copy of a lib relation's column give none, nor does a lib
//! name but that of a component's output column whose rule makes a frame,
//! which gives the made frame. A source that a D4 element moves gives an
//! unknown frame.

use std::collections::BTreeMap;
use std::ops::Range;

use arclog::algebra::geometry::Geometry;
use arclog::algebra::algebra;
use arclog::check::CheckedProgram;
use arclog::eval::body_ir::BodyIr;
use arclog::eval::ir::{atom_modes, Argument, Arguments, AtomSource, ClauseIr, IrNode, IrPaths, NodePaths, Operand, Union, Variable, VariableInfo};
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{column_spelled, Atom, ColumnName, Conjunct, ConstraintOp, FactRelation, LabelId, OutputOwner, OutputStep, PortName, RelationRef};
use arclog::registry::{is_key, key_fill, ColumnType, FrameRule, LibName, Registry};
use arclog::resolver::given::{node_relation, Given, GivenLabel};
use arclog::resolver::registry_columns;
use arclog::resolver::{DependencyKind, GraphNodeIndex, ResolvedProgram, Resolution};
use arclog::types::ValueType;

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

/// How a source gives the frame its column's values stand in.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SourceFrame {
    /// The frame of the column the source reads.
    Read,
    /// A frame that the lib column `maker` makes, one per row of the atom or
    /// the instance at `at`. It lies in the frame that `within` gives, where
    /// that is some.
    Made { maker: Maker, at: NodePath, within: Option<Box<SourceFrame>> },
    /// A frame the engine cannot name: a D4 element moves the values.
    Unknown,
}

/// The lib column that makes a frame.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Maker {
    /// The column of a lib relation or a relation macro.
    Relation { relation: LibName, column: ColumnName },
    /// The column of an output of a component.
    Output { component: LibName, output: PortName, column: ColumnName },
}

impl Maker {
    /// `<relation>.<column>`, such as `relative.X_rel`, or
    /// `<component>.<output>.<column>`, such as `Division.tile.P_inner`.
    pub fn spelled(&self) -> String {
        match self {
            Maker::Relation { relation, column } => format!("{}.{}", relation.0, column_spelled(column)),
            Maker::Output { component, output, column } => format!("{}.{}.{}", component.0, output.0, column_spelled(column)),
        }
    }
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
    /// For a source that an atom reads, which row of that atom's relation the
    /// value comes from in one derivation of the table's row: 0 for the atom
    /// of a clause, whose value comes from that atom's one row, and the index
    /// of the declared row for a column of an instance's output that the
    /// registry's `copies` maps. Two copy flows into one table with the same
    /// atom and the same occurrence read one row of their source. `None`
    /// claims no row: a source of no atom, and a source of a column of an
    /// instance's output that no declared row maps.
    pub occurrence: Option<u16>,
    /// The frames the source gives its column's values, empty where it gives
    /// none: a constant and a copy of a lib relation's column give none, and a
    /// lib name gives the made frame of an output column whose rule makes one.
    /// Two sources that differ only here are one source, which gives the
    /// frames of both (`add_distinct`).
    pub frames: Vec<SourceFrame>,
}

/// The frame rule of the lib column that computes a column's values, with the
/// frame the column makes where the rule makes one: its `maker`, and the path
/// `at` of the atom or the `INIT` form that makes it.
struct RuleAt<'a> {
    rule: &'a FrameRule,
    maker: &'a Maker,
    at: &'a NodePath,
}

impl RuleAt<'_> {
    fn made(&self, within: Option<SourceFrame>) -> SourceFrame {
        SourceFrame::Made { maker: self.maker.clone(), at: self.at.clone(), within: within.map(Box::new) }
    }
}

impl ColumnSource {
    fn without_atom(kind: SourceKind, relation: Option<RelationRef>) -> Self {
        ColumnSource { kind, relation, column: SourceColumn::None, row: None, atom: NodePath::default(), occurrence: None, frames: Vec::new() }
    }

    fn with_frames(mut self, frames: Vec<SourceFrame>) -> Self {
        self.frames = frames;
        self
    }

    /// Whether `other` is this source but for the frames.
    fn same_source(&self, other: &ColumnSource) -> bool {
        (self.kind, &self.relation, self.column, &self.row, &self.atom, self.occurrence) == (other.kind, &other.relation, other.column, &other.row, &other.atom, other.occurrence)
    }

    /// This source, which computes a column's values through a lib column
    /// whose frame rule is `rule_at`, as the column's source: `named` is
    /// whether the rule names the column that this source reads. Under
    /// `(of ...)` a named source keeps its frames, under `new` each source
    /// gives the made frame, and under `(new (of ...))` a named source gives
    /// the made frame lying in each frame it gave, or in none where it gave
    /// none. A source of no named column gives none, and so does every source
    /// where there is no rule.
    fn framed(mut self, rule_at: Option<&RuleAt<'_>>, named: bool) -> Self {
        let kept = if named { std::mem::take(&mut self.frames) } else { Vec::new() };
        self.frames = match rule_at {
            None => Vec::new(),
            Some(rule_at) if rule_at.rule.makes && rule_at.rule.of.is_empty() => vec![rule_at.made(None)],
            Some(rule_at) if rule_at.rule.makes && named && kept.is_empty() => vec![rule_at.made(None)],
            Some(rule_at) if rule_at.rule.makes => kept.into_iter().map(|frame| rule_at.made(Some(frame))).collect(),
            Some(_) => kept,
        };
        self
    }

    fn computed(mut self) -> Self {
        self.kind = SourceKind::Computed;
        self
    }

    /// This source as a declared row reads it: the row's index as the
    /// occurrence where an atom reads it, and none otherwise.
    fn in_row(mut self, row: usize) -> Self {
        self.occurrence = if self.atom.0.is_empty() { None } else { Some(u16::try_from(row).expect("fewer than 2^16 declared rows")) };
        self
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
                    hits.push(Hit { node, paths, column: column.0 });
                }
            }
        }
        hits
    }
}

/// Whether `clause`, or a branch in it, has an argument of an atom on a
/// variable of `class`, or an `=` comparison of one.
fn touches(clause: &ClauseIr, class: &[Variable]) -> bool {
    let on = |arguments: &Arguments| arguments.0.iter().any(|(_, argument)| matches!(argument, Argument::Variable(variable) if class.contains(variable)));
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
        let frames = if matches!(relation, RelationRef::Lib(_)) { Vec::new() } else { vec![SourceFrame::Read] };
        vec![ColumnSource { kind: SourceKind::Copy, relation: Some(relation), column, row, atom: path.clone(), occurrence: Some(0), frames }]
    }

    /// The sources of `variable` in `alt`, which `visiting` holds the
    /// variables being resolved above: the union over the alternatives of
    /// `alt` that choose a branch of each `OR` and `IF` that binds the
    /// variable's class. In each, a variable that stands at a site of a
    /// positive atom of a program relation or a fact gets a copy of each
    /// such column, and a variable bound to `0` is a constant. A variable
    /// that only lib atoms bind is computed from the variables at the columns
    /// of a mode of the atom that the alternative binds elsewhere, and
    /// otherwise copies the lib relation's column. A variable of an
    /// orientation type whose class stands at no atom, which the evaluator
    /// binds by the type's domain, copies the column of the lib relation of
    /// one column that holds that domain ([`domain_relation`]), with no atom
    /// and no occurrence.
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
                _ => program.push(hit),
            }
        }
        let mut found: Vec<ColumnSource> = Vec::new();
        if zero {
            found.push(ColumnSource::without_atom(SourceKind::Constant, None));
        }
        if !zero && hits.is_empty() {
            let ty = alt.variables.get(usize::from(variable.0)).map(|info| &info.ty);
            found.extend(ty.and_then(|ty| domain_relation(self.flows.registry, ty)).map(|relation| ColumnSource {
                column: SourceColumn::Position(0),
                ..ColumnSource::without_atom(SourceKind::Copy, Some(RelationRef::Lib(relation)))
            }));
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
    /// column. A mode holds where each of its bound columns holds `0` or a
    /// variable with sources, and at least one holds a variable: a mode whose
    /// bound columns hold only `0` computes from no variable. Each computed
    /// source gives the frames that the registry's rule for the column at the
    /// mode gives it ([`ColumnSource::framed`]), made at the atom, and none
    /// where the variable it comes from has type `Offset`.
    fn lib_sources(&self, hit: &Hit<'_>, alt: &Alt<'_>, visiting: &mut Vec<Variable>) -> Vec<ColumnSource> {
        let (IrNode::Lib(lib), Some((path, atom))) = (hit.node, self.atom_of(hit.paths)) else { return Vec::new() };
        let program = self.flows.program;
        let position_of = |column: &ColumnName| {
            let (index, _) = atom.sites.iter().enumerate().find(|(_, site)| &site.column == column)?;
            program.column_position(&path.child(index as u32)).map(|position| position.0)
        };
        let here = atom.sites.iter().find(|site| position_of(&site.column) == Some(hit.column)).map(|site| &site.column);
        let lib_name = match &atom.relation {
            RelationRef::Lib(name) => Some(name),
            _ => None,
        };
        let maker = lib_name.zip(here).map(|(name, column)| Maker::Relation { relation: name.clone(), column: column.clone() });
        let mut computed = Vec::new();
        let mut holds = false;
        for mode in atom_modes(self.flows.registry, atom) {
            if here.is_some_and(|column| mode.bound.contains(column)) {
                continue;
            }
            let rule = lib_name.zip(here).and_then(|(name, column)| self.flows.registry.relation_frame(name, mode, column));
            let rule_at = rule.as_ref().zip(maker.as_ref()).map(|(rule, maker)| RuleAt { rule, maker, at: path });
            let mut from = Vec::new();
            let mut bound = true;
            let mut reads_variable = false;
            for column in mode.bound.iter() {
                let Some(position) = position_of(column) else {
                    bound = false;
                    break;
                };
                let named = rule.as_ref().is_some_and(|rule| rule.names(None, column));
                for (_, argument) in lib.arguments.0.iter().filter(|(at, _)| at.0 == position) {
                    let Argument::Variable(variable) = argument else { continue };
                    reads_variable = true;
                    let sources = self.sources(*variable, alt, visiting);
                    bound &= !sources.is_empty();
                    let offset = alt.variables.get(usize::from(variable.0)).is_some_and(|info| info.ty == ValueType::Offset);
                    from.extend(sources.into_iter().map(|source| {
                        let source = source.computed().framed(rule_at.as_ref(), named);
                        if offset { source.with_frames(Vec::new()) } else { source }
                    }));
                }
            }
            if bound && reads_variable {
                holds = true;
                computed.extend(from);
            }
        }
        if holds { computed } else { self.read(hit) }
    }
}

/// The lib relation of one column that holds each constant of the orientation
/// type `ty`, such as `axis_elem` for `Axis`, or `None` where `ty` is no
/// orientation type or the registry has no such relation. A one-column
/// relation of `ty` with fewer rows, such as `d4_identity`, is not it.
fn domain_relation(registry: &Registry, ty: &ValueType) -> Option<LibName> {
    ty.orientation_types()?;
    let domain = Geometry::get().domain(ty).len();
    let mut found = registry.names().filter(|&name| {
        let Some(relation) = registry.algebra_relation(name) else { return false };
        let [column] = &*relation.columns else { return false };
        if column.ty.fixed() != Some(ty) || !relation.modes.is_empty() {
            return false;
        }
        let mut rows = 0;
        let Some(algebra) = algebra(name) else { return false };
        let counted = algebra.evaluate(&[None], registry, &mut |_| rows += 1);
        counted.is_ok() && rows == domain
    });
    let name = found.next()?;
    found.next().is_none().then(|| name.clone())
}

/// The walk over the dependency graph: the program, the checked program
/// that gives the evaluator's IR of a body, and the registry.
struct Flows<'p> {
    checked: &'p CheckedProgram,
    program: &'p ResolvedProgram,
    registry: &'p Registry,
}

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
///   computed; a label of an orientation type whose class stands at no
///   atom, a copy of the column of the lib relation that holds the type's
///   domain, such as `axis_elem`; a key label in the class, in a body of a
///   keyed form that binds the class at no site of a positive atom, gives the sources
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
/// - a column of an instance's output that a declared row of the
///   registry's `copies` maps: in place of the sources above, the sources
///   of the input column that the row maps it from, as the instance's
///   written body for that input gives them (a computed source staying
///   computed), the lib name where the input has a default, and the
///   fill's sources where it is `from-key` and unwritten. The output's
///   `key`, where a declared row is on an input with a `key` column, keeps
///   its sources and takes beside them the sources of the key's labels in
///   the bodies the instance writes for that input;
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
/// The occurrence of a source ([`ColumnSource::occurrence`]) is 0 for a
/// source that an atom of a body reads, a computed one included. A source
/// that a declared row maps into a column of an instance's output has the
/// index of that row among the output's where an atom reads it. Each other
/// source of a column of an instance's output has none.
///
/// An output of an instance that reads its own outputs has no flow from
/// them.
///
/// A source that names a column of an input port of an instance is
/// replaced by the sources of that port's column, through each chain of
/// input ports, because the export makes no table for a port.
pub fn column_flows(checked: &CheckedProgram, node: GraphNodeIndex, output: Option<&[OutputStep]>, types: &[ValueType], registry: &Registry) -> Vec<Vec<ColumnSource>> {
    let flows = Flows { checked, program: &checked.program, registry };
    flows.flows_visiting(node, output, types.len(), types, &mut Vec::new())
}

/// What a form's column gives to the row positions of its relation.
enum Placed<'g> {
    /// A column with a label written at a path of it, which stands at `position`.
    Labelled { slot: usize, position: usize, label: &'g GivenLabel },
    /// A column of a declared type that no label is written at, which takes
    /// the row `positions` of its width.
    Declared { slot: usize, positions: Range<usize> },
}

/// The column of a form's relation that stands at a row position of the
/// table, and the label the form writes at it.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Placement {
    /// The index of the column in the relation's own column order, as
    /// [`arclog::resolver::given::Given::slots`] lists the columns; a record's
    /// fields share the index of their record.
    pub slot: u32,
    /// The label written at the position, none for a column of a declared type.
    pub label: Option<LabelId>,
}

/// The [`Placement`] at each of the `width` row positions of the relation of
/// `node`, whose read names `output`, as the form at `form` gives it: none at a
/// position that the form's columns do not reach. Where several labels stand at
/// a position, the first in the order of the form's columns. A clause with no
/// columns of its own stores the columns of its first proposer or of its
/// instance's port in their declared order, so each of its row positions
/// stands at the slot of its column in that order, with no label.
pub fn column_placements(checked: &CheckedProgram, node: GraphNodeIndex, output: Option<&[OutputStep]>, form: &NodePath, width: usize, registry: &Registry) -> Vec<Option<Placement>> {
    let flows = Flows { checked, program: &checked.program, registry };
    let mut placements: Vec<Option<Placement>> = vec![None; width];
    let mut place = |slot: usize, positions: Range<usize>, label: Option<LabelId>| {
        let slot = u32::try_from(slot).expect("fewer than 2^32 columns");
        for position in positions {
            if let Some(held @ None) = placements.get_mut(position) {
                *held = Some(Placement { slot, label });
            }
        }
    };
    for relation in flows.given_at(node, output).iter().filter(|relation| relation.form == *form) {
        for placed in flows.placements(relation) {
            match placed {
                Placed::Labelled { slot, position, label } => place(slot, position..position + 1, Some(label.label)),
                Placed::Declared { slot, positions } => place(slot, positions, None),
            }
        }
        if relation.slots.is_empty() {
            if let Some(paths) = checked.program.row_paths(node).filter(|paths| paths.len() == width) {
                for (position, slot) in record_slots(&paths).into_iter().enumerate() {
                    place(slot, position..position + 1, None);
                }
            }
        }
    }
    placements
}

/// The frame rule at each of the `width` row positions of the relation of
/// `node`, an output of the instance at `form`, whose read names `output`: none
/// at a position that is no declared column of the output or whose column has
/// no frame.
pub fn output_frames(checked: &CheckedProgram, node: GraphNodeIndex, output: Option<&[OutputStep]>, form: &NodePath, width: usize, registry: &Registry) -> Vec<Option<OutputFrame>> {
    let flows = Flows { checked, program: &checked.program, registry };
    let mut frames: Vec<Option<OutputFrame>> = vec![None; width];
    for relation in flows.given_at(node, output).iter().filter(|relation| relation.form == *form) {
        for placed in flows.placements(relation) {
            let Placed::Declared { slot, positions } = placed else { continue };
            let Some(frame) = flows.output_frame(relation, slot) else { continue };
            for position in positions {
                if let Some(held @ None) = frames.get_mut(position) {
                    *held = Some(frame.clone());
                }
            }
        }
    }
    frames
}

/// The input columns that the declared rows of the registry's `copies` map
/// each of the `width` row positions of the relation of `node`, an output of
/// the instance at `form` whose read names `output`, from, as the row positions
/// of each in the rows of its input: a position that no row maps has none.
pub fn output_copies(checked: &CheckedProgram, node: GraphNodeIndex, output: Option<&[OutputStep]>, form: &NodePath, width: usize, registry: &Registry) -> Vec<Vec<(PortName, Range<usize>)>> {
    let flows = Flows { checked, program: &checked.program, registry };
    let mut copies: Vec<Vec<(PortName, Range<usize>)>> = vec![Vec::new(); width];
    for relation in flows.given_at(node, output).iter().filter(|relation| relation.form == *form) {
        for placed in flows.placements(relation) {
            let Placed::Declared { slot, positions } = placed else { continue };
            let copied = flows.copied_from(relation, slot);
            for (offset, position) in positions.enumerate() {
                if let Some(held) = copies.get_mut(position).filter(|held| held.is_empty()) {
                    // The row position of the column a copy of the input column's field at the same offset.
                    *held = copied.iter().filter_map(|(port, range)| (offset < range.len()).then(|| (port.clone(), range.start + offset..range.start + offset + 1))).collect();
                }
            }
        }
    }
    copies
}

/// The index among the columns of a relation of each of its row positions,
/// given the path of each: a record's fields, which share the first name of
/// their paths, share the index of their record.
fn record_slots(paths: &[Box<[ColumnName]>]) -> Vec<usize> {
    let mut slots = Vec::new();
    for (index, path) in paths.iter().enumerate() {
        let field_of_previous = index > 0 && path.len() > 1 && paths[index - 1].len() > 1 && paths[index - 1][0] == path[0];
        let slot = match slots.last() {
            None => 0,
            Some(&previous) if field_of_previous => previous,
            Some(&previous) => previous + 1,
        };
        slots.push(slot);
    }
    slots
}

impl<'p> Flows<'p> {
    /// [`column_flows`], where `visiting` holds the nodes
    /// being resolved above `node`. A column of a position that `types`
    /// leaves out has a type no D4 element moves.
    fn flows_visiting(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>, width: usize, types: &[ValueType], visiting: &mut Vec<GraphNodeIndex>) -> Vec<Vec<ColumnSource>> {
        visiting.push(node);
        let mut flows: Vec<Vec<ColumnSource>> = vec![Vec::new(); width];
        let given = self.given_at(node, output);
        let mut held: BTreeMap<(usize, NodePath), Option<BodyIr>> = BTreeMap::new();
        // The frame that the registry's rule makes at each row position of an output of an instance, where it makes one.
        let mut made: Vec<Option<SourceFrame>> = vec![None; width];
        for (which, relation) in given.iter().enumerate() {
            for placed in self.placements(relation) {
                match placed {
                    Placed::Labelled { slot, position, label: GivenLabel { label, body, .. } } => {
                        let body = held.entry((which, body.clone())).or_insert_with(|| self.checked.body_ir(self.registry, relation, body));
                        let found = self.label_sources(body.as_ref(), *label, visiting);
                        let moved = slot >= relation.sites_from && types.get(position).is_some_and(ValueType::moved_by_d4);
                        if let Some(sources) = flows.get_mut(position) {
                            add_distinct(sources, if moved { found.into_iter().map(|source| source.computed().with_frames(vec![SourceFrame::Unknown])).collect() } else { found });
                        }
                    }
                    Placed::Declared { slot, positions } => {
                        let frame = self.output_frame(relation, slot);
                        for position in positions {
                            if let Some(sources) = flows.get_mut(position) {
                                add_distinct(sources, self.declared_sources(node, frame.as_ref(), visiting));
                                made[position] = frame.as_ref().filter(|frame| frame.rule.makes).map(|frame| frame.rule_at().made(None));
                            }
                        }
                    }
                }
            }
        }
        for relation in &given {
            self.add_key_fill(relation, types, &mut flows);
        }
        let mut copied = vec![false; width];
        for relation in &given {
            self.add_copied_rows(relation, types, &mut flows, &mut copied, visiting);
        }
        let kind = &self.program.graph.nodes[node.0 as usize].kind;
        if let DependencyKind::RecursiveInstance(instance) = kind {
            let own = |source: &ColumnSource| matches!(&source.relation, Some(RelationRef::Output(name)) if name.of == OutputOwner::Instance(instance.clone()));
            for sources in &mut flows {
                sources.retain(|source| !own(source));
            }
        }
        if matches!(kind, DependencyKind::InstanceOutput { .. } | DependencyKind::RecursiveInstance(_)) {
            for (sources, _) in flows.iter_mut().zip(&copied).filter(|(_, copied)| !**copied) {
                let held = std::mem::take(sources);
                add_distinct(sources, held.into_iter().map(|source| ColumnSource { occurrence: None, ..source }).collect());
            }
        }
        for (sources, made) in flows.iter_mut().zip(made).filter(|(sources, _)| sources.is_empty()) {
            let lib = given.iter().flat_map(|relation| relation.lib.iter());
            sources.extend(lib.map(|name| ColumnSource::without_atom(SourceKind::LibName, Some(RelationRef::Lib(name.clone()))).with_frames(made.iter().cloned().collect())));
        }
        visiting.pop();
        flows
    }

    /// The relations that the forms of `node` give it, but for those of an
    /// output other than the `output` that a read names.
    fn given_at(&self, node: GraphNodeIndex, output: Option<&[OutputStep]>) -> Vec<Given> {
        self.program.given(node, self.registry).into_iter().filter(|relation| output.zip(relation.output.as_deref()).is_none_or(|(read, own)| read == own)).collect()
    }

    /// The place of each column of `relation` among the row positions: a
    /// labelled slot at the position of each of its labels, `label_position`
    /// of the label in the relation's form or else the label's own `place`,
    /// and a declared slot with no labels at its `width` row positions from
    /// the end of the slots before it. A label with no position is left out.
    fn placements<'g>(&self, relation: &'g Given) -> Vec<Placed<'g>> {
        let mut placed = Vec::new();
        let mut start = 0usize;
        for (slot, given) in relation.slots.iter().enumerate() {
            for label in &given.labels {
                let own = self.program.label_position(&relation.form, label.label).map(|position| usize::from(position.0));
                if let Some(position) = own.or(label.place) {
                    placed.push(Placed::Labelled { slot, position, label });
                }
            }
            if given.declared.is_some() && given.labels.is_empty() {
                placed.push(Placed::Declared { slot, positions: start..start + given.width });
            }
            start += given.width;
        }
        placed
    }

    /// The sources of `label` in the IR of a body `held`, none where the body
    /// does not compile or binds no such label.
    fn label_sources(&self, held: Option<&BodyIr>, label: LabelId, visiting: &[GraphNodeIndex]) -> Vec<ColumnSource> {
        let Some(held) = held else { return Vec::new() };
        let (clause, paths) = held.parts();
        let walk = Walk { flows: self, visiting };
        paths.labels.iter().position(|bound| *bound == label).map_or_else(Vec::new, |variable| walk.sources(Variable(variable as u16), &Alt::of(clause, paths), &mut Vec::new()))
    }

    /// The fill of each `from-key` input that the instance of `relation`
    /// leaves unwritten ([`Given::filled`]): for each, where its columns' types
    /// are all known, the key position each of its row positions takes
    /// ([`key_fill`]). `types` are the row-position types of the relation;
    /// nothing is given where they are not all known.
    fn fills(&self, relation: &Given, types: &[ValueType], width: usize) -> Vec<Fill> {
        if relation.filled.is_empty() || types.len() != width {
            return Vec::new();
        }
        // The first row position and the width of each column of the port.
        let mut at = Vec::new();
        let mut start = 0usize;
        for slot in &relation.slots {
            at.push((slot.is_key, slot.declared.as_ref(), start..start + slot.width));
            start += slot.width;
        }
        let Some((_, _, key)) = at.iter().find(|(is_key, ..)| *is_key) else { return Vec::new() };
        let mut fills = Vec::new();
        for (input, columns) in &relation.filled {
            let mut input_types = Vec::new();
            let mut targets = Vec::new();
            let mut known = true;
            for ty in columns {
                match ty {
                    ColumnType::Fixed(fixed) => input_types.push(fixed.clone()),
                    ColumnType::Parameter(_) => {
                        let Some((_, _, own)) = at.iter().find(|(is_key, declared, _)| !is_key && *declared == Some(ty)) else {
                            known = false;
                            break;
                        };
                        targets.extend(own.clone().map(|position| (position, input_types.len() + position - own.start)));
                        input_types.extend(types[own.clone()].iter().cloned());
                    }
                    _ => {
                        known = false;
                        break;
                    }
                }
            }
            if !known {
                continue;
            }
            let Some(positions) = key_fill(&types[key.clone()], &input_types) else { continue };
            fills.push(Fill { input: *input, key_start: key.start, positions, targets });
        }
        fills
    }

    /// Adds to each row position of a column of `relation`, on a type
    /// parameter that a `from-key` input the instance leaves unwritten stands
    /// on, the flows at the key position that the fill gives it
    /// ([`Flows::fills`]).
    fn add_key_fill(&self, relation: &Given, types: &[ValueType], flows: &mut [Vec<ColumnSource>]) {
        for fill in self.fills(relation, types, flows.len()) {
            for &(position, row) in &fill.targets {
                let found = flows[fill.key_start + fill.positions[row]].clone();
                add_distinct(&mut flows[position], found);
            }
        }
    }

    /// For the output of an instance that `relation` gives, replaces the
    /// sources of each column that a declared row of the registry's `copies`
    /// maps by the sources of the input's column that the row maps it from,
    /// each with the declared row's index as its occurrence, and adds those
    /// of an input's `key` to the sources of the output's `key`. `copied` marks the
    /// row positions of the columns that a declared row maps, the `key`
    /// included. The input's sources are those of its node where the instance
    /// writes the input, the lib name where the input has a default, and the
    /// flows of the key position that the fill gives it where it is
    /// `from-key`, an unwritten input giving none for its `key`.
    fn add_copied_rows(&self, relation: &Given, types: &[ValueType], flows: &mut [Vec<ColumnSource>], copied: &mut [bool], visiting: &mut Vec<GraphNodeIndex>) {
        let Some([OutputStep::Port(port)]) = relation.output.as_deref() else { return };
        let root = NodeRef::Program(self.program.program.value());
        let Some(NodeRef::Instance(instance)) = node_at(root, &relation.form) else { return };
        let Some(component) = registry_columns::component(self.registry, &instance.component) else { return };
        let Some(output) = component.outputs.iter().find(|output| output.name == *port) else { return };
        let keyed = instance.key.is_some();
        let fills = self.fills(relation, types, flows.len());
        let to_ranges = output.row_ranges(keyed, relation.slots.iter().map(|slot| slot.width));
        let mut found: Vec<Vec<ColumnSource>> = vec![Vec::new(); flows.len()];
        for (row, declared) in output.copies.iter().enumerate() {
            for from in declared.alternatives.iter() {
                let input = &component.inputs[from.input];
                let Some(slots) = self.program.instance_port_slots(&relation.form, &input.port, self.registry) else { continue };
                let from_ranges = input.port.row_ranges(keyed, slots.iter().map(|slot| slot.width));
                let node = self.program.nodes_of(&relation.form).iter().copied().find(|node| {
                    matches!(&self.program.graph.nodes[node.0 as usize].kind, DependencyKind::InstanceInput { instance: name, input: written } if *name == instance.name && *written == input.port.name)
                });
                // The first row position of each column among those other than the `key`'s.
                let mut others = Vec::new();
                let mut count = 0usize;
                for (column, range) in input.port.columns.iter().zip(&from_ranges) {
                    others.push(count);
                    count += range.as_ref().filter(|_| !is_key(column)).map_or(0, |range| range.len());
                }
                for (from_column, to_column) in from.column_pairs(&input.port, output) {
                    let (Some(from_range), Some(to_range)) = (from_ranges[from_column].clone(), to_ranges[to_column].clone()) else { continue };
                    if is_key(&input.port.columns[from_column]) {
                        // The key's labels as the input's written bodies bind them.
                        for body in self.program.input_bodies(&relation.form, &input.port.name) {
                            let bound = self.checked.body_ir(self.registry, relation, &body);
                            for slot in relation.slots.iter().filter(|slot| slot.is_key) {
                                for GivenLabel { label, place, .. } in &slot.labels {
                                    let Some(position) = self.program.label_position(&relation.form, *label).map(|position| usize::from(position.0)).or(*place) else { continue };
                                    let sources = self.label_sources(bound.as_ref(), *label, visiting);
                                    copied[position] = true;
                                    add_distinct(&mut found[position], sources.into_iter().map(|source| source.in_row(row)).collect());
                                }
                            }
                        }
                        for position in to_range {
                            copied[position] = true;
                        }
                        continue;
                    }
                    for (offset, position) in to_range.enumerate() {
                        copied[position] = true;
                        let sources = match node {
                            Some(node) => self.port_sources(node, (from_range.start + offset) as u16, visiting),
                            None if input.default.is_some() => relation.lib.iter().map(|name| ColumnSource::without_atom(SourceKind::LibName, Some(RelationRef::Lib(name.clone())))).collect(),
                            None => fills
                                .iter()
                                .find(|fill| fill.input == from.input)
                                .and_then(|fill| flows.get(fill.key_start + *fill.positions.get(others[from_column] + offset)?))
                                .cloned()
                                .unwrap_or_default(),
                        };
                        add_distinct(&mut found[position], sources.into_iter().map(|source| source.in_row(row)).collect());
                    }
                }
            }
        }
        let mut start = 0usize;
        for slot in &relation.slots {
            for position in start..start + slot.width {
                if copied[position] {
                    let sources = std::mem::take(&mut found[position]);
                    if slot.is_key {
                        add_distinct(&mut flows[position], sources);
                    } else {
                        flows[position] = sources;
                    }
                }
            }
            start += slot.width;
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
    /// columns, computed, in place of the port. Each gives the frames that
    /// `frame`, the frame rule of the declared column of an instance's
    /// output, gives it ([`ColumnSource::framed`]), and none where there is
    /// no rule.
    fn declared_sources(&self, node: GraphNodeIndex, frame: Option<&OutputFrame>, visiting: &mut Vec<GraphNodeIndex>) -> Vec<ColumnSource> {
        let rule_at = frame.map(OutputFrame::rule_at);
        let mut found = Vec::new();
        for &read in self.program.graph.reads[node.0 as usize].iter().filter(|&&read| read != node) {
            let graph_node = &self.program.graph.nodes[read.0 as usize];
            let Some(relation) = node_relation(&graph_node.kind) else { continue };
            let Some((_, width)) = self.program.node_width(read) else { continue };
            for position in 0..width {
                if let DependencyKind::InstanceInput { input, .. } = &graph_node.kind {
                    let named = frame.is_some_and(|frame| frame.names(input, position));
                    found.extend(self.port_sources(read, position as u16, visiting).into_iter().map(|source| source.computed().framed(rule_at.as_ref(), named)));
                    continue;
                }
                let (relation, position) = match relation {
                    RelationRef::Fact(FactRelation::Input) => (RelationRef::Fact(FactRelation::ExInput), position + 1),
                    ref other => (other.clone(), position),
                };
                let source = ColumnSource { kind: SourceKind::Computed, relation: Some(relation), column: SourceColumn::Position(position as u16), row: None, atom: NodePath::default(), occurrence: None, frames: Vec::new() };
                found.push(source.framed(rule_at.as_ref(), false));
            }
        }
        found
    }

    /// The frame rule of the column at `slot` of the output that `relation`
    /// gives, where `relation` is an output of an instance of a component of the
    /// registry, and the column has a frame.
    fn output_frame(&self, relation: &Given, slot: usize) -> Option<OutputFrame> {
        let [OutputStep::Port(port)] = relation.output.as_deref()? else { return None };
        let NodeRef::Instance(instance) = node_at(NodeRef::Program(self.program.program.value()), &relation.form)? else { return None };
        let component = registry_columns::component(self.registry, &instance.component)?;
        let output = component.outputs.iter().find(|output| output.name == *port)?;
        let keyed = instance.key.is_some();
        let column = output.columns_at(keyed).nth(slot)?;
        let rule = self.registry.output_frame(&instance.component, port, &column.name)?;
        let named = rule
            .of
            .iter()
            .filter_map(|named| {
                let input = component.inputs.iter().find(|input| Some(&input.port.name) == named.input.as_ref())?;
                let slots = self.program.instance_port_slots(&relation.form, &input.port, self.registry)?;
                let ranges = input.port.row_ranges(keyed, slots.iter().map(|slot| slot.width));
                let at = input.port.columns.iter().position(|column| column.name == named.column)?;
                Some((input.port.name.clone(), ranges[at].clone()?))
            })
            .collect();
        let maker = Maker::Output { component: instance.component.clone(), output: port.clone(), column: column.name.clone() };
        Some(OutputFrame { rule, maker, at: relation.form.clone(), named })
    }

    /// The input columns that a declared row of the registry's `copies` maps
    /// the column at `slot` of the output that `relation` gives from, as the
    /// row positions of each in the rows of its input.
    fn copied_from(&self, relation: &Given, slot: usize) -> Vec<(PortName, Range<usize>)> {
        let Some([OutputStep::Port(port)]) = relation.output.as_deref() else { return Vec::new() };
        let Some(NodeRef::Instance(instance)) = node_at(NodeRef::Program(self.program.program.value()), &relation.form) else { return Vec::new() };
        let Some(component) = registry_columns::component(self.registry, &instance.component) else { return Vec::new() };
        let Some(output) = component.outputs.iter().find(|output| output.name == *port) else { return Vec::new() };
        let keyed = instance.key.is_some();
        let Some(column) = output.columns_at(keyed).nth(slot) else { return Vec::new() };
        let mut copied = Vec::new();
        for from in output.copies.iter().flat_map(|row| row.alternatives.iter()) {
            let input = &component.inputs[from.input];
            let Some(slots) = self.program.instance_port_slots(&relation.form, &input.port, self.registry) else { continue };
            let ranges = input.port.row_ranges(keyed, slots.iter().map(|slot| slot.width));
            for &(from_column, _) in from.columns.iter().filter(|&&(_, to)| output.columns[to].name == column.name) {
                if let Some(range) = ranges[from_column].clone() {
                    copied.push((input.port.name.clone(), range));
                }
            }
        }
        copied
    }
}

/// The frame rule of a column of an instance's output, with the frame it
/// makes: the lib column that makes it, the path of the `INIT` form, and the
/// row positions of the input columns that the rule names.
#[derive(Clone)]
pub struct OutputFrame {
    pub rule: FrameRule,
    maker: Maker,
    at: NodePath,
    /// The row positions of each input column that the rule names, in the
    /// rows of that input.
    pub named: Vec<(PortName, Range<usize>)>,
}

impl OutputFrame {
    fn rule_at(&self) -> RuleAt<'_> {
        RuleAt { rule: &self.rule, maker: &self.maker, at: &self.at }
    }

    /// Whether the rule names the column of the input port `input` that stands
    /// at row position `position`.
    fn names(&self, input: &PortName, position: usize) -> bool {
        self.named.iter().any(|(name, range)| name == input && range.contains(&position))
    }
}

/// Adds to `held` each of `sources` it does not hold, in order. A source that
/// `held` holds but for its frames adds the frames it lacks to the held one.
fn add_distinct(held: &mut Vec<ColumnSource>, sources: Vec<ColumnSource>) {
    for source in sources {
        match held.iter_mut().find(|own| own.same_source(&source)) {
            Some(own) => {
                for frame in source.frames {
                    if !own.frames.contains(&frame) {
                        own.frames.push(frame);
                    }
                }
            }
            None => held.push(source),
        }
    }
}

/// The fill of one `from-key` input an instance leaves unwritten: the index of
/// the input among the component's, the first row position of the `key` in
/// the output, the key position of each row position of the input other than
/// the key's, and, for each row position of the output on a type parameter of
/// the input, the pair of that position and the input's row position it takes.
struct Fill {
    input: usize,
    key_start: usize,
    positions: Vec<usize>,
    targets: Vec<(usize, usize)>,
}
