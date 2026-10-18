//! The lib registry: the names of the lib, and what each declares. It is
//! embedded from the registry file and the proposers file, as
//! [`REGISTRY_TEXT`] and [`PROPOSERS_TEXT`], when the engine is compiled, so
//! the wheel reads no file for it. A new lib element adds a
//! registry entry and changes no checker code.
//!
//! # The file
//!
//! The file is `engine/lib/registry.sexpr`. It is s-expressions, read by the
//! reader of [`crate::read::read_sexprs`], so the engine has one reader for
//! every s-expression file. `include_str!` puts its text into the compiled
//! crate, and [`Registry::get`] reads that text once, on first use. The test
//! `registry_file` under `engine/arclog/tests/` parses both lib files, so a
//! fault of either fails `cargo test`.
//!
//! Each top-level form declares one lib element, by its head:
//!
//! - `(relation <name> (columns (<Column> <type>) ...) (modes (<Column> ...) ...))`:
//!   an algebra relation, the group relations and `pose_difference`
//!   included. Each mode lists the columns, other than an orientation
//!   type's, that must be grounded for the relation to ground the others; a
//!   relation over a finite domain has no `modes` form, and no mode is empty.
//! - `(component <name> <construction|detector|task-structure> (type-parameters <t> ...)
//!   (inputs (<input> (<column> <type>) ... [(default <rows>)] [reads-outputs]) ...)
//!   (outputs (<output> (<column> <type>) ...) ...))`: a construction, a
//!   detector or a task-structure component, its inputs in the order the component declares them. An
//!   input's `default` writes its rows as a `param` form writes them after
//!   its types (`docs/arclog/arcdata.md#params`): each row as a list of its
//!   values, and the rows of a relation with a Position or an Offset column
//!   as a grid. An
//!   input marked `reads-outputs` reads the instance's outputs, as
//!   `Unfold`'s `step`, `skip` and `take` do. An output may share its name
//!   with an input of the same form: an instance's output of that name reads
//!   the input's relation, as `Unfold`'s `take`, where the instance writes no
//!   clause for it, holds the item of least `score`.
//! - `(proposer <name> native (columns (<Column> <type>) ...))`: a native
//!   proposer, such as a domain proposer.
//! - `(proposer <name> arclog)`: a proposer written in arclog, whose clause
//!   stands in `engine/lib/proposers.arclog`. Its columns are its clause's
//!   labels, in the order they first stand in the clause.
//! - `(derivation <Name> (fields (<Field> <type>) ...) (columns (<Column> <type>) ...))`:
//!   a fixed derivation of a table, its row's fields and the table's columns.
//!   A derivation may share its name with a component, as `Frame` and
//!   `Division` do.
//! - `(constants <type> <NAME> ...)`: the constants of an orientation type,
//!   and `(constants C4 <NAME> ...)`: the D4 constants that are C4, the
//!   rotations.
//! - `(fact <name> (columns (<Column> <type>) ...))`: the columns of a fact
//!   relation, `input`, `ex_input` or `ex_output`, the Example column `E`
//!   first in the two of the examples.
//! - `(macro <name> (columns (<Column> <Label>) ...) (modes ...) <body>)`:
//!   a lib relation that the lib defines from other lib names, each column
//!   with the label of the definition it stands for, its modes as a
//!   `relation` form gives them, and its definition. A
//!   [`Macro::Relation`]'s column types are the ones
//!   [`macro_column_types`] gives.
//! - `(macro <name> (component ...) [(INIT ...)] (output <port> (<Label> ...) <body>) ...)`:
//!   a cell instance, its declaration as a `component` form gives it, the
//!   `INIT` form of the underlying construction where it has one, and a body
//!   for each of its outputs, as [`Macro::CellInstance`] gives. Within these
//!   bodies an atom `(self.<port> <sites>)` reads the cell instance's own
//!   input `<port>`, as [`crate::program::RelationRef::DefinedPort`] holds it.
//!
//! A macro's definition reads only lib names that a form of the file
//! declares, and a definition that reads another name is a fault of the
//! file.
//!
//! A `<type>` is a type name of [`crate::program::TypeName`], `Pose` for
//! the assembly the read names, `shared-pose` for one assembly's Pose type
//! at each such column of the relation, `(pose-or <type>)` for the type or
//! the Pose type of the label at the site, or a type parameter of its
//! component. The file declares no `representative`. The file and
//! `engine/lib/proposers.arclog` are named in diagnostics as
//! [`crate::layout::SourceFile::LibRegistry`] and
//! [`crate::layout::SourceFile::LibProposers`].
//!
//! `engine/lib/proposers.arclog` holds one form `(proposer <Name> <atom> ...)`
//! per proposer of the form `(proposer <name> arclog)`, its name in the
//! spelling of a proposer, as `(proposer DominantColor ...)`, then the atoms
//! of its clause's body, which [`crate::read::read_body`] reads.
//!
//! The registry and resolver stage writes the bodies and the file's entries.

#![allow(unused_variables, dead_code)]

use crate::check::CheckId;
use crate::hash::StableHashMap;
use crate::layout::SourcePlace;
use crate::program::{Atom, Body, ColumnName, Conjunct, Constraint, Operand, LabelId, LabelUse, Negated, Node, PortName, RelationRef, Site, SiteArg};
use crate::terms::{OrientationConstant, OrientationType};
use crate::types::{Meet, ValueType};

/// The text of the registry file, which [`Registry::get`] reads.
pub const REGISTRY_TEXT: &str = include_str!("../../lib/registry.sexpr");

/// The text of the proposers file, read by
/// [`crate::read::read_sexprs`] with
/// [`crate::layout::SourceFile::LibProposers`] and [`crate::read::read_body`].
pub const PROPOSERS_TEXT: &str = include_str!("../../lib/proposers.arclog");

/// A name of the lib: a relation, a component, a proposer, a derivation or
/// a macro, as the file writes it: `margin`, `Connectivity`,
/// `DominantColor`, `Frame`. An orientation constant is named by
/// [`Registry::orientation_constant`] instead.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct LibName(pub Box<str>);

/// The name of a component's type parameter, such as `t` or `key`.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct TypeParameter(pub Box<str>);

/// The type a lib column declares. A `:Pose` column has the type Pose of its
/// assembly.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ColumnType {
    Fixed(ValueType),
    /// The Pose type of the assembly the read names.
    Pose,
    /// The Pose type of one assembly, the same at each column of the
    /// relation that declares it, as `pose_difference(a, b, d)` reads two
    /// poses of one assembly.
    SharedPose,
    /// The given type, or the Pose type of the label at the column's site,
    /// as `d4_elem`'s column is D4 or takes its label's Pose type, since
    /// every D4 element is a pose (`docs/arclog/rigid.md#the-pose`).
    PoseOr(ValueType),
    /// A type parameter of the component, made concrete by an instance's
    /// binding.
    Parameter(TypeParameter),
}

/// A declared column: its name and type.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Column {
    pub name: ColumnName,
    pub ty: ColumnType,
}

/// A mode of an algebra relation: the columns whose labels must be grounded
/// for its other columns to be grounded.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct Mode {
    pub grounded: Box<[ColumnName]>,
}

/// An algebra relation, a relation of the box algebra or the orientation
/// algebra, with its columns, their types and its modes.
#[derive(Clone, Debug)]
pub struct AlgebraRelation {
    pub columns: Box<[Column]>,
    /// Empty for a relation over a finite domain.
    pub modes: Box<[Mode]>,
}

/// The kind of a component: a construction, a detector or a task-structure
/// component. A task-structure component, `Choose` or
/// `DemonstrationConsistency`, is the component of a `CHOOSE` or a
/// `DEMONSTRATED` form, whose ports the registry declares as it declares a
/// construction's.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum ComponentKind {
    Construction,
    Detector,
    TaskStructure,
}

/// One input or output of a component.
#[derive(Clone, Debug)]
pub struct Port {
    pub name: PortName,
    pub columns: Box<[Column]>,
}

/// An input of a component, with its default rows, which hold where the
/// instance writes no clause for the input.
#[derive(Clone, Debug)]
pub struct InputPort {
    pub port: Port,
    pub default: Option<DefaultRows>,
    /// Whether the input reads the instance's outputs, as `Unfold`'s `step`,
    /// `skip` and `take` do, through atoms whose every variable another atom
    /// of the clause grounds.
    pub reads_outputs: bool,
}

/// The default rows of an input, as the file writes them, read by
/// [`crate::read::read_param_value`]. It gives its rows as a set, and no
/// position of a row, so no caller can pick one default by its place in the
/// file, and no lib interface makes a free choice.
#[derive(Clone, Debug)]
pub struct DefaultRows {
    written: crate::program::ParamValue,
}

impl DefaultRows {
    /// The default rows, typed by `types`, the types of the input's columns
    /// in order: [`crate::terms::encode_param_value`] of the default's
    /// value, with `table` interning an Ident's values.
    pub fn rows(
        &self,
        types: &[ValueType],
        registry: &Registry,
        table: &mut crate::terms::InternTable,
    ) -> Result<crate::hash::StableHashSet<Box<[crate::terms::TermId]>>, crate::terms::DataValueError> {
        crate::terms::encode_param_value(&self.written, types, registry, table)
    }
}

/// A construction or a detector: its type parameters, its inputs in the
/// order the component declares them, with their defaults, and its outputs.
#[derive(Clone, Debug)]
pub struct Component {
    pub kind: ComponentKind,
    pub type_parameters: Box<[TypeParameter]>,
    /// The inputs in the order the component declares them.
    pub inputs: Box<[InputPort]>,
    pub outputs: Box<[Port]>,
}

/// A proposer: a native one, or one written in arclog.
#[derive(Clone, Debug)]
pub enum Proposer {
    /// A native proposer and its columns.
    Native { columns: Box<[Column]> },
    /// A proposer written in arclog: the body of its clause, and its
    /// columns, the names of the clause's labels in the order they first
    /// stand in it.
    Arclog { columns: Box<[ColumnName]>, body: Node<Body> },
}

/// What a lib name declares.
#[derive(Clone, Debug)]
pub enum LibEntry {
    Relation(AlgebraRelation),
    Component(Component),
    Proposer(Proposer),
    Macro(Macro),
}

/// A fixed derivation of a table, such as `Frame` or `Division`: the fields
/// of each row of the values a `param` form writes for it, and the columns
/// of the table it derives. A `DET` names the derivation in place of a
/// proposer, `(DET &frame Frame)` (`docs/arclog/arclog.md#program`), and
/// the parameter's value is written as the values the table derives from
/// (`docs/arclog/arcdata.md#params`).
#[derive(Clone, Debug)]
pub struct Derivation {
    pub fields: Box<[Column]>,
    pub columns: Box<[Column]>,
}

/// A lib name that the lib defines from other lib names, a relation or a
/// cell instance, with its declaration and its definition, which the
/// resolver expands under [`crate::resolver::MacroExpansion::Expand`]. The
/// declaration serves the checks under
/// [`crate::resolver::MacroExpansion::Keep`], the form the corpus is written
/// in. A program runs in either form. A relation macro's column types are
/// its definition's, as [`macro_column_types`] gives them, and its modes
/// are the ones its form writes.
#[derive(Clone, Debug)]
pub enum Macro {
    /// A lib relation: its declaration, its columns, their types and its
    /// modes, the label of the definition that each of its columns stands
    /// for, in the order of the declaration's columns, and its definition.
    Relation {
        relation: AlgebraRelation,
        labels: Box<[crate::program::LabelId]>,
        definition: Node<Body>,
    },
    /// A cell instance: its declaration as a component, its type
    /// parameters, inputs in order with their defaults, and outputs; its
    /// definition over the underlying construction or relation; and a body
    /// for each of its outputs.
    CellInstance {
        component: Component,
        definition: CellDefinition,
        outputs: Box<[CellOutput]>,
    },
}

/// What a cell instance is defined over: Quotient over Connectivity,
/// Propagation over Flood, Walk over Ray, Distance over CellDistance, and
/// `divide` over Division.
#[derive(Clone, Debug)]
pub enum CellDefinition {
    /// An `INIT` form of the underlying construction with its domain inputs
    /// populated, whose other input bodies read the cell instance's inputs
    /// by their port names, as Connectivity over Quotient.
    Instance(Node<crate::program::Instance>),
    /// No instance: the outputs' bodies read the underlying relation over
    /// the cell instance's inputs, as Division over `divide`.
    Relation,
}

/// An output of a cell instance, as a body over the outputs of its
/// definition's instance, where it has one, and its own inputs: the output's
/// port, the label of the body that each of its columns stands for, in the
/// order of the port's columns, and the body.
#[derive(Clone, Debug)]
pub struct CellOutput {
    pub port: PortName,
    pub labels: Box<[crate::program::LabelId]>,
    pub body: Node<Body>,
}

/// The constants of one orientation type, as a set: it gives membership
/// and each constant, and no position of a constant, so no caller can pick
/// one constant by its place in the file, and no lib interface makes a free
/// choice.
#[derive(Clone, Debug, Default)]
pub struct ConstantSet {
    constants: crate::hash::StableHashSet<OrientationConstant>,
}

impl ConstantSet {
    /// Whether `constant` is in the set.
    pub fn contains(&self, constant: OrientationConstant) -> bool {
        todo!()
    }

    /// Each constant of the set, in an order of encodings and no order of
    /// the content.
    #[allow(unreachable_code)]
    pub fn each(&self) -> impl Iterator<Item = OrientationConstant> + '_ {
        todo!();
        std::iter::empty()
    }
}

/// A fault of the registry file, reported when it is first read.
#[derive(Clone, Debug)]
pub struct RegistryError {
    pub diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

/// The lib registry: the names of the lib, and what each declares.
#[derive(Debug)]
pub struct Registry {
    entries: StableHashMap<LibName, LibEntry>,
    /// The derivations, apart from the entries, since a name such as
    /// `Frame` or `Division` is both a component and a derivation.
    derivations: StableHashMap<LibName, Derivation>,
    constants: StableHashMap<Box<str>, OrientationConstant>,
    c4: ConstantSet,
    facts: StableHashMap<crate::program::FactRelation, Box<[Column]>>,
}

impl Registry {
    /// The registry of [`REGISTRY_TEXT`], read on first use.
    ///
    /// A fault of the file fails the test `registry_file`, so this panics on
    /// one.
    pub fn get() -> &'static Registry {
        todo!()
    }

    /// The registry that `text` declares, with the proposers that
    /// `proposers` writes in arclog, which are read with the entries of
    /// `text`. [`Registry::get`] gives it [`REGISTRY_TEXT`] and
    /// [`PROPOSERS_TEXT`].
    pub fn parse(text: &str, proposers: &str) -> Result<Registry, RegistryError> {
        todo!()
    }

    /// What `name` declares, or `None` where the lib has no such name.
    pub fn entry(&self, name: &LibName) -> Option<&LibEntry> {
        todo!()
    }

    /// The derivation that `name` declares, which a `DET` names in place of
    /// a proposer, or `None` where the lib declares no derivation of that
    /// name.
    pub fn derivation(&self, name: &LibName) -> Option<&Derivation> {
        todo!()
    }

    /// The orientation constant written `name`, such as `DIR_T`.
    pub fn orientation_constant(&self, name: &str) -> Option<OrientationConstant> {
        todo!()
    }

    /// The name of `constant`, for a writer.
    pub fn constant_name(&self, constant: OrientationConstant) -> &str {
        todo!()
    }

    /// The constants of `ty`, for a domain proposer and for `<ty>_elem`.
    pub fn constants_of(&self, ty: OrientationType) -> &ConstantSet {
        todo!()
    }

    /// The D4 constants that are C4, the rotations, as `C4` stands under
    /// `D4`, for `c4_elem`.
    pub fn c4_constants(&self) -> &ConstantSet {
        todo!()
    }

    /// The columns of `fact`, with their types, which the resolver turns a
    /// read's column names into positions by and the checker types by.
    /// `ex_input` and `ex_output` have the Example column `E` first
    /// (`docs/arclog/arclog.md#program`).
    pub fn fact_columns(&self, fact: crate::program::FactRelation) -> &[Column] {
        todo!()
    }
}

/// A relation macro of the file, as [`macro_column_types`] reads it.
#[derive(Clone, Copy, Debug)]
pub struct RelationMacro<'a> {
    pub name: &'a LibName,
    /// The place of the macro's form, where a diagnostic on it stands.
    pub place: SourcePlace,
    /// Each column's name and the label of the definition it stands for, in
    /// the order of the macro's columns.
    pub columns: &'a [(ColumnName, LabelId)],
    /// The definition, as [`crate::read::read_body`] gives it.
    pub definition: &'a Body,
}

/// The column types of each relation macro of `macros`, in the order of its
/// columns, or a diagnostic at a macro's form for each fault.
///
/// The type of a column is the meet, as [`ValueType::meet`] gives it, of
/// the types of every site where its label stands in the definition, at any
/// depth, and a join, as [`ValueType::join`] gives it, comes only between
/// alternatives. A negated atom's sites count as a positive atom's, and a
/// `NOT` of a form gives what that form gives. An `OR` gives the join of the
/// types its branches give, an `IF` the meet of its test's type with the
/// join of its then and else lists' types, and an `ALL` the meet of its
/// domain's and its body's types. A branch that gives the label no type
/// gives the `OR` or the `IF`'s join none. A constraint over two labels,
/// at any depth, gives each the sites of the other, and `0` gives no type.
/// A site is one label at an atom's column, and has the column's type: a
/// column of a lib name that `lib` declares, where the type is fixed or
/// `(pose-or <type>)`, or a column of another macro of `macros`, of the type
/// this gives it. Any other site gives no type.
///
/// `lib` holds the columns of each lib name that a form other than a
/// relation macro declares. The macros are read in an order of their reads
/// of one another, so the order of `macros` gives the order of the
/// diagnostics alone. A fault is a cycle of macros that read one another,
/// given at each macro of the cycle; a column whose label's sites have an
/// empty meet, or whose branches give types with no join; or a column whose
/// label stands at no site that gives a type. A macro that reads a macro
/// with a fault takes no types, and gives no diagnostic of its own for it.
pub fn macro_column_types(
    macros: &[RelationMacro<'_>],
    lib: &StableHashMap<LibName, Box<[Column]>>,
) -> Result<StableHashMap<LibName, Box<[ValueType]>>, Vec<crate::diagnostic::Diagnostic>> {
    let mut derivation = MacroDerivation {
        macros,
        lib,
        index: macros.iter().enumerate().map(|(i, m)| (m.name.clone(), i)).collect(),
        states: vec![MacroState::Unread; macros.len()],
        stack: Vec::new(),
        diagnostics: Vec::new(),
    };
    for i in 0..macros.len() {
        derivation.read(i);
    }
    if !derivation.diagnostics.is_empty() {
        return Err(derivation.diagnostics);
    }
    let types = derivation.states.into_iter().zip(macros).map(|(state, m)| match state {
        MacroState::Typed(types) => (m.name.clone(), types),
        _ => unreachable!("a macro with no types gives a diagnostic"),
    });
    Ok(types.collect())
}

/// Where [`macro_column_types`] stands in its read of one macro.
#[derive(Clone, Debug)]
enum MacroState {
    Unread,
    /// Its reads of other macros are being read, so a read of it now closes
    /// a cycle.
    Reading,
    Typed(Box<[ValueType]>),
    /// It has a fault, or reads a macro with one.
    Faulted,
}

/// A fault of the type of one label in a definition.
enum LabelFault {
    /// Two sites give the label types with an empty meet.
    EmptyMeet(ValueType, ValueType),
    /// Two branches give the label types with no join.
    NoJoin(ValueType, ValueType),
}

struct MacroDerivation<'a, 'b> {
    macros: &'a [RelationMacro<'b>],
    lib: &'a StableHashMap<LibName, Box<[Column]>>,
    index: StableHashMap<LibName, usize>,
    states: Vec<MacroState>,
    /// The macros being read, each reading the next.
    stack: Vec<usize>,
    diagnostics: Vec<crate::diagnostic::Diagnostic>,
}

impl MacroDerivation<'_, '_> {
    /// Reads macro `i` after each macro it reads, and sets its state.
    fn read(&mut self, i: usize) {
        match self.states[i] {
            MacroState::Unread => {}
            MacroState::Reading => {
                self.close_cycle(i);
                return;
            }
            MacroState::Typed(_) | MacroState::Faulted => return,
        }
        self.states[i] = MacroState::Reading;
        self.stack.push(i);
        let mut reads = Vec::new();
        each_conjunct(self.macros[i].definition, &mut |conjunct| {
            if let Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) = conjunct {
                if let RelationRef::Lib(name) = &atom.value().relation {
                    if let Some(&j) = self.index.get(name) {
                        reads.push(j);
                    }
                }
            }
        });
        for &j in &reads {
            self.read(j);
        }
        self.stack.pop();
        let read_faulted = reads.iter().any(|&j| !matches!(self.states[j], MacroState::Typed(_)));
        if matches!(self.states[i], MacroState::Faulted) || read_faulted {
            self.states[i] = MacroState::Faulted;
            return;
        }
        self.states[i] = match self.column_types(&self.macros[i]) {
            Some(types) => MacroState::Typed(types),
            None => MacroState::Faulted,
        };
    }

    /// Gives a diagnostic at each macro of the cycle that a read of macro
    /// `i`, which is being read, closes, and marks each with a fault.
    fn close_cycle(&mut self, i: usize) {
        let start = self.stack.iter().position(|&j| j == i).expect("a macro being read stands on the stack");
        let cycle: Vec<usize> = self.stack[start..].to_vec();
        let names: Vec<String> = cycle.iter().map(|&j| format!("`{}`", self.macros[j].name.0)).collect();
        for &j in &cycle {
            if matches!(self.states[j], MacroState::Faulted) {
                continue;
            }
            self.states[j] = MacroState::Faulted;
            let message = format!("the macro `{}` reads itself through the macros {}", self.macros[j].name.0, names.join(", "));
            self.diagnostics.push(crate::read::check_error(CheckId::Cycles, message, self.macros[j].place));
        }
    }

    /// The type of each column of `m`, or `None` with a diagnostic for each
    /// column that has a fault.
    fn column_types(&mut self, m: &RelationMacro<'_>) -> Option<Box<[ValueType]>> {
        let mut types = Vec::new();
        let mut faulted = false;
        for (column, label) in m.columns {
            let message = match self.label_type(m.definition, &equal_labels(m.definition, *label)) {
                Ok(Some(ty)) => {
                    types.push(ty);
                    continue;
                }
                Ok(None) => "stands at no site that gives a type".to_string(),
                Err(LabelFault::EmptyMeet(a, b)) => format!("stands at sites of the types {a:?} and {b:?}, whose meet is empty"),
                Err(LabelFault::NoJoin(a, b)) => format!("takes the types {a:?} and {b:?} from two branches, which have no join"),
            };
            faulted = true;
            let message = format!("the label of the column `{}` of the macro `{}` {message}", column_display(column), m.name.0);
            self.diagnostics.push(crate::read::check_error(CheckId::Types, message, m.place));
        }
        if faulted { None } else { Some(types.into()) }
    }

    /// The type that `body` gives the labels of `class`, the labels that
    /// the definition's constraints make equal, `None` where it gives none.
    fn label_type(&self, body: &Body, class: &[LabelId]) -> Result<Option<ValueType>, LabelFault> {
        let mut ty = None;
        for conjunct in body.conjuncts.iter() {
            ty = meet(ty, self.conjunct_type(conjunct, class)?)?;
        }
        Ok(ty)
    }

    /// The type that `conjunct` gives the labels of `class`, `None` where it
    /// gives none.
    fn conjunct_type(&self, conjunct: &Conjunct, class: &[LabelId]) -> Result<Option<ValueType>, LabelFault> {
        match conjunct {
            Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
                let atom = atom.value();
                let mut ty = None;
                for site in atom.sites.iter().filter(|site| site_label(site).is_some_and(|l| class.contains(&l))) {
                    ty = meet(ty, self.site_type(atom, &site.column))?;
                }
                Ok(ty)
            }
            Conjunct::Not(Negated::Form(form)) => self.conjunct_type(form, class),
            Conjunct::Or(branches) => join_branches(branches.iter().map(|branch| self.label_type(branch.value(), class))),
            Conjunct::If { test, then, otherwise } => {
                let branches = [then, otherwise].into_iter().map(|branch| self.label_type(branch.value(), class));
                meet(self.label_type(test.value(), class)?, join_branches(branches)?)
            }
            Conjunct::All { domain, body } => {
                meet(self.label_type(domain.value(), class)?, self.label_type(body.value(), class)?)
            }
            Conjunct::Constraint(_) => Ok(None),
        }
    }

    /// The type of the column `column` of the relation `atom` reads, where
    /// that relation is a lib name of `lib` or a macro with types.
    fn site_type(&self, atom: &Atom, column: &ColumnName) -> Option<ValueType> {
        let RelationRef::Lib(name) = &atom.relation else { return None };
        if let Some(&j) = self.index.get(name) {
            let MacroState::Typed(types) = &self.states[j] else {
                unreachable!("a macro takes types only after each macro it reads has types")
            };
            let position = self.macros[j].columns.iter().position(|(c, _)| c == column)?;
            return Some(types[position].clone());
        }
        match &self.lib.get(name)?.iter().find(|c| &c.name == column)?.ty {
            ColumnType::Fixed(ty) | ColumnType::PoseOr(ty) => Some(ty.clone()),
            ColumnType::Pose | ColumnType::SharedPose | ColumnType::Parameter(_) => None,
        }
    }
}

/// The one label that `site` holds, where it holds one label and no field.
fn site_label(site: &Site) -> Option<LabelId> {
    match &site.value.args[..] {
        [SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label))] => Some(*label),
        _ => None,
    }
}

/// The meet of two types of one label, either of which may be absent.
fn meet(a: Option<ValueType>, b: Option<ValueType>) -> Result<Option<ValueType>, LabelFault> {
    match (a, b) {
        (Some(a), Some(b)) => match a.meet(&b) {
            Meet::Type(ty) => Ok(Some(ty)),
            Meet::Empty => Err(LabelFault::EmptyMeet(a, b)),
        },
        (a, b) => Ok(a.or(b)),
    }
}

/// The join of the types that branches give one label, or `None` where a
/// branch gives it none.
fn join_branches(
    branches: impl Iterator<Item = Result<Option<ValueType>, LabelFault>>,
) -> Result<Option<ValueType>, LabelFault> {
    let mut joined: Option<ValueType> = None;
    for branch in branches {
        let Some(ty) = branch? else { return Ok(None) };
        joined = Some(match joined {
            None => ty,
            Some(prev) => prev.join(&ty).ok_or_else(|| LabelFault::NoJoin(prev.clone(), ty.clone()))?,
        });
    }
    Ok(joined)
}

/// The name of `column`, for a diagnostic.
fn column_display(column: &ColumnName) -> String {
    match column {
        ColumnName::Written(name) => name.to_string(),
        ColumnName::Slot(slot) => format!("slot {slot}"),
    }
}

/// `label` and each label that a constraint of `body`, at any depth, makes
/// equal to it, directly or through other labels.
fn equal_labels(body: &Body, label: LabelId) -> Vec<LabelId> {
    let mut pairs = Vec::new();
    each_conjunct(body, &mut |conjunct| {
        if let Conjunct::Constraint(Constraint { first, second: Operand::Label(second), .. }) = conjunct {
            pairs.push((first.label, second.label));
        }
    });
    let mut class = vec![label];
    let mut grown = true;
    while grown {
        grown = false;
        for &(a, b) in &pairs {
            for (x, y) in [(a, b), (b, a)] {
                if class.contains(&x) && !class.contains(&y) {
                    class.push(y);
                    grown = true;
                }
            }
        }
    }
    class
}

/// Visits each conjunct of `body` at any depth, a conjunct inside a `NOT`
/// included.
fn each_conjunct(body: &Body, visit: &mut dyn FnMut(&Conjunct)) {
    fn conjunct(c: &Conjunct, visit: &mut dyn FnMut(&Conjunct)) {
        visit(c);
        match c {
            Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_) => {}
            Conjunct::Not(Negated::Form(form)) => conjunct(form, visit),
            Conjunct::Or(branches) => branches.iter().for_each(|b| each_conjunct(b.value(), visit)),
            Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().for_each(|b| each_conjunct(b.value(), visit)),
            Conjunct::All { domain, body } => [domain, body].into_iter().for_each(|b| each_conjunct(b.value(), visit)),
        }
    }
    for c in body.conjuncts.iter() {
        conjunct(c, visit);
    }
}
