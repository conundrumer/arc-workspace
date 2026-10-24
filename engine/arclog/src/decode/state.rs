//! The state of a decode and its step by one token, by the grammar of the
//! stream that `crate::stream::write` writes: the finished forms, the form in
//! progress as a stack of open nodes, the relations declared by slot, and the
//! count of the labels of the form in progress.
//!
//! A decoded program names by slot each name that the stream holds as an id,
//! as `docs/arclog/arclog.md#names` gives: a relation it declares, by its
//! slot; an instance, a `CHOOSE` form and a `RIGID_DET` form, by the slot of
//! the first relation it declares; a column of a relation it declares, by the
//! column's position among the relation's columns; a field of a record, by
//! its position in the record; and the name of a bare label at a column of a
//! type parameter, by the label's id.

use std::sync::Arc;

use super::Context;
use crate::check::CheckedProgram;
use crate::eval::Outcome;
use crate::program::path::{NodePath, PathStep};
use crate::program::{
    written_inputs, Atom, Body, Choose, Clause, ClauseKeyword, ColumnName, Conjunct, Constraint, ConstraintLabel, ConstraintOp, DeclaredName, Form, Instance,
    InstanceInput, InstanceName, KeyBody, KeyClause, LabelId, LabelUse, Negated, Node, OneMark, Operand, OutputName, OutputOwner, OutputStep, PortName,
    Program, ProgramRelation, RelationColumn, RelationName, RelationRef, RigidDet, RigidDetName, Site, SiteArg, SiteValue,
};
use crate::read::columns::{key_labels, made_labels};
use crate::read::is_type_parameter_column;
use crate::registry::{Component, LibEntry, LibName};
use crate::registry::Registry;
use crate::resolver::columns::example;
use crate::resolver::{resolve, resolve_last, ResolvedProgram, SolverScope};
use crate::safety::body_labels;
use crate::resolver::form_columns::rigid_outputs;
use crate::resolver::registry_columns::{component, proposer_columns, typed_columns};
use crate::stream::write::reads_example_column;
use crate::stream::{Control, Token};

/// Why the grammar refuses a token at a state.
pub(super) type Unexpected = &'static str;

/// A relation the program has declared: what a read of it names, the
/// names of its columns in order, and whether a read of it resolves: an
/// instance's relation of an input resolves where the instance writes the
/// input, as `crate::registry::Component::relation_ports` gives.
#[derive(Debug)]
struct Declared {
    relation: ProgramRelation,
    columns: Arc<[ColumnName]>,
    readable: bool,
}

/// The state of a decode. A clone copies the stack's frames, each of which
/// holds its children as shared nodes, and shares the finished forms and the
/// declarations.
#[derive(Clone, Debug)]
pub(super) struct State {
    program: Node<Program>,
    /// The relations declared, by slot.
    declared: Arc<[Arc<Declared>]>,
    /// The count of the relations declared at the last finished form, which
    /// are those of the finished forms.
    finished_slots: u32,
    /// The count of the labels of the form in progress, the next label's id.
    labels: u32,
    stack: Vec<Frame>,
    /// The resolution of the finished forms, made on its first read, which
    /// every clone of the state shares until a form finishes.
    resolved: Arc<std::sync::OnceLock<Arc<ResolvedProgram>>>,
    /// The checked program of the finished forms, resolved from the
    /// resolution of the state before the last form finished, made on its
    /// first read and shared by every clone of the state until a form
    /// finishes.
    checked_last: Arc<std::sync::OnceLock<Outcome<CheckedProgram>>>,
}

/// An open node of the form in progress, with its children so far.
#[derive(Clone, Debug)]
enum Frame {
    Clause(ClauseFrame),
    /// A `ONE` mark of a clause, with its key labels so far.
    One(Vec<LabelId>),
    Body(BodyFrame),
    Atom(AtomFrame),
    Site(SiteFrame),
    Constraint(ConstraintFrame),
    Or(Vec<Node<Body>>),
    Lists(ListsFrame),
    Instance(InstanceFrame),
    KeyClause(KeyClauseFrame),
    Input(InputFrame),
    HeadSite(HeadSiteFrame),
    Choose(ChooseFrame),
    Rigid(RigidFrame),
}

/// The frame of `$variant` on top of `$state`'s stack.
macro_rules! top {
    ($state:expr, $variant:path) => {
        match $state.stack.last_mut() {
            Some($variant(frame)) => frame,
            _ => unreachable!("the frame stands on top"),
        }
    };
}

#[derive(Clone, Debug)]
struct ClauseFrame {
    keyword: ClauseKeyword,
    proposers: Vec<LibName>,
    stage: ClauseStage,
}

#[derive(Clone, Debug)]
enum ClauseStage {
    /// After the keyword and each proposer, before the body opens.
    Proposers,
    /// The body stands open above the clause.
    Body,
    /// The body is complete: the `SET` mark, then the `ONE` marks, then the
    /// clause's `END`.
    Marks { body: Node<Body>, ones: Vec<OneMark>, set: bool },
}

/// What closes a body, by the node that holds it.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Close {
    /// A clause's body: `ONE` or `END`.
    Clause,
    /// A branch of an `OR`: `ALSO`, which opens the next branch, or `END`.
    Branch,
    /// Each other list: `END`.
    List,
    /// The form of a `NOT` over a form: its one conjunct.
    Not,
}

#[derive(Clone, Debug)]
struct BodyFrame {
    conjuncts: Vec<Conjunct>,
    close: Close,
    /// Whether the body is a key's body or stands within one, where `^`
    /// marks a key column.
    key: bool,
    /// Whether a `NOT` stands before the next conjunct.
    negate: bool,
}

#[derive(Clone, Debug)]
struct AtomFrame {
    relation: RelationRef,
    /// The names of the relation's columns, by the position of a column
    /// token.
    columns: Arc<[ColumnName]>,
    sites: Vec<Site>,
    negated: bool,
}

#[derive(Clone, Debug)]
struct SiteFrame {
    column: ColumnName,
    args: Vec<SiteArg>,
    /// The count of the fields of the record the site's column holds, where
    /// it holds one.
    record: Option<u16>,
    /// The field whose column token stands, which its label follows.
    field: Option<u32>,
}

#[derive(Clone, Debug)]
struct ConstraintFrame {
    op: ConstraintOp,
    first: Option<ConstraintLabel>,
}

/// The lists of an `IF` form, or of an `ALL` form where `all` holds.
#[derive(Clone, Debug)]
struct ListsFrame {
    all: bool,
    lists: Vec<Node<Body>>,
}

#[derive(Clone, Debug)]
struct InstanceFrame {
    /// The slot of the first relation the instance declares.
    first: u32,
    /// The component, from its token on.
    component: Option<LibName>,
    key: Option<Node<KeyClause>>,
    inputs: Vec<Node<InstanceInput>>,
    stage: Naming,
}

#[derive(Clone, Debug)]
struct KeyClauseFrame {
    body: Option<Node<Body>>,
    inputs: Vec<Node<InstanceInput>>,
    stage: Naming,
}

/// Where the clauses of an instance stand.
#[derive(Clone, Copy, Debug)]
enum Naming {
    /// The engine has named the `key`, or the input at this position of the
    /// component, and the language model answers with `SKIP` or the clause.
    Named(Option<usize>),
    /// A child stands open above, or the component is yet to come.
    Open,
}

#[derive(Clone, Debug)]
struct InputFrame {
    /// The input's position among the component's inputs.
    position: usize,
    name: PortName,
    columns: Arc<[ColumnName]>,
    body: Option<Node<Body>>,
    head: Vec<Site>,
    /// The column whose projection stands open, once the body is complete.
    column: usize,
}

#[derive(Clone, Debug)]
struct HeadSiteFrame {
    column: ColumnName,
    args: Vec<SiteArg>,
    /// The count of the fields written.
    fields: u32,
    field: Option<u32>,
    /// Whether the `END` of the site's record stands, which the `END` of the
    /// projection's column follows.
    record_ended: bool,
}

#[derive(Clone, Debug)]
struct ChooseFrame {
    rows: Option<KeyBody>,
    from: Option<Node<Body>>,
    never: Vec<Node<Body>>,
    stage: ChooseStage,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum ChooseStage {
    For,
    ForOpen,
    FromOpen,
    Never,
    NeverOpen,
    /// After a `never` body: `ALSO` and the next, or the form's `END`.
    NeverEnd,
}

#[derive(Clone, Debug)]
struct RigidFrame {
    key: Option<KeyBody>,
    instance: Option<KeyBody>,
    parts: Vec<Node<Atom>>,
    stage: RigidStage,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum RigidStage {
    Key,
    KeyOpen,
    Instance,
    InstanceOpen,
    Parts,
}

/// The node of a frame: the node a closed frame gives the frame below it,
/// or, in [`State::partial`], the partial node of an open frame.
enum Built {
    Body(Node<Body>),
    Conjunct(Conjunct),
    Atom { atom: Node<Atom>, negated: bool },
    Site(Site),
    /// A head site, or none for an empty projection.
    HeadSite(Option<Site>),
    Input { input: Node<InstanceInput>, position: usize },
    KeyClause(Node<KeyClause>),
    Form(Form),
}

/// What a frame does with a token.
enum Offer {
    /// The frame consumed the token.
    Taken,
    /// The stack changed and the token stands, for the new top.
    Again,
    /// The frame is complete: it closes, its node goes to the frame below
    /// it, and the token stands where `consumed` does not hold.
    Close { consumed: bool },
}

impl State {
    pub(super) fn new() -> State {
        State { program: Node::new(Program { forms: Arc::from([]) }), declared: Arc::from([]), finished_slots: 0, labels: 0, stack: Vec::new(), resolved: Arc::default(), checked_last: Arc::default() }
    }

    /// The finished forms.
    pub(super) fn program(&self) -> &Node<Program> {
        &self.program
    }

    /// The resolution of the finished forms, a synthesized program whose
    /// names resolve within it.
    pub(super) fn resolved(&self, registry: &Registry) -> Arc<ResolvedProgram> {
        let resolved = self.resolved.get_or_init(|| Arc::new(resolve(&self.program, None, &SolverScope::default(), registry).value));
        Arc::clone(resolved)
    }

    /// The checked program of the finished forms, as [`State::checked_last`]
    /// holds it.
    pub(super) fn checked_last(&self) -> &std::sync::OnceLock<Outcome<CheckedProgram>> {
        &self.checked_last
    }

    /// The resolution of `partial`, the finished forms with the form in
    /// progress as the last form, as [`State::partial`] gives it.
    fn resolved_partial(&self, partial: &Node<Program>, registry: &Registry) -> ResolvedProgram {
        resolve_last(&self.resolved(registry), partial, registry)
    }

    /// The state after `token`, and the tokens the engine emits after it.
    pub(super) fn step(&self, context: &Context<'_>, token: &Token) -> Result<(State, Vec<Token>), Unexpected> {
        let mut next = self.clone();
        let mut forced = Vec::new();
        loop {
            match next.offer(context, token, &mut forced)? {
                Offer::Taken => break,
                Offer::Again => continue,
                Offer::Close { consumed } => {
                    let closer = consumed.then_some(token);
                    if let Some(built) = next.close(context, &mut forced)? {
                        next.deliver(context, built, closer, &mut forced)?;
                    }
                    if consumed {
                        break;
                    }
                }
            }
        }
        Ok((next, forced))
    }

    /// The program with the form in progress as its last form, and the path
    /// in that form of the innermost open node, or none where the last form
    /// is complete; or none where the form in progress shows no node yet.
    pub(super) fn partial(&self) -> Option<(Node<Program>, Option<NodePath>)> {
        if self.stack.is_empty() {
            return Some((self.program.clone(), None));
        }
        let mut built = None;
        let mut shown = vec![false; self.stack.len()];
        for (index, frame) in self.stack.iter().enumerate().rev() {
            built = self.partial_node(frame, built);
            shown[index] = built.is_some();
        }
        let Some(Built::Form(form)) = built else { return None };
        let open = (0..self.stack.len() - 1).take_while(|index| shown[index + 1]).map(|index| PathStep(child_step(&self.stack[index], &self.stack[index + 1])));
        Some((self.with_form(form), Some(NodePath(open.collect()))))
    }

    fn with_form(&self, form: Form) -> Node<Program> {
        let forms = self.program.value().forms.iter().cloned().chain([form]).collect();
        Node::new(Program { forms })
    }

    fn finish_form(&mut self, form: Form) {
        self.program = self.with_form(form);
        self.finished_slots = self.next_slot();
        self.resolved = Arc::default();
        self.checked_last = Arc::default();
        self.labels = 0;
    }

    fn next_slot(&self) -> u32 {
        u32::try_from(self.declared.len()).expect("fewer than 2^32 relations")
    }

    /// The readable relations of the finished forms declared from `first` on,
    /// each with its slot.
    pub(super) fn declared_from(&self, first: u32) -> impl Iterator<Item = (u32, &ProgramRelation)> {
        (first..self.finished_slots).zip(self.declared[first as usize..].iter()).filter(|(_, declared)| declared.readable).map(|(slot, declared)| (slot, &declared.relation))
    }

    /// The count of the relations that the finished forms declare, which is
    /// the first slot of the form in progress.
    pub(super) fn finished_slots(&self) -> u32 {
        self.finished_slots
    }

    /// The slot that the clause in progress takes.
    pub(super) fn open_slot(&self) -> u32 {
        self.next_slot()
    }

    /// Takes the next slot for `relation`, with the columns `columns`, and
    /// gives it.
    fn declare(&mut self, relation: ProgramRelation, columns: Arc<[ColumnName]>, readable: bool) -> u32 {
        let slot = self.next_slot();
        self.declared = self.declared.iter().cloned().chain([Arc::new(Declared { relation, columns, readable })]).collect();
        slot
    }

    /// Whether the innermost body is a key's body or stands within one.
    fn in_key(&self) -> bool {
        self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Body(body) => Some(body.key),
            _ => None,
        }) == Some(true)
    }

    fn push_body(&mut self, close: Close, key: bool) {
        self.stack.push(Frame::Body(BodyFrame { conjuncts: Vec::new(), close, key, negate: false }));
    }

    /// The label that `token` gives, where it gives one: `*` and, where
    /// `key` holds, `^` make the next label, whose echo goes to `forced`.
    fn label_token(&mut self, token: &Token, key: bool, forced: &mut Vec<Token>) -> Option<LabelUse> {
        let mut make = |state: &mut State| {
            let id = state.labels;
            state.labels += 1;
            forced.push(Token::Label(id));
            LabelId(id)
        };
        match token {
            Token::Control(Control::Fresh) => Some(LabelUse::Fresh(make(self))),
            Token::Control(Control::Key) if key => Some(LabelUse::Key(make(self))),
            Token::Control(Control::Zero) => Some(LabelUse::Zero),
            Token::Label(id) if *id < self.labels => Some(LabelUse::Join(LabelId(*id))),
            _ => None,
        }
    }

    fn offer(&mut self, context: &Context<'_>, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        match self.stack.last() {
            None => self.open_form(token, forced),
            Some(Frame::Clause(_)) => self.offer_clause(context, token),
            Some(Frame::One(_)) => match token {
                Token::Label(id) if *id < self.labels => {
                    top!(self, Frame::One).push(LabelId(*id));
                    Ok(Offer::Taken)
                }
                Token::Control(Control::End) => Ok(Offer::Close { consumed: true }),
                _ => Err("a `ONE` mark holds labels seen, then its `END`"),
            },
            Some(Frame::Body(_)) => self.offer_body(context, token),
            Some(Frame::Atom(_)) => match token {
                Token::Column(position) => {
                    let atom = top!(self, Frame::Atom);
                    let column = atom.columns.get(*position as usize).ok_or("the relation has no column at the position")?.clone();
                    self.open_site(context, column);
                    Ok(Offer::Taken)
                }
                _ => Ok(Offer::Close { consumed: false }),
            },
            Some(Frame::Site(_)) => self.offer_site(token, forced),
            Some(Frame::Constraint(_)) => self.offer_constraint(token, forced),
            Some(Frame::Instance(_)) => self.offer_instance(context, token, forced),
            Some(Frame::KeyClause(clause)) => match (clause.stage, token) {
                (Naming::Named(Some(position)), Token::Control(Control::Skip)) => {
                    self.name_input(context, position + 1, forced);
                    Ok(Offer::Taken)
                }
                (Naming::Named(Some(position)), _) => {
                    top!(self, Frame::KeyClause).stage = Naming::Open;
                    self.open_input(context, position);
                    Ok(Offer::Again)
                }
                _ => Err("a key clause holds its body, then its inputs"),
            },
            Some(Frame::HeadSite(_)) => self.offer_head_site(token, forced),
            Some(Frame::Choose(_)) => self.offer_choose(token, forced),
            Some(Frame::Rigid(_)) => self.offer_rigid(context, token, forced),
            Some(Frame::Or(_) | Frame::Lists(_) | Frame::Input(_)) => unreachable!("a frame that stands below an open child"),
        }
    }

    /// The keyword of a form.
    fn open_form(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let frame = match token {
            Token::Control(Control::Rule) => Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Rule, proposers: Vec::new(), stage: ClauseStage::Proposers }),
            Token::Control(Control::Det) => Frame::Clause(ClauseFrame { keyword: ClauseKeyword::Det, proposers: Vec::new(), stage: ClauseStage::Proposers }),
            Token::Control(Control::Init) => {
                Frame::Instance(InstanceFrame { first: self.next_slot(), component: None, key: None, inputs: Vec::new(), stage: Naming::Open })
            }
            Token::Control(Control::Choose) => {
                forced.push(Token::Column(0));
                Frame::Choose(ChooseFrame { rows: None, from: None, never: Vec::new(), stage: ChooseStage::For })
            }
            Token::Control(Control::RigidDet) => {
                forced.push(Token::Column(0));
                Frame::Rigid(RigidFrame { key: None, instance: None, parts: Vec::new(), stage: RigidStage::Key })
            }
            _ => return Err("a form opens with its keyword"),
        };
        self.stack.push(frame);
        Ok(Offer::Taken)
    }

    /// A clause's proposers, which a column token after the last of them
    /// makes an atom of the body, and its marks and `END`.
    fn offer_clause(&mut self, context: &Context<'_>, token: &Token) -> Result<Offer, Unexpected> {
        let clause = top!(self, Frame::Clause);
        match (&clause.stage, token) {
            (ClauseStage::Proposers, Token::Proposer(name)) => {
                clause.proposers.push(name.clone());
                Ok(Offer::Taken)
            }
            (ClauseStage::Proposers, Token::Column(_)) if !clause.proposers.is_empty() => {
                let proposer = clause.proposers.pop().expect("a proposer");
                clause.stage = ClauseStage::Body;
                self.push_body(Close::Clause, false);
                self.open_atom(context, &Token::Proposer(proposer))?;
                Ok(Offer::Again)
            }
            (ClauseStage::Proposers, _) => {
                clause.stage = ClauseStage::Body;
                self.push_body(Close::Clause, false);
                Ok(Offer::Again)
            }
            (ClauseStage::Marks { ones, set: false, .. }, Token::Control(Control::Set)) if ones.is_empty() => {
                let ClauseStage::Marks { set, .. } = &mut clause.stage else { unreachable!("a clause at its marks") };
                *set = true;
                Ok(Offer::Taken)
            }
            (ClauseStage::Marks { .. }, Token::Control(Control::One)) => {
                self.stack.push(Frame::One(Vec::new()));
                Ok(Offer::Taken)
            }
            (ClauseStage::Marks { .. }, Token::Control(Control::End)) => Ok(Offer::Close { consumed: true }),
            _ => Err("a clause's marks end with its `END`"),
        }
    }

    /// A body's conjuncts, then its closing token. `OR` opens an `OR` form
    /// wherever it stands, and `ALSO` closes a branch of one.
    fn offer_body(&mut self, context: &Context<'_>, token: &Token) -> Result<Offer, Unexpected> {
        let in_key = self.in_key();
        let body = top!(self, Frame::Body);
        if let Token::Control(control @ (Control::Not | Control::Op(_) | Control::Or | Control::If | Control::All)) = token {
            if std::mem::take(&mut body.negate) {
                self.push_body(Close::Not, in_key);
                if *control == Control::Not {
                    top!(self, Frame::Body).negate = true;
                    return Ok(Offer::Taken);
                }
                return Ok(Offer::Again);
            }
            match control {
                Control::Not => body.negate = true,
                Control::Op(op) => self.stack.push(Frame::Constraint(ConstraintFrame { op: *op, first: None })),
                Control::Or => {
                    self.stack.push(Frame::Or(Vec::new()));
                    self.push_body(Close::Branch, in_key);
                }
                control => {
                    self.stack.push(Frame::Lists(ListsFrame { all: *control == Control::All, lists: Vec::new() }));
                    self.push_body(Close::List, in_key);
                }
            }
            return Ok(Offer::Taken);
        }
        if is_relation(token) {
            self.open_atom(context, token)?;
            return Ok(Offer::Taken);
        }
        let closes = match (body.close, token) {
            (Close::Not, _) => false,
            (_, Token::Control(Control::End)) => true,
            (Close::Clause, Token::Control(Control::One | Control::Set)) | (Close::Branch, Token::Control(Control::Also)) => true,
            _ => false,
        };
        match closes && !body.negate {
            true => Ok(Offer::Close { consumed: true }),
            false => Err("a body holds its conjuncts, then its closing token"),
        }
    }

    /// Opens the atom of the relation token `token`.
    fn open_atom(&mut self, context: &Context<'_>, token: &Token) -> Result<(), Unexpected> {
        let registry = context.registry;
        let lib = |name: &LibName, proposer: bool| match registry.entry(name) {
            Some(LibEntry::Proposer(_)) if proposer => Ok(RelationRef::Lib(name.clone())),
            Some(LibEntry::Relation(_) | LibEntry::Macro(_)) if !proposer && component(registry, name).is_none() => Ok(RelationRef::Lib(name.clone())),
            _ => Err("the lib name is no relation"),
        };
        let (relation, columns): (RelationRef, Arc<[ColumnName]>) = match token {
            Token::Relation(slot) => {
                if self.stack.iter().any(|frame| matches!(frame, Frame::Instance(instance) if *slot >= instance.first)) && !self.reads_outputs(context) {
                    return Err("an instance's relations are read within it only by an input that reads its outputs");
                }
                let declared = self.declared.get(*slot as usize).filter(|declared| declared.readable).ok_or("the slot holds no relation that a read resolves")?;
                let relation = match &declared.relation {
                    ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
                    ProgramRelation::Output(output) => RelationRef::Output(output.clone()),
                };
                (relation, declared.columns.clone())
            }
            Token::Fact(fact) => (RelationRef::Fact(*fact), Arc::from([])),
            Token::Lib(name) => (lib(name, false)?, Arc::from([])),
            Token::Proposer(name) => (lib(name, true)?, Arc::from([])),
            _ => return Err("an atom opens with its relation"),
        };
        let columns = match token {
            Token::Relation(_) => columns,
            _ => typed_columns(registry, &relation).ok_or("the lib declares no columns of the relation")?.iter().map(|column| column.name.clone()).collect(),
        };
        let negated = match self.stack.last_mut() {
            Some(Frame::Body(body)) => std::mem::take(&mut body.negate),
            _ => false,
        };
        self.stack.push(Frame::Atom(AtomFrame { relation, columns, sites: Vec::new(), negated }));
        if let Token::Relation(_) = token {
            let (program, open) = self.partial().expect("a form that shows its atom");
            let at = self.absolute(&open.expect("an open atom"));
            if reads_example_column(&self.resolved_partial(&program, context.registry), &at) {
                let atom = top!(self, Frame::Atom);
                atom.columns = std::iter::once(example()).chain(atom.columns.iter().cloned()).collect();
            }
        }
        Ok(())
    }

    /// Opens the site on `column` of the atom on top. A site on a column of
    /// a type parameter holds a record where the resolver places one there.
    fn open_site(&mut self, context: &Context<'_>, column: ColumnName) {
        let typed = type_parameter(&column);
        self.stack.push(Frame::Site(SiteFrame { column, args: Vec::new(), record: None, field: None }));
        if typed {
            let (program, open) = self.partial().expect("a form that shows its site");
            let at = self.absolute(&open.expect("an open site"));
            top!(self, Frame::Site).record = self.resolved_partial(&program, context.registry).column_group(&at).map(|group| group.len);
        }
    }

    /// The path in the program of the node at `open` in the form in
    /// progress.
    fn absolute(&self, open: &NodePath) -> NodePath {
        NodePath::top(self.program.value().forms.len() as u32).join(open)
    }

    /// A site's labels; on a record, each field's column token and label,
    /// then `END`.
    fn offer_site(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let in_key = self.in_key();
        let site = top!(self, Frame::Site);
        let (field, record) = (site.field, site.record);
        match (field, record, token) {
            (Some(field), _, _) => {
                let label = self.label_token(token, in_key, forced).ok_or("a field's column token is followed by its label")?;
                let site = top!(self, Frame::Site);
                site.args.push(field_arg(&site.column, field, label));
                site.field = None;
                return Ok(Offer::Taken);
            }
            (None, Some(fields), Token::Column(field)) if *field < u32::from(fields) => {
                site.field = Some(*field);
                return Ok(Offer::Taken);
            }
            (None, Some(_), Token::Control(Control::End)) => return Ok(Offer::Close { consumed: true }),
            _ => {}
        }
        match self.label_token(token, in_key, forced) {
            Some(label) => {
                let site = top!(self, Frame::Site);
                site.args.push(bare_arg(&site.column, label));
                Ok(Offer::Taken)
            }
            None if record.is_some() => Err("a site on a record ends with `END`"),
            None => Ok(Offer::Close { consumed: false }),
        }
    }

    fn offer_constraint(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let label = self.label_token(token, false, forced).ok_or("a constraint holds a label, then a label or `0`")?;
        let constraint = top!(self, Frame::Constraint);
        let Some(first) = constraint.first else {
            constraint.first = Some(ConstraintLabel::try_from(label).map_err(|_| "a constraint's first operand is a label")?);
            return Ok(Offer::Taken);
        };
        let second = match label {
            LabelUse::Zero => Operand::Zero,
            label => Operand::Label(ConstraintLabel::try_from(label).expect("a label")),
        };
        let conjunct = Conjunct::Constraint(Constraint { op: constraint.op, first, second });
        self.stack.pop();
        let body = top!(self, Frame::Body);
        body.conjuncts.push(conjunct);
        self.close_not();
        Ok(Offer::Taken)
    }

    fn offer_instance(&mut self, context: &Context<'_>, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let instance = top!(self, Frame::Instance);
        match (instance.component.is_some(), instance.stage, token) {
            (false, _, Token::Lib(name)) => {
                let declared = component(context.registry, name).ok_or("an `INIT` names a component")?;
                instance.component = Some(name.clone());
                instance.stage = Naming::Named(None);
                let owner = OutputOwner::Instance(InstanceName(DeclaredName::Slot(instance.first)));
                let every: Vec<&PortName> = declared.inputs.iter().map(|input| &input.port.name).collect();
                for port in declared.relation_ports(&every) {
                    let output = OutputName { of: owner.clone(), path: [OutputStep::Port(port.name.clone())].into() };
                    let readable = declared.outputs.iter().any(|output| output.name == port.name);
                    self.declare(ProgramRelation::Output(output), port.columns.iter().map(|column| column.name.clone()).collect(), readable);
                }
                forced.push(Token::Column(0));
                Ok(Offer::Taken)
            }
            (true, Naming::Named(None), Token::Control(Control::Skip)) => {
                self.name_input(context, 0, forced);
                Ok(Offer::Taken)
            }
            (true, Naming::Named(None), _) => {
                instance.stage = Naming::Open;
                self.stack.push(Frame::KeyClause(KeyClauseFrame { body: None, inputs: Vec::new(), stage: Naming::Open }));
                self.push_body(Close::List, true);
                Ok(Offer::Again)
            }
            (true, Naming::Named(Some(position)), Token::Control(Control::Skip)) => {
                self.name_input(context, position + 1, forced);
                Ok(Offer::Taken)
            }
            (true, Naming::Named(Some(position)), _) => {
                instance.stage = Naming::Open;
                self.open_input(context, position);
                Ok(Offer::Again)
            }
            _ => Err("an `INIT` names its component"),
        }
    }

    /// A projection's column: its labels, or its fields, each a column
    /// token and a label, then the record's `END`; then the column's `END`.
    fn offer_head_site(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let site = top!(self, Frame::HeadSite);
        if let Some(field) = site.field {
            let label = self.label_token(token, false, forced).ok_or("a field's column token is followed by its label")?;
            let site = top!(self, Frame::HeadSite);
            site.args.push(field_arg(&site.column, field, label));
            site.field = None;
            site.fields += 1;
            return Ok(Offer::Taken);
        }
        match token {
            Token::Control(Control::End) => {
                let record = site.fields > 0 || site.args.len() > 1;
                if record && !site.record_ended {
                    site.record_ended = true;
                    return Ok(Offer::Taken);
                }
                Ok(Offer::Close { consumed: true })
            }
            _ if site.record_ended => Err("a projection's column ends with `END`"),
            Token::Column(field) if *field == site.fields => {
                site.field = Some(*field);
                Ok(Offer::Taken)
            }
            _ => {
                let label = self.label_token(token, false, forced).ok_or("a projection holds labels, then `END`")?;
                let site = top!(self, Frame::HeadSite);
                site.args.push(bare_arg(&site.column, label));
                Ok(Offer::Taken)
            }
        }
    }

    fn offer_choose(&mut self, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let choose = top!(self, Frame::Choose);
        let skip = *token == Token::Control(Control::Skip);
        match (choose.stage, skip) {
            (ChooseStage::For, true) => {
                choose.stage = ChooseStage::FromOpen;
                forced.push(Token::Column(1));
                self.push_body(Close::List, false);
                Ok(Offer::Taken)
            }
            (ChooseStage::For, false) => {
                choose.stage = ChooseStage::ForOpen;
                self.push_body(Close::List, true);
                Ok(Offer::Again)
            }
            (ChooseStage::Never, true) => {
                self.finish_choose(forced);
                Ok(Offer::Taken)
            }
            (ChooseStage::Never, false) => {
                choose.stage = ChooseStage::NeverOpen;
                self.push_body(Close::List, false);
                Ok(Offer::Again)
            }
            (ChooseStage::NeverEnd, _) => match token {
                Token::Control(Control::Also) => {
                    choose.stage = ChooseStage::NeverOpen;
                    self.push_body(Close::List, false);
                    Ok(Offer::Taken)
                }
                Token::Control(Control::End) => {
                    self.finish_choose(forced);
                    Ok(Offer::Taken)
                }
                _ => Err("a `never` body is followed by `ALSO` and the next, or by the form's `END`"),
            },
            _ => unreachable!("a `CHOOSE` form whose body stands open"),
        }
    }

    fn offer_rigid(&mut self, context: &Context<'_>, token: &Token, forced: &mut Vec<Token>) -> Result<Offer, Unexpected> {
        let rigid = top!(self, Frame::Rigid);
        let skip = *token == Token::Control(Control::Skip);
        match (rigid.stage, skip) {
            (RigidStage::Key, true) => {
                rigid.stage = RigidStage::Instance;
                forced.push(Token::Column(1));
                Ok(Offer::Taken)
            }
            (RigidStage::Instance, true) => {
                rigid.stage = RigidStage::Parts;
                Ok(Offer::Taken)
            }
            (RigidStage::Key, false) | (RigidStage::Instance, false) => {
                rigid.stage = if rigid.stage == RigidStage::Key { RigidStage::KeyOpen } else { RigidStage::InstanceOpen };
                self.push_body(Close::List, true);
                Ok(Offer::Again)
            }
            (RigidStage::Parts, _) if *token == Token::Control(Control::End) => Ok(Offer::Close { consumed: true }),
            (RigidStage::Parts, _) if is_relation(token) => {
                self.open_atom(context, token)?;
                Ok(Offer::Taken)
            }
            _ => Err("a `RIGID_DET` form's parts are atoms, then its `END`"),
        }
    }

    /// Pops the top frame and gives its node, or none where the frame
    /// below has taken it.
    fn close(&mut self, context: &Context<'_>, forced: &mut Vec<Token>) -> Result<Option<Built>, Unexpected> {
        let frame = self.stack.pop().expect("an open frame");
        let built = match frame {
            Frame::Clause(clause) => {
                let ClauseStage::Marks { body, ones, set } = clause.stage else { unreachable!("a clause closes at its marks' `END`") };
                let slot = self.next_slot();
                let columns = slot_columns(made_labels(body.value()), 0);
                let names: Arc<[ColumnName]> = match (columns.is_empty(), clause.proposers.first()) {
                    (true, Some(proposer)) => proposer_columns(context.registry, proposer).ok_or("a clause's proposer is one the lib names")?.into(),
                    _ => columns.iter().map(|column| column.name.clone()).collect(),
                };
                let derives = ProgramRelation::Declared(RelationName(DeclaredName::Slot(slot)));
                let value = Clause { keyword: clause.keyword, derives: derives.clone(), gloss: None, proposers: clause.proposers.into(), body, ones: ones.into(), set, columns };
                self.declare(derives, names, true);
                forced.push(Token::Relation(slot));
                Built::Form(Form::Clause(Node::new(value)))
            }
            Frame::One(key) => {
                let clause = top!(self, Frame::Clause);
                let ClauseStage::Marks { ones, .. } = &mut clause.stage else { unreachable!("a mark stands on its clause's marks") };
                ones.push(OneMark { key: key.into() });
                return Ok(None);
            }
            Frame::Body(body) => Built::Body(Node::new(Body { conjuncts: body.conjuncts.into() })),
            Frame::Atom(atom) => Built::Atom { atom: Node::new(Atom { relation: atom.relation, sites: atom.sites.into() }), negated: atom.negated },
            Frame::Site(site) => Built::Site(Site { column: site.column, value: SiteValue { args: site.args.into() } }),
            Frame::HeadSite(site) => Built::HeadSite((!site.args.is_empty()).then(|| Site { column: site.column, value: SiteValue { args: site.args.into() } })),
            Frame::Rigid(rigid) => {
                let name = RigidDetName(DeclaredName::Slot(self.next_slot()));
                let value = RigidDet { name: name.clone(), key: rigid.key, instance: rigid.instance, parts: rigid.parts.into() };
                for (steps, columns) in rigid_outputs(&value) {
                    let output = OutputName { of: OutputOwner::RigidDet(name.clone()), path: steps };
                    let slot = self.declare(ProgramRelation::Output(output), columns.names().cloned().collect(), true);
                    forced.push(Token::Relation(slot));
                }
                Built::Form(Form::RigidDet(Node::new(value)))
            }
            Frame::Constraint(_) | Frame::Or(_) | Frame::Lists(_) | Frame::Instance(_) | Frame::KeyClause(_) | Frame::Input(_) | Frame::Choose(_) => {
                unreachable!("a frame that its own offer or its child's delivery closes")
            }
        };
        Ok(Some(built))
    }

    /// Gives `built`, the node of the frame that closed on `closer`, to the
    /// frame below it.
    fn deliver(&mut self, context: &Context<'_>, built: Built, closer: Option<&Token>, forced: &mut Vec<Token>) -> Result<(), Unexpected> {
        if let Built::Form(form) = built {
            self.finish_form(form);
            return Ok(());
        }
        let in_key = self.in_key();
        let ends = closer == Some(&Token::Control(Control::End));
        match (self.stack.last_mut().expect("a frame below"), built) {
            (Frame::Clause(clause), Built::Body(body)) => {
                let set = closer == Some(&Token::Control(Control::Set));
                clause.stage = ClauseStage::Marks { body, ones: Vec::new(), set };
                match (ends, set) {
                    (true, _) => {
                        let built = self.close(context, forced)?.expect("a clause gives its form");
                        self.deliver(context, built, closer, forced)?;
                    }
                    (false, true) => {}
                    (false, false) => self.stack.push(Frame::One(Vec::new())),
                }
            }
            (Frame::Body(body), Built::Conjunct(conjunct)) => {
                body.conjuncts.push(conjunct);
                self.close_not();
            }
            (Frame::Body(body), Built::Atom { atom, negated }) => {
                body.conjuncts.push(if negated { Conjunct::Not(Negated::Atom(atom)) } else { Conjunct::Atom(atom) });
                self.close_not();
            }
            (Frame::Rigid(rigid), Built::Atom { atom, .. }) => rigid.parts.push(atom),
            (Frame::Atom(atom), Built::Site(site)) => atom.sites.push(site),
            (Frame::Or(branches), Built::Body(body)) => {
                branches.push(body);
                match ends {
                    true => {
                        let Some(Frame::Or(branches)) = self.stack.pop() else { unreachable!("the `OR` stands on top") };
                        self.deliver(context, Built::Conjunct(Conjunct::Or(branches.into())), None, forced)?;
                    }
                    false => self.push_body(Close::Branch, in_key),
                }
            }
            (Frame::Lists(lists), Built::Body(body)) => {
                lists.lists.push(body);
                if lists.lists.len() < if lists.all { 2 } else { 3 } {
                    self.push_body(Close::List, in_key);
                } else {
                    let Some(Frame::Lists(ListsFrame { all, lists })) = self.stack.pop() else { unreachable!("the lists stand on top") };
                    let conjunct = match all {
                        false => {
                            let [test, then, otherwise] = <[Node<Body>; 3]>::try_from(lists).expect("an `IF` form's three lists");
                            Conjunct::If { test, then, otherwise }
                        }
                        true => {
                            let [domain, body] = <[Node<Body>; 2]>::try_from(lists).expect("an `ALL` form's two lists");
                            Conjunct::All { domain, body }
                        }
                    };
                    self.deliver(context, Built::Conjunct(conjunct), None, forced)?;
                }
            }
            (Frame::KeyClause(clause), Built::Body(body)) => {
                clause.body = Some(body);
                self.name_input(context, 0, forced);
            }
            (Frame::KeyClause(KeyClauseFrame { inputs, .. }) | Frame::Instance(InstanceFrame { inputs, .. }), Built::Input { input, position }) => {
                inputs.push(input);
                self.name_input(context, position + 1, forced);
            }
            (Frame::Input(input), Built::Body(body)) => {
                input.body = Some(body);
                if let Some(built) = self.next_column(forced) {
                    self.deliver(context, built, None, forced)?;
                }
            }
            (Frame::Input(input), Built::HeadSite(site)) => {
                input.head.extend(site);
                input.column += 1;
                if let Some(built) = self.next_column(forced) {
                    self.deliver(context, built, None, forced)?;
                }
            }
            (Frame::Choose(choose), Built::Body(body)) => match choose.stage {
                ChooseStage::ForOpen => {
                    choose.rows = Some(key_body(body));
                    choose.stage = ChooseStage::FromOpen;
                    forced.push(Token::Column(1));
                    self.push_body(Close::List, false);
                }
                ChooseStage::FromOpen => {
                    choose.from = Some(body);
                    choose.stage = ChooseStage::Never;
                    forced.push(Token::Column(2));
                }
                _ => {
                    choose.never.push(body);
                    choose.stage = ChooseStage::NeverEnd;
                }
            },
            (Frame::Rigid(rigid), Built::Body(body)) => match rigid.stage {
                RigidStage::KeyOpen => {
                    rigid.key = Some(key_body(body));
                    rigid.stage = RigidStage::Instance;
                    forced.push(Token::Column(1));
                }
                _ => {
                    rigid.instance = Some(key_body(body));
                    rigid.stage = RigidStage::Parts;
                }
            },
            _ => unreachable!("a node that the frame below takes"),
        }
        Ok(())
    }

    /// Closes the `NOT` over a form on top, which holds its one conjunct,
    /// and each that its close completes.
    fn close_not(&mut self) {
        while let Some(Frame::Body(BodyFrame { close: Close::Not, conjuncts, .. })) = self.stack.last() {
            if conjuncts.is_empty() {
                return;
            }
            let Some(Frame::Body(body)) = self.stack.pop() else { unreachable!("the `NOT` stands on top") };
            let [form] = <[Conjunct; 1]>::try_from(body.conjuncts).expect("a `NOT` over one form");
            top!(self, Frame::Body).conjuncts.push(Conjunct::Not(Negated::Form(Arc::new(form))));
        }
    }

    /// The instance whose clauses stand open.
    fn instance(&self) -> &InstanceFrame {
        let instance = self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Instance(instance) => Some(instance),
            _ => None,
        });
        instance.expect("an input stands in an instance")
    }

    fn component<'r>(&self, context: &Context<'r>) -> &'r Component {
        let name = self.instance().component.as_ref().expect("a named component");
        component(context.registry, name).expect("a component the lib names")
    }

    /// The engine's name of the next input at or after `from` that the open
    /// group of the instance names; past the last, the close of that group:
    /// of a key clause, after which the instance names each input the key
    /// clause does not write, or of the instance, which declares its
    /// relations.
    fn name_input(&mut self, context: &Context<'_>, from: usize, forced: &mut Vec<Token>) {
        let declared = self.component(context);
        let in_key = matches!(self.stack.last(), Some(Frame::KeyClause(_)));
        let keyed = self.instance().key.iter().flat_map(|key| key.value().inputs.iter().map(|input| input.value().name.clone()));
        let keyed: Vec<PortName> = keyed.collect();
        let next = (from..declared.inputs.len()).find(|position| in_key || !keyed.contains(&declared.inputs[*position].port.name));
        if let Some(position) = next {
            match self.stack.last_mut() {
                Some(Frame::KeyClause(KeyClauseFrame { stage, .. }) | Frame::Instance(InstanceFrame { stage, .. })) => *stage = Naming::Named(Some(position)),
                _ => unreachable!("an input stands in a key clause or an instance"),
            }
            forced.push(Token::Column(1 + position as u32));
            return;
        }
        match self.stack.pop() {
            Some(Frame::KeyClause(clause)) => {
                let key = KeyClause { key: key_body(clause.body.expect("a key clause's body")), inputs: clause.inputs.into() };
                top!(self, Frame::Instance).key = Some(Node::new(key));
                self.name_input(context, 0, forced);
            }
            Some(Frame::Instance(instance)) => {
                forced.extend((instance.first..self.next_slot()).map(Token::Relation));
                let name = InstanceName(DeclaredName::Slot(instance.first));
                let component = instance.component.expect("a named component");
                let value = Instance { name, component, key: instance.key, inputs: instance.inputs.into() };
                let written: Vec<&PortName> = written_inputs(value.key.as_ref(), &value.inputs).map(|input| &input.name).collect();
                let resolved = |declared: &Arc<Declared>, slot: usize| match &declared.relation {
                    ProgramRelation::Output(OutputName { path, .. }) if slot >= instance.first as usize && !declared.readable => {
                        matches!(&path[..], [OutputStep::Port(port)] if written.contains(&port))
                    }
                    _ => declared.readable,
                };
                let declared = self.declared.iter().enumerate().map(|(slot, declared)| match resolved(declared, slot) == declared.readable {
                    true => declared.clone(),
                    false => Arc::new(Declared { relation: declared.relation.clone(), columns: declared.columns.clone(), readable: true }),
                });
                self.declared = declared.collect();
                self.finish_form(Form::Instance(Node::new(value)));
            }
            _ => unreachable!("an input stands in a key clause or an instance"),
        }
    }

    /// Whether the innermost input stands open and reads its instance's
    /// outputs.
    fn reads_outputs(&self, context: &Context<'_>) -> bool {
        let input = self.stack.iter().rev().find_map(|frame| match frame {
            Frame::Input(input) => Some(input.position),
            _ => None,
        });
        input.is_some_and(|position| self.component(context).inputs[position].reads_outputs)
    }

    /// Opens the input at `position` of the instance's component.
    fn open_input(&mut self, context: &Context<'_>, position: usize) {
        let port = &self.component(context).inputs[position].port;
        let columns = port.columns.iter().map(|column| column.name.clone()).collect();
        self.stack.push(Frame::Input(InputFrame { position, name: port.name.clone(), columns, body: None, head: Vec::new(), column: 0 }));
        self.push_body(Close::List, false);
    }

    /// The engine's name of the next column of the input on top, or, past
    /// the last, the input.
    fn next_column(&mut self, forced: &mut Vec<Token>) -> Option<Built> {
        let input = top!(self, Frame::Input);
        if let Some(column) = input.columns.get(input.column) {
            forced.push(Token::Column(input.column as u32));
            let column = column.clone();
            self.stack.push(Frame::HeadSite(HeadSiteFrame { column, args: Vec::new(), fields: 0, field: None, record_ended: false }));
            return None;
        }
        let Some(Frame::Input(input)) = self.stack.pop() else { unreachable!("the input stands on top") };
        let value = InstanceInput { name: input.name, head: input.head.into(), body: input.body.expect("an input's body") };
        Some(Built::Input { input: Node::new(value), position: input.position })
    }

    /// Closes the `CHOOSE` form on top, which declares its relation.
    fn finish_choose(&mut self, forced: &mut Vec<Token>) {
        let Some(Frame::Choose(choose)) = self.stack.pop() else { unreachable!("the `CHOOSE` form stands on top") };
        let slot = self.next_slot();
        let from = choose.from.expect("a `CHOOSE` form's `from`");
        let rows = choose.rows.as_ref().map_or(0, |rows| rows.columns.len());
        let candidate_columns = slot_columns(made_labels(from.value()), rows);
        let name = RelationName(DeclaredName::Slot(slot));
        let row_columns = choose.rows.iter().flat_map(|rows| rows.columns.iter());
        let columns = row_columns.chain(candidate_columns.iter()).map(|column| column.name.clone()).collect();
        let from_inside_for = inside_for(choose.rows.as_ref(), from.value());
        let value = Choose { name: name.clone(), rows: choose.rows, candidate_columns, from, from_inside_for, never: choose.never.into() };
        self.declare(ProgramRelation::Declared(name), columns, true);
        forced.push(Token::Relation(slot));
        self.finish_form(Form::Choose(Node::new(value)));
    }

    /// The partial node of `frame`, with `child`, the partial node of the
    /// frame above it, as its last child.
    fn partial_node(&self, frame: &Frame, child: Option<Built>) -> Option<Built> {
        let open_body = |child: Option<Built>| match child {
            Some(Built::Body(body)) => body,
            _ => empty(),
        };
        let slot = DeclaredName::Slot(self.next_slot());
        let built = match frame {
            Frame::Clause(clause) => {
                let (body, ones, set) = match &clause.stage {
                    ClauseStage::Marks { body, ones, set } => (body.clone(), ones.clone(), *set),
                    _ => (open_body(child), Vec::new(), false),
                };
                let derives = ProgramRelation::Declared(RelationName(slot));
                let proposers = clause.proposers.iter().cloned().collect();
                let value = Clause { keyword: clause.keyword, derives, gloss: None, proposers, body, ones: ones.into(), set, columns: Arc::from([]) };
                Built::Form(Form::Clause(Node::new(value)))
            }
            Frame::One(_) | Frame::Constraint(_) => return None,
            Frame::Body(frame) => {
                let mut conjuncts = frame.conjuncts.clone();
                match child {
                    Some(Built::Conjunct(conjunct)) => conjuncts.push(conjunct),
                    Some(Built::Atom { atom, negated: true }) => conjuncts.push(Conjunct::Not(Negated::Atom(atom))),
                    Some(Built::Atom { atom, negated: false }) => conjuncts.push(Conjunct::Atom(atom)),
                    _ => {}
                }
                match frame.close {
                    Close::Not => Built::Conjunct(Conjunct::Not(Negated::Form(Arc::new(conjuncts.pop()?)))),
                    _ => Built::Body(Node::new(Body { conjuncts: conjuncts.into() })),
                }
            }
            Frame::Atom(atom) => {
                let sites = atom.sites.iter().cloned().chain(child.and_then(|child| match child {
                    Built::Site(site) => Some(site),
                    _ => None,
                }));
                Built::Atom { atom: Node::new(Atom { relation: atom.relation.clone(), sites: sites.collect() }), negated: atom.negated }
            }
            Frame::Site(site) => Built::Site(Site { column: site.column.clone(), value: SiteValue { args: site.args.iter().cloned().collect() } }),
            Frame::Or(branches) => Built::Conjunct(Conjunct::Or(branches.iter().cloned().chain([open_body(child)]).collect())),
            Frame::Lists(lists) => {
                let mut all: Vec<Node<Body>> = lists.lists.iter().cloned().chain([open_body(child)]).collect();
                all.resize_with(if lists.all { 2 } else { 3 }, empty);
                Built::Conjunct(match <[Node<Body>; 3]>::try_from(all) {
                    Ok([test, then, otherwise]) => Conjunct::If { test, then, otherwise },
                    Err(all) => {
                        let [domain, body] = <[Node<Body>; 2]>::try_from(all).expect("an `ALL` form's two lists");
                        Conjunct::All { domain, body }
                    }
                })
            }
            Frame::Instance(instance) => {
                let component = instance.component.clone()?;
                let mut key = instance.key.clone();
                let mut inputs = instance.inputs.clone();
                match child {
                    Some(Built::KeyClause(clause)) => key = Some(clause),
                    Some(Built::Input { input, .. }) => inputs.push(input),
                    _ => {}
                }
                let value = Instance { name: InstanceName(DeclaredName::Slot(instance.first)), component, key, inputs: inputs.into() };
                Built::Form(Form::Instance(Node::new(value)))
            }
            Frame::KeyClause(clause) => {
                let mut inputs = clause.inputs.clone();
                let key = match (&clause.body, child) {
                    (Some(body), child) => {
                        if let Some(Built::Input { input, .. }) = child {
                            inputs.push(input);
                        }
                        key_body(body.clone())
                    }
                    (None, child) => KeyBody { body: open_body(child), columns: Arc::from([]) },
                };
                Built::KeyClause(Node::new(KeyClause { key, inputs: inputs.into() }))
            }
            Frame::Input(input) => {
                let (head, body) = match (&input.body, child) {
                    (Some(body), Some(Built::HeadSite(Some(site)))) => (input.head.iter().cloned().chain([site]).collect(), body.clone()),
                    (Some(body), _) => (input.head.iter().cloned().collect(), body.clone()),
                    (None, child) => (Arc::from([]), open_body(child)),
                };
                Built::Input { input: Node::new(InstanceInput { name: input.name.clone(), head, body }), position: input.position }
            }
            Frame::HeadSite(site) => Built::HeadSite(Some(Site { column: site.column.clone(), value: SiteValue { args: site.args.iter().cloned().collect() } })),
            Frame::Choose(choose) => {
                let from = choose.from.clone().unwrap_or_else(empty);
                let mut value = Choose { name: RelationName(slot), rows: choose.rows.clone(), candidate_columns: Arc::from([]), from, from_inside_for: false, never: Arc::from([]) };
                let never = choose.never.iter().cloned();
                match choose.stage {
                    ChooseStage::ForOpen => value.rows = Some(KeyBody { body: open_body(child), columns: Arc::from([]) }),
                    ChooseStage::FromOpen => value.from = open_body(child),
                    ChooseStage::NeverOpen => value.never = never.chain([open_body(child)]).collect(),
                    ChooseStage::For | ChooseStage::Never | ChooseStage::NeverEnd => value.never = never.collect(),
                }
                value.from_inside_for = inside_for(value.rows.as_ref(), value.from.value());
                Built::Form(Form::Choose(Node::new(value)))
            }
            Frame::Rigid(rigid) => {
                let mut value = RigidDet { name: RigidDetName(slot), key: rigid.key.clone(), instance: rigid.instance.clone(), parts: Arc::from([]) };
                let parts = rigid.parts.iter().cloned();
                match (rigid.stage, child) {
                    (RigidStage::KeyOpen, child) => value.key = Some(KeyBody { body: open_body(child), columns: Arc::from([]) }),
                    (RigidStage::InstanceOpen, child) => value.instance = Some(KeyBody { body: open_body(child), columns: Arc::from([]) }),
                    (_, Some(Built::Atom { atom, .. })) => value.parts = parts.chain([atom]).collect(),
                    (_, _) => value.parts = parts.collect(),
                }
                Built::Form(Form::RigidDet(Node::new(value)))
            }
        };
        Some(built)
    }
}

/// The index, among the children of the node of `frame`, of the node of
/// `above`, the frame above it.
fn child_step(frame: &Frame, above: &Frame) -> u32 {
    let count = |count: usize| u32::try_from(count).expect("fewer than 2^32 children");
    match frame {
        Frame::Clause(_) => 0,
        Frame::Body(body) => count(body.conjuncts.len()),
        Frame::Atom(atom) => count(atom.sites.len()),
        Frame::Site(site) => count(site.args.len()),
        Frame::Or(branches) => count(branches.len()),
        Frame::Lists(lists) => count(lists.lists.len()),
        Frame::Instance(instance) => match above {
            Frame::KeyClause(_) => 0,
            _ => count(usize::from(instance.key.is_some()) + instance.inputs.len()),
        },
        Frame::KeyClause(clause) => match above {
            Frame::Input(_) => count(1 + clause.inputs.len()),
            _ => 0,
        },
        Frame::Input(input) => match above {
            Frame::HeadSite(_) => count(input.head.len()),
            _ => 0,
        },
        Frame::Choose(choose) => {
            let rows = usize::from(choose.rows.is_some());
            match choose.stage {
                ChooseStage::ForOpen => 0,
                ChooseStage::FromOpen => count(rows),
                _ => count(rows + 1 + choose.never.len()),
            }
        }
        Frame::Rigid(rigid) => {
            let key = usize::from(rigid.key.is_some());
            match rigid.stage {
                RigidStage::KeyOpen => 0,
                RigidStage::InstanceOpen => count(key),
                _ => count(key + usize::from(rigid.instance.is_some()) + rigid.parts.len()),
            }
        }
        Frame::One(_) | Frame::Constraint(_) | Frame::HeadSite(_) => unreachable!("a frame that holds no open child"),
    }
}

/// Whether `token` opens an atom.
fn is_relation(token: &Token) -> bool {
    matches!(token, Token::Lib(_) | Token::Proposer(_) | Token::Fact(_) | Token::Relation(_))
}

/// Whether `column` is a column of a type parameter, whose bare labels
/// carry a name.
fn type_parameter(column: &ColumnName) -> bool {
    matches!(column, ColumnName::Written(name) if is_type_parameter_column(name))
}

/// A bare label at a site on `column`.
fn bare_arg(column: &ColumnName, label: LabelUse) -> SiteArg {
    match (type_parameter(column), label) {
        (true, LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) => SiteArg::NamedLabel { name: ColumnName::Slot(id.0), label },
        _ => SiteArg::Label(label),
    }
}

/// The label at the field at `field` of a record at a site on `column`.
fn field_arg(column: &ColumnName, field: u32, label: LabelUse) -> SiteArg {
    match type_parameter(column) {
        true => SiteArg::NamedLabel { name: ColumnName::Slot(field), label },
        false => SiteArg::Field(Site { column: ColumnName::Slot(field), value: SiteValue { args: Arc::from([SiteArg::Label(label)]) } }),
    }
}

/// The columns of `labels`, each named by its slot, from `first`.
pub(super) fn slot_columns(labels: Vec<LabelId>, first: usize) -> Arc<[RelationColumn]> {
    let column = |(index, label)| RelationColumn { name: ColumnName::Slot(u32::try_from(first + index).expect("fewer than 2^32 columns")), label };
    labels.into_iter().enumerate().map(column).collect()
}

/// Whether a `CHOOSE` form's `from` stands inside its `for`, which is where
/// it reads a label of the rows, as `docs/arclog/constraints.md#choose`
/// gives.
fn inside_for(rows: Option<&KeyBody>, from: &Body) -> bool {
    let read = body_labels(from);
    rows.is_some_and(|rows| rows.columns.iter().any(|column| read.contains(&column.label)))
}

/// A key's body, whose columns are its `^` labels.
fn key_body(body: Node<Body>) -> KeyBody {
    KeyBody { columns: slot_columns(key_labels(body.value()), 0), body }
}

fn empty() -> Node<Body> {
    Node::new(Body { conjuncts: Arc::from([]) })
}
