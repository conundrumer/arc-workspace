//! The reader of the nodes of an arclog file from its s-expressions, and of
//! a body or an `INIT` form of the registry file.
//!
//! Each node records its layout under its path, as [`crate::layout::Layout`]
//! gives, numbered as the table of `engine/arclog/src/program/path.rs`
//! gives, and the writer of [`crate::write`] walks the nodes in the same
//! order.

use std::collections::BTreeSet;
use std::sync::Arc;

use crate::diagnostic::Diagnostic;
use crate::layout::{Layout, NodeLayout, SourceFile, SourcePlace};
use crate::program::path::NodePath;
use crate::program::*;
use crate::registry::LibName;

use super::columns::{key_labels, made_labels, relation_columns};
use super::labels::LabelScope;
use super::spelling::{self as sp, parse};
use super::{grammar, SExpr};

/// A node the reader leaves out, whose diagnostic it has given.
pub(super) struct Refused;

pub(super) type R<T> = Result<T, Refused>;

/// The names of the `INIT` and `RIGID_DET` forms of a file, whose outputs a
/// read `&x.y` names.
#[derive(Default)]
pub(super) struct Owners {
    instances: BTreeSet<Box<str>>,
    rigid: BTreeSet<Box<str>>,
}

impl Owners {
    pub(super) fn collect(&mut self, expr: &SExpr) {
        let SExpr::List { items, .. } = expr else { return };
        if let [SExpr::Symbol { text: head, .. }, SExpr::Symbol { text: name, .. }, ..] = &items[..] {
            match &**head {
                sp::INIT => {
                    self.instances.insert(name.clone());
                }
                sp::RIGID_DET => {
                    self.rigid.insert(name.clone());
                }
                _ => {}
            }
        }
        for item in items.iter() {
            self.collect(item);
        }
    }

    /// The owners that the forms of `programs` declare, at any depth.
    pub(super) fn of_programs(programs: &[&Program]) -> Self {
        let mut owners = Owners::default();
        for program in programs {
            owners.forms(&program.forms);
        }
        owners
    }

    fn forms(&mut self, forms: &[Form]) {
        for form in forms {
            match form {
                Form::Claim(claim) => self.forms(&claim.value().forms),
                Form::Instance(instance) => self.insert_written(&instance.value().name.0, false),
                Form::RigidDet(rigid) => self.insert_written(&rigid.value().name.0, true),
                Form::Demonstrated(demonstrated) => {
                    for rule in demonstrated.value().rules.iter() {
                        self.forms(&rule.value().forms);
                    }
                }
                Form::Alts(alts) => {
                    for alt in alts.value().alts.iter() {
                        self.alt(alt.value());
                    }
                }
                Form::Clause(_) | Form::Choose(_) => {}
            }
        }
    }

    fn alt(&mut self, alt: &Alt) {
        for item in alt.items.iter() {
            match item {
                AltItem::Form(form) => self.forms(std::slice::from_ref(form)),
                AltItem::Alt(nested) => self.alt(nested.value()),
            }
        }
    }

    fn insert_written(&mut self, name: &DeclaredName, rigid: bool) {
        let DeclaredName::Written(text) = name else {
            panic!("a program read from a file writes each name, and a slot is a decode's")
        };
        let set = if rigid { &mut self.rigid } else { &mut self.instances };
        set.insert(text.clone());
    }
}

/// The layout a node records as it is read.
pub(super) struct Record {
    place: Option<SourcePlace>,
    tokens: Vec<SourcePlace>,
    elided: Vec<u32>,
    labels: Box<[(LabelId, Box<str>)]>,
}

impl Record {
    pub(super) fn new(place: Option<SourcePlace>) -> Self {
        Record { place, tokens: Vec::new(), elided: Vec::new(), labels: Box::new([]) }
    }

    pub(super) fn token(&mut self, place: SourcePlace) {
        self.tokens.push(place);
    }
}

/// The place of the `(` of a list whose place is `place`.
pub(super) fn open_of(place: SourcePlace) -> SourcePlace {
    SourcePlace { end: place.start + 1, ..place }
}

/// A list's items, its place, and the places of its parentheses.
pub(super) struct List<'e> {
    pub(super) items: &'e [SExpr],
    pub(super) place: SourcePlace,
    pub(super) open: SourcePlace,
    pub(super) close: SourcePlace,
}

/// The head symbol of `expr`, where it is a list headed by a symbol.
pub(crate) fn head_of(expr: &SExpr) -> Option<&str> {
    match expr {
        SExpr::List { items, .. } => match items.first() {
            Some(SExpr::Symbol { text, .. }) => Some(text),
            _ => None,
        },
        _ => None,
    }
}

fn is_demo_rule(expr: &SExpr) -> bool {
    head_of(expr) == Some(sp::DEMO_RULE)
}

fn never_skip(_: &SExpr) -> bool {
    false
}

pub(super) fn is_name(text: &str) -> bool {
    let mut chars = text.chars();
    chars.next().is_some_and(|c| c.is_ascii_alphabetic()) && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// The name of a bare label, its mark left out: `P` of `*P`.
fn label_name(text: &str) -> ColumnName {
    ColumnName::Written(text.trim_start_matches([sp::FRESH_MARK, sp::KEY_MARK]).into())
}

/// Whether `column`, a site's column as the file writes it, is a type
/// parameter's, which is lowercase (`docs/arclog/arclog.md#sites`).
fn is_type_parameter_column(column: &str) -> bool {
    column.starts_with(|c: char| c.is_ascii_lowercase())
}

pub(super) struct Reader {
    owners: Owners,
    /// Whether a read `(self.<port> ...)` stands, as in a definition of the
    /// registry file.
    defined_ports: bool,
    pub(super) diagnostics: Vec<Diagnostic>,
    nodes: Vec<(NodePath, NodeLayout)>,
}

impl Reader {
    pub(super) fn new(exprs: &[SExpr], defined_ports: bool) -> Self {
        let mut owners = Owners::default();
        for expr in exprs {
            owners.collect(expr);
        }
        Reader::with_owners(owners, defined_ports)
    }

    /// A reader whose read `&x.y` names the outputs of `owners`.
    pub(super) fn with_owners(owners: Owners, defined_ports: bool) -> Self {
        Reader { owners, defined_ports, diagnostics: Vec::new(), nodes: Vec::new() }
    }

    /// The layout of the nodes read, as nodes of `file`.
    pub(super) fn layout(self, file: SourceFile, comments: Vec<crate::layout::Comment>) -> Layout {
        Layout { nodes: self.nodes.into_iter().map(|(path, node)| ((file, path), node)).collect(), comments: comments.into() }
    }

    pub(super) fn refuse<T>(&mut self, message: impl Into<Box<str>>, place: SourcePlace) -> R<T> {
        self.diagnostics.push(grammar(message, place));
        Err(Refused)
    }

    pub(super) fn save(&mut self, path: &NodePath, record: Record) {
        let Record { place, tokens, elided, labels } = record;
        self.nodes.push((
            path.clone(),
            NodeLayout { place, tokens: tokens.into(), label_names: labels, elided_sites: elided.into() },
        ));
    }

    /// Reads one node of a list of nodes that the reader may leave out: the
    /// layout it recorded goes with it.
    pub(super) fn optional<T>(&mut self, read: impl FnOnce(&mut Self) -> R<T>) -> Option<T> {
        let mark = self.nodes.len();
        let value = read(self).ok();
        if value.is_none() {
            self.nodes.truncate(mark);
        }
        value
    }

    pub(super) fn list<'e>(&mut self, expr: &'e SExpr, what: &str) -> R<List<'e>> {
        match expr {
            SExpr::List { items, place, close } => Ok(List { items, place: *place, open: open_of(*place), close: *close }),
            other => self.refuse(format!("{what} is a list"), other.place()),
        }
    }

    pub(super) fn symbol<'e>(&mut self, expr: Option<&'e SExpr>, what: &str, at: SourcePlace) -> R<(&'e str, SourcePlace)> {
        match expr {
            Some(SExpr::Symbol { text, place }) => Ok((text, *place)),
            Some(other) => self.refuse(format!("{what} is a symbol"), other.place()),
            None => self.refuse(format!("the list lacks {what}"), at),
        }
    }

    pub(super) fn string<'e>(&mut self, expr: Option<&'e SExpr>, what: &str, at: SourcePlace) -> R<(&'e str, SourcePlace)> {
        match expr {
            Some(SExpr::String { text, place }) => Ok((text, *place)),
            Some(other) => self.refuse(format!("{what} is a string"), other.place()),
            None => self.refuse(format!("the list lacks {what}"), at),
        }
    }

    fn declared(&mut self, text: &str, place: SourcePlace) -> R<DeclaredName> {
        match text.strip_prefix(sp::DECLARED_MARK) {
            Some(name) if is_name(name) => Ok(DeclaredName::Written(text.into())),
            _ => self.refuse(format!("`{text}` is not a declared name, `&` and a name"), place),
        }
    }

    fn output(&mut self, text: &str, place: SourcePlace) -> R<OutputName> {
        let mut parts = text.split('.');
        let owner = parts.next().expect("a split gives at least one part");
        let steps: Vec<&str> = parts.collect();
        let declared = self.declared(owner, place)?;
        if steps.iter().any(|s| !is_name(s)) {
            return self.refuse(format!("`{text}` has a step that is not a name"), place);
        }
        let instance = self.owners.instances.contains(owner);
        let rigid = self.owners.rigid.contains(owner);
        match (instance, rigid, &steps[..]) {
            (true, false, [port]) => Ok(OutputName {
                of: OutputOwner::Instance(InstanceName(declared)),
                path: Arc::new([OutputStep::Port(PortName((*port).into()))]),
            }),
            (false, true, [step, rest @ ..]) if rest.len() <= 1 && !(*step == sp::POSE && !rest.is_empty()) => {
                let first = if *step == sp::POSE {
                    OutputStep::Pose
                } else {
                    OutputStep::Part(DeclaredName::Written(format!("{}{step}", sp::DECLARED_MARK).into()))
                };
                let path = std::iter::once(first).chain(rest.iter().map(|p| OutputStep::Port(PortName((*p).into())))).collect();
                Ok(OutputName { of: OutputOwner::RigidDet(RigidDetName(declared)), path })
            }
            (false, false, _) => self.refuse(format!("`{owner}` of `{text}` names no `INIT` or `RIGID_DET` form of the file"), place),
            (true, true, _) => self.refuse(format!("`{owner}` names both an `INIT` and a `RIGID_DET` form"), place),
            _ => self.refuse(format!("`{text}` is not a path the outputs of `{owner}` have"), place),
        }
    }

    pub(super) fn program_relation(&mut self, text: &str, place: SourcePlace) -> R<ProgramRelation> {
        if text.contains('.') {
            Ok(ProgramRelation::Output(self.output(text, place)?))
        } else {
            Ok(ProgramRelation::Declared(RelationName(self.declared(text, place)?)))
        }
    }

    fn relation_ref(&mut self, text: &str, place: SourcePlace) -> R<RelationRef> {
        if let Some(fact) = parse(sp::FACT_RELATIONS, text) {
            return Ok(RelationRef::Fact(fact));
        }
        if text.starts_with(sp::DECLARED_MARK) {
            return Ok(match self.program_relation(text, place)? {
                ProgramRelation::Declared(name) => RelationRef::Declared(name),
                ProgramRelation::Output(name) => RelationRef::Output(name),
            });
        }
        if let Some(port) = text.strip_prefix(sp::SELF_PREFIX).filter(|_| self.defined_ports) {
            return Ok(RelationRef::DefinedPort(PortName(port.into())));
        }
        if is_name(text) {
            return Ok(RelationRef::Lib(LibName(text.into())));
        }
        self.refuse(format!("`{text}` names no relation"), place)
    }

    fn label(&mut self, text: &str, place: SourcePlace, scope: &LabelScope) -> R<LabelUse> {
        if text == sp::ZERO {
            return Ok(LabelUse::Zero);
        }
        if let Some(name) = text.strip_prefix(sp::FRESH_MARK) {
            if !is_name(name) {
                return self.refuse(format!("`{text}` is not a label"), place);
            }
            return Ok(LabelUse::Fresh(scope.made(place)));
        }
        if let Some(name) = text.strip_prefix(sp::KEY_MARK) {
            if !is_name(name) {
                return self.refuse(format!("`{text}` is not a label"), place);
            }
            return Ok(LabelUse::Key(scope.made(place)));
        }
        if !is_name(text) {
            return self.refuse(format!("`{text}` is not a label"), place);
        }
        match scope.joined(text, place) {
            Some(id) => Ok(LabelUse::Join(id)),
            None => self.refuse(format!("`{text}` joins a label that no site of its form makes"), place),
        }
    }

    // Forms.

    pub(super) fn program(&mut self, exprs: &[SExpr], end: SourcePlace) -> Node<Program> {
        let root = NodePath::default();
        let forms = self.forms(exprs, &root, 0, None);
        let mut record = Record::new(None);
        record.token(end);
        self.save(&root, record);
        Node::new(Program { forms: forms.into() })
    }

    /// The forms of `exprs`, each at its index after `first` among the
    /// children of `parent`, leaving out each that matches no form.
    fn forms(&mut self, exprs: &[SExpr], parent: &NodePath, first: u32, scope: Option<&LabelScope>) -> Vec<Form> {
        let mut forms = Vec::new();
        for expr in exprs {
            let path = parent.child(first + forms.len() as u32);
            if let Some(form) = self.optional(|r| r.form(expr, &path, scope)) {
                forms.push(form);
            }
        }
        forms
    }

    /// A form, in `scope` where it stands inside a `DEMO_RULE` form, and in
    /// a scope of its own otherwise.
    pub(super) fn form(&mut self, expr: &SExpr, path: &NodePath, scope: Option<&LabelScope>) -> R<Form> {
        let list = self.list(expr, "a form")?;
        let (head, head_place) = self.symbol(list.items.first(), "a form's keyword", list.place)?;
        if parse(sp::CLAIM_KINDS, head).is_some() {
            return Ok(Form::Claim(self.claim(&list, path)?));
        }
        if head == sp::ALTS {
            return Ok(Form::Alts(self.alts(&list, path)?));
        }
        let own = match scope {
            Some(_) => None,
            None => {
                let skip: &dyn Fn(&SExpr) -> bool = if head == sp::DEMONSTRATED { &is_demo_rule } else { &never_skip };
                Some(LabelScope::new(std::slice::from_ref(expr), skip))
            }
        };
        let scope = scope.or(own.as_ref()).expect("a form has its scope or its own");
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(head_place);
        let form = if parse(sp::CLAUSE_KEYWORDS, head).is_some() {
            Form::Clause(self.clause(&list, path, scope, &mut record)?)
        } else {
            match head {
                sp::INIT => Form::Instance(self.instance(&list, path, scope, &mut record)?),
                sp::CHOOSE => Form::Choose(self.choose(&list, path, scope, &mut record)?),
                sp::RIGID_DET => Form::RigidDet(self.rigid_det(&list, path, scope, &mut record)?),
                sp::DEMONSTRATED => Form::Demonstrated(self.demonstrated(&list, path, scope, &mut record)?),
                _ => return self.refuse(format!("`{head}` heads no form"), head_place),
            }
        };
        record.token(list.close);
        if let Some(own) = &own {
            record.labels = own.names();
        }
        self.save(path, record);
        Ok(form)
    }

    fn claim(&mut self, list: &List, path: &NodePath) -> R<Node<Claim>> {
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        let (head, head_place) = self.symbol(list.items.first(), "a claim's keyword", list.place)?;
        let kind = parse(sp::CLAIM_KINDS, head).expect("the caller read a claim's keyword");
        record.token(head_place);
        let (slug, place) = self.symbol(list.items.get(1), "a claim's slug", list.place)?;
        record.token(place);
        let (text, place) = self.string(list.items.get(2), "a claim's text", list.place)?;
        record.token(place);
        let mut rest = &list.items[3..];
        let mut approximated = None;
        if let Some(first) = rest.first().filter(|e| head_of(e) == Some(sp::APPROXIMATED)) {
            let inner = self.list(first, "an `APPROXIMATED` form")?;
            record.token(inner.open);
            record.token(inner.items[0].place());
            let (rule, place) = self.string(inner.items.get(1), "the approximation's rule", inner.place)?;
            record.token(place);
            if let Some(extra) = inner.items.get(2) {
                return self.refuse("an `APPROXIMATED` form holds one string", extra.place());
            }
            record.token(inner.close);
            approximated = Some(Text(rule.into()));
            rest = &rest[1..];
        }
        let forms = self.forms(rest, path, 0, None);
        record.token(list.close);
        self.save(path, record);
        Ok(Node::new(Claim { kind, slug: Slug(slug.into()), text: Text(text.into()), approximated, forms: forms.into() }))
    }

    pub(super) fn dollar_name(&mut self, expr: Option<&SExpr>, what: &str, at: SourcePlace, record: &mut Record) -> R<Box<str>> {
        let (text, place) = self.symbol(expr, what, at)?;
        if !text.strip_prefix('$').is_some_and(is_name) {
            return self.refuse(format!("{what} is `$` and a name"), place);
        }
        record.token(place);
        Ok(text.into())
    }

    fn alts(&mut self, list: &List, path: &NodePath) -> R<Node<Alts>> {
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(list.items[0].place());
        let name = self.dollar_name(list.items.get(1), "an `ALTS` form's name", list.place, &mut record)?;
        let (gloss, place) = self.string(list.items.get(2), "an `ALTS` form's gloss", list.place)?;
        record.token(place);
        let concept = self.dollar_name(list.items.get(3), "the concept case's name", list.place, &mut record)?;
        let mut alts = Vec::new();
        for expr in list.items.iter().skip(4) {
            if head_of(expr) != Some(sp::ALT) {
                return self.refuse("an `ALTS` form holds `ALT` blocks after its names", expr.place());
            }
            let path = path.child(alts.len() as u32);
            alts.push(self.alt(expr, &path)?);
        }
        record.token(list.close);
        self.save(path, record);
        Ok(Node::new(Alts { name: AltsName(name), gloss: Text(gloss.into()), concept: AltsName(concept), alts: alts.into() }))
    }

    fn alt(&mut self, expr: &SExpr, path: &NodePath) -> R<Node<Alt>> {
        let list = self.list(expr, "an `ALT` block")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(list.items[0].place());
        let name = self.dollar_name(list.items.get(1), "an alt's name", list.place, &mut record)?;
        let mut items = Vec::new();
        for expr in list.items.iter().skip(2) {
            let child = path.child(items.len() as u32);
            if head_of(expr) == Some(sp::ALT) {
                items.push(AltItem::Alt(self.alt(expr, &child)?));
            } else if let Some(form) = self.optional(|r| r.form(expr, &child, None)) {
                items.push(AltItem::Form(form));
            }
        }
        record.token(list.close);
        self.save(path, record);
        Ok(Node::new(Alt { name: AltsName(name), items: items.into() }))
    }

    fn clause(&mut self, list: &List, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Node<Clause>> {
        let (head, _) = self.symbol(list.items.first(), "a clause's keyword", list.place)?;
        let keyword = parse(sp::CLAUSE_KEYWORDS, head).expect("the caller read a clause's keyword");
        let (name, place) = self.symbol(list.items.get(1), "the relation's name", list.place)?;
        let derives = self.program_relation(name, place)?;
        record.token(place);
        let mut rest = &list.items[2..];
        let mut gloss = None;
        if let Some(SExpr::String { text, place }) = rest.first() {
            gloss = Some(Text(text.clone()));
            record.token(*place);
            rest = &rest[1..];
        }
        let mut proposers = Vec::new();
        while let Some(SExpr::Symbol { text, place }) = rest.first() {
            if !is_name(text) {
                return self.refuse(format!("`{text}` is not a proposer's name"), *place);
            }
            proposers.push(LibName(text.clone()));
            record.token(*place);
            rest = &rest[1..];
        }
        let marks_at = rest.iter().position(|e| head_of(e) == Some(sp::ONE)).unwrap_or(rest.len());
        let (conjuncts, marks) = rest.split_at(marks_at);
        let body = self.conjuncts(conjuncts, &path.child(0), scope, Record::new(None), None);
        let mut ones = Vec::new();
        for expr in marks {
            if head_of(expr) != Some(sp::ONE) {
                return self.refuse("a clause's `ONE` marks stand after its body", expr.place());
            }
            let mark = self.list(expr, "a `ONE` mark")?;
            record.token(mark.open);
            record.token(mark.items[0].place());
            let mut key = Vec::new();
            for item in &mark.items[1..] {
                let (text, place) = self.symbol(Some(item), "a `ONE` mark's label", mark.place)?;
                match self.label(text, place, scope)? {
                    LabelUse::Join(id) => key.push(id),
                    _ => return self.refuse("a `ONE` mark's label joins", place),
                }
                record.token(place);
            }
            record.token(mark.close);
            ones.push(OneMark { key: key.into() });
        }
        let columns = relation_columns(&made_labels(body.value()), scope);
        Ok(Node::new(Clause {
            keyword,
            derives,
            gloss,
            proposers: proposers.into(),
            body,
            ones: ones.into(),
            columns,
        }))
    }

    /// The body of the conjuncts `exprs`, at `path`, with `record` as its
    /// layout, and `close` the place of its `)` where the body is a list of
    /// its own.
    fn conjuncts(
        &mut self,
        exprs: &[SExpr],
        path: &NodePath,
        scope: &LabelScope,
        mut record: Record,
        close: Option<SourcePlace>,
    ) -> Node<Body> {
        let mut conjuncts = Vec::new();
        for expr in exprs {
            let child = path.child(conjuncts.len() as u32);
            if let Some(conjunct) = self.optional(|r| r.conjunct(expr, &child, scope)) {
                conjuncts.push(conjunct);
            }
        }
        record.tokens.extend(close);
        self.save(path, record);
        Node::new(Body { conjuncts: conjuncts.into() })
    }

    /// A body written as one list of conjuncts, as a branch of an `OR` is.
    fn body_list(&mut self, expr: Option<&SExpr>, path: &NodePath, scope: &LabelScope, at: SourcePlace) -> R<Node<Body>> {
        let Some(expr) = expr else { return self.refuse("the list lacks a body", at) };
        let list = self.list(expr, "a body")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        Ok(self.conjuncts(list.items, path, scope, record, Some(list.close)))
    }

    fn conjunct(&mut self, expr: &SExpr, path: &NodePath, scope: &LabelScope) -> R<Conjunct> {
        let list = self.list(expr, "a conjunct")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        let (head, head_place) = self.symbol(list.items.first(), "a conjunct's head", list.place)?;
        let arity = |n: usize| list.items.len() == n + 1;
        let conjunct = if head == sp::NOT {
            record.token(head_place);
            if !arity(1) {
                return self.refuse("`NOT` holds one atom or form", list.place);
            }
            let inner = &list.items[1];
            if matches!(head_of(inner), Some(sp::NOT | sp::OR | sp::IF | sp::ALL)) {
                Conjunct::Not(Negated::Form(Arc::new(self.conjunct(inner, &path.child(0), scope)?)))
            } else {
                let atom = self.list(inner, "a negated atom")?;
                record.token(atom.open);
                let value = self.atom(&atom, path, scope, &mut record)?;
                record.token(atom.close);
                Conjunct::Not(Negated::Atom(Node::new(value)))
            }
        } else if head == sp::OR {
            record.token(head_place);
            let mut branches = Vec::new();
            for (index, branch) in list.items[1..].iter().enumerate() {
                branches.push(self.body_list(Some(branch), &path.child(index as u32), scope, list.place)?);
            }
            if branches.is_empty() {
                return self.refuse("an `OR` holds its branches", list.place);
            }
            Conjunct::Or(branches.into())
        } else if head == sp::IF {
            record.token(head_place);
            if !arity(3) {
                return self.refuse("an `IF` holds a test, a then and an else", list.place);
            }
            let test = self.body_list(list.items.get(1), &path.child(0), scope, list.place)?;
            let then = self.body_list(list.items.get(2), &path.child(1), scope, list.place)?;
            let otherwise = self.body_list(list.items.get(3), &path.child(2), scope, list.place)?;
            Conjunct::If { test, then, otherwise }
        } else if head == sp::ALL {
            record.token(head_place);
            if !arity(2) {
                return self.refuse("an `ALL` holds a domain and a body", list.place);
            }
            let domain = self.body_list(list.items.get(1), &path.child(0), scope, list.place)?;
            let body = self.body_list(list.items.get(2), &path.child(1), scope, list.place)?;
            Conjunct::All { domain, body }
        } else if let Some(op) = parse(sp::CONSTRAINT_OPS, head) {
            record.token(head_place);
            if !arity(2) {
                return self.refuse("a constraint holds two labels", list.place);
            }
            let (text, place) = self.symbol(list.items.get(1), "a constraint's label", list.place)?;
            let Ok(first) = ConstraintLabel::try_from(self.label(text, place, scope)?) else {
                return self.refuse("a constraint's first label is a label, made or joined", place);
            };
            record.token(place);
            let (text, place) = self.symbol(list.items.get(2), "a constraint's label", list.place)?;
            let second = match ConstraintLabel::try_from(self.label(text, place, scope)?) {
                Ok(label) => Operand::Label(label),
                Err(LabelUse::Zero) => Operand::Zero,
                Err(_) => return self.refuse("a constraint takes no `^` label", place),
            };
            record.token(place);
            Conjunct::Constraint(Constraint { op, first, second })
        } else {
            Conjunct::Atom(Node::new(self.atom(&list, path, scope, &mut record)?))
        };
        record.token(list.close);
        self.save(path, record);
        Ok(conjunct)
    }

    /// The atom of `list`, its relation and its sites, the sites as the
    /// children of `path`, with its tokens in `record`.
    fn atom(&mut self, list: &List, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Atom> {
        let (name, place) = self.symbol(list.items.first(), "an atom's relation", list.place)?;
        let relation = self.relation_ref(name, place)?;
        record.token(place);
        let sites = self.sites(&list.items[1..], path, scope, record, false);
        Ok(Atom { relation, sites })
    }

    /// The sites of `exprs`, an input's head sites where `head_site` holds.
    fn sites(&mut self, exprs: &[SExpr], path: &NodePath, scope: &LabelScope, record: &mut Record, head_site: bool) -> Arc<[Site]> {
        let mut sites = Vec::new();
        for expr in exprs {
            let index = sites.len() as u32;
            if let Some((site, elided)) = self.optional(|r| r.site(expr, &path.child(index), scope, head_site)) {
                if elided {
                    record.elided.push(index);
                }
                sites.push(site);
            }
        }
        sites.into()
    }

    /// A site, and whether the file writes it as the bare label.
    fn site(&mut self, expr: &SExpr, path: &NodePath, scope: &LabelScope, head_site: bool) -> R<(Site, bool)> {
        let mut record = Record::new(Some(expr.place()));
        let (site, elided) = match expr {
            SExpr::Symbol { text, place } => {
                let label = self.site_label(text, *place, scope, head_site)?;
                if label == LabelUse::Zero {
                    return self.refuse("`0` stands at a site only after the column's name", *place);
                }
                record.token(*place);
                let column = label_name(text);
                (Site { column, value: SiteValue { args: Arc::new([SiteArg::Label(label)]) } }, true)
            }
            _ => {
                let list = self.list(expr, "a site")?;
                record.token(list.open);
                let (head, place) = self.symbol(list.items.first(), "a site's column", list.place)?;
                let Some(column) = head.strip_prefix(sp::COLUMN_MARK).filter(|c| is_name(c)) else {
                    return self.refuse(format!("`{head}` is not a column, `:` and a name"), place);
                };
                record.token(place);
                let named = is_type_parameter_column(column);
                let mut args = Vec::new();
                for item in &list.items[1..] {
                    match item {
                        SExpr::Symbol { text, place } => {
                            let label = self.site_label(text, *place, scope, head_site)?;
                            args.push(match label {
                                LabelUse::Zero => SiteArg::Label(label),
                                _ if named => SiteArg::NamedLabel { name: label_name(text), label },
                                _ => SiteArg::Label(label),
                            });
                            record.token(*place);
                        }
                        _ => {
                            let index = args.len() as u32;
                            if let Some((field, _)) = self.optional(|r| r.site(item, &path.child(index), scope, head_site)) {
                                args.push(SiteArg::Field(field));
                            }
                        }
                    }
                }
                if args.is_empty() {
                    return self.refuse("a site holds a label or a field site", list.place);
                }
                record.token(list.close);
                (Site { column: ColumnName::Written(column.into()), value: SiteValue { args: args.into() } }, false)
            }
        };
        self.save(path, record);
        Ok((site, elided))
    }

    /// The label of a site, which at an input's head site joins a label
    /// the body or the key makes (`docs/arclog/arclog.md#instance`).
    fn site_label(&mut self, text: &str, place: SourcePlace, scope: &LabelScope, head_site: bool) -> R<LabelUse> {
        let label = self.label(text, place, scope)?;
        match label {
            LabelUse::Fresh(_) if head_site => self.refuse("a head site carries no `*`: the body or the key makes its label", place),
            LabelUse::Zero if head_site => self.refuse("a head site holds no `0`: the body makes its label with `(= *X 0)`", place),
            LabelUse::Key(_) if head_site => self.refuse("a head site carries no `^`: the body or the key makes its label", place),
            _ => Ok(label),
        }
    }

    fn input(&mut self, expr: &SExpr, path: &NodePath, scope: &LabelScope) -> R<Node<InstanceInput>> {
        let list = self.list(expr, "an input")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        let (name, place) = self.symbol(list.items.first(), "an input's name", list.place)?;
        if !is_name(name) {
            return self.refuse(format!("`{name}` is not an input's name"), place);
        }
        record.token(place);
        let Some(head_expr) = list.items.get(1) else { return self.refuse("an input holds its head sites", list.place) };
        let head = self.list(head_expr, "an input's head")?;
        record.token(head.open);
        let sites = self.sites(head.items, path, scope, &mut record, true);
        record.token(head.close);
        let body = self.conjuncts(&list.items[2..], &path.child(sites.len() as u32), scope, Record::new(None), None);
        record.token(list.close);
        self.save(path, record);
        Ok(Node::new(InstanceInput { name: PortName(name.into()), head: sites, body }))
    }

    fn key_body(&mut self, expr: Option<&SExpr>, path: &NodePath, scope: &LabelScope, at: SourcePlace) -> R<KeyBody> {
        let body = self.body_list(expr, path, scope, at)?;
        let columns = relation_columns(&key_labels(body.value()), scope);
        Ok(KeyBody { body, columns })
    }

    fn key_clause(&mut self, list: &List, path: &NodePath, scope: &LabelScope) -> R<Node<KeyClause>> {
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(list.items[0].place());
        let key = self.key_body(list.items.get(1), &path.child(0), scope, list.place)?;
        let mut inputs = Vec::new();
        for expr in list.items.iter().skip(2) {
            let child = path.child(1 + inputs.len() as u32);
            inputs.push(self.input(expr, &child, scope)?);
        }
        record.token(list.close);
        self.save(path, record);
        Ok(Node::new(KeyClause { key, inputs: inputs.into() }))
    }

    /// The key clause that `rest` opens with, if it opens with one, at
    /// `path`, and the rest after it.
    fn leading_key<'e>(&mut self, rest: &'e [SExpr], path: &NodePath, scope: &LabelScope) -> R<(Option<Node<KeyClause>>, &'e [SExpr])> {
        match rest.first().filter(|e| head_of(e) == Some(sp::KEY)) {
            Some(expr) => {
                let list = self.list(expr, "a key clause")?;
                Ok((Some(self.key_clause(&list, path, scope)?), &rest[1..]))
            }
            None => Ok((None, rest)),
        }
    }

    fn instance(&mut self, list: &List, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Node<Instance>> {
        let (name, place) = self.symbol(list.items.get(1), "an instance's name", list.place)?;
        let name = InstanceName(self.declared(name, place)?);
        record.token(place);
        let (component, place) = self.symbol(list.items.get(2), "an instance's component", list.place)?;
        if !is_name(component) {
            return self.refuse(format!("`{component}` is not a component's name"), place);
        }
        record.token(place);
        let (key, rest) = self.leading_key(&list.items[3..], &path.child(0), scope)?;
        let first = u32::from(key.is_some());
        let mut inputs = Vec::new();
        for expr in rest {
            let child = path.child(first + inputs.len() as u32);
            inputs.push(self.input(expr, &child, scope)?);
        }
        Ok(Node::new(Instance { name, component: LibName(component.into()), key, inputs: inputs.into() }))
    }

    fn choose(&mut self, list: &List, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Node<Choose>> {
        let (name, place) = self.symbol(list.items.get(1), "a `CHOOSE` form's name", list.place)?;
        let name = RelationName(self.declared(name, place)?);
        record.token(place);
        let mut rest = &list.items[2..];
        let mut next = 0;
        let mut rows = None;
        let mut from = None;
        let mut from_inside_for = false;
        if let Some(expr) = rest.first().filter(|e| head_of(e) == Some(sp::FOR)) {
            let clause = self.list(expr, "a `for` clause")?;
            record.token(clause.open);
            record.token(clause.items[0].place());
            rows = Some(self.key_body(clause.items.get(1), &path.child(next), scope, clause.place)?);
            next += 1;
            match &clause.items[2..] {
                [] => {}
                [inner] if head_of(inner) == Some(sp::FROM) => {
                    from = Some(self.choose_from(inner, &path.child(next), scope, record)?);
                    from_inside_for = true;
                    next += 1;
                }
                [extra, ..] => return self.refuse("a `for` clause holds its body, then its `from` clause", extra.place()),
            }
            record.token(clause.close);
            rest = &rest[1..];
        }
        if from.is_none() {
            match rest.first().filter(|e| head_of(e) == Some(sp::FROM)) {
                Some(expr) => {
                    from = Some(self.choose_from(expr, &path.child(next), scope, record)?);
                    next += 1;
                    rest = &rest[1..];
                }
                None => return self.refuse("a `CHOOSE` form holds a `from` clause", list.place),
            }
        }
        let from = from.expect("the `from` clause was read");
        let mut never = Vec::new();
        for expr in rest {
            if head_of(expr) != Some(sp::NEVER) {
                return self.refuse("a `CHOOSE` form ends in its `never` clauses", expr.place());
            }
            let clause = self.list(expr, "a `never` clause")?;
            record.token(clause.open);
            record.token(clause.items[0].place());
            never.push(self.conjuncts(&clause.items[1..], &path.child(next), scope, Record::new(None), None));
            next += 1;
            record.token(clause.close);
        }
        let candidate_columns = relation_columns(&made_labels(from.value()), scope);
        Ok(Node::new(Choose { name, rows, candidate_columns, from, from_inside_for, never: never.into() }))
    }

    fn choose_from(&mut self, expr: &SExpr, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Node<Body>> {
        let clause = self.list(expr, "a `from` clause")?;
        record.token(clause.open);
        record.token(clause.items[0].place());
        let body = self.conjuncts(&clause.items[1..], path, scope, Record::new(None), None);
        record.token(clause.close);
        Ok(body)
    }

    fn rigid_det(&mut self, list: &List, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Node<RigidDet>> {
        let (name, place) = self.symbol(list.items.get(1), "a `RIGID_DET` form's name", list.place)?;
        let name = RigidDetName(self.declared(name, place)?);
        record.token(place);
        let mut next = 0;
        let mut closes = Vec::new();
        let mut rest = &list.items[2..];
        let mut key = None;
        let mut instance = None;
        for (head, clause) in [(sp::KEY, &mut key), (sp::INSTANCE, &mut instance)] {
            let [expr] = rest else { continue };
            if head_of(expr) != Some(head) {
                continue;
            }
            let inner = self.list(expr, "a clause of a `RIGID_DET` form")?;
            record.token(inner.open);
            record.token(inner.items[0].place());
            *clause = Some(self.key_body(inner.items.get(1), &path.child(next), scope, inner.place)?);
            next += 1;
            closes.push(inner.close);
            rest = inner.items.get(2..).unwrap_or_default();
        }
        let mut parts = Vec::new();
        for expr in rest {
            let atom = self.list(expr, "a part")?;
            let child = path.child(next + parts.len() as u32);
            let mut part = Record::new(Some(atom.place));
            part.token(atom.open);
            let value = self.atom(&atom, &child, scope, &mut part)?;
            part.token(atom.close);
            self.save(&child, part);
            parts.push(Node::new(value));
        }
        for close in closes.into_iter().rev() {
            record.token(close);
        }
        Ok(Node::new(RigidDet { name, key, instance, parts: parts.into() }))
    }

    fn demonstrated(&mut self, list: &List, path: &NodePath, scope: &LabelScope, record: &mut Record) -> R<Node<Demonstrated>> {
        let (name, place) = self.symbol(list.items.get(1), "a `DEMONSTRATED` form's name", list.place)?;
        let name = RelationName(self.declared(name, place)?);
        record.token(place);
        let (key, rest) = self.leading_key(&list.items[2..], &path.child(0), scope)?;
        let mut next = u32::from(key.is_some());
        let mut inputs = Vec::new();
        let mut rules = Vec::new();
        for expr in rest {
            if is_demo_rule(expr) {
                rules.push(self.demo_rule(expr, &path.child(next))?);
            } else if rules.is_empty() {
                inputs.push(self.input(expr, &path.child(next), scope)?);
            } else {
                return self.refuse("a `DEMONSTRATED` form's inputs stand before its `DEMO_RULE` forms", expr.place());
            }
            next += 1;
        }
        Ok(Node::new(Demonstrated { name, key, inputs: inputs.into(), rules: rules.into() }))
    }

    fn demo_rule(&mut self, expr: &SExpr, path: &NodePath) -> R<Node<DemoRule>> {
        let scope = LabelScope::new(std::slice::from_ref(expr), &never_skip);
        let list = self.list(expr, "a `DEMO_RULE` form")?;
        let mut record = Record::new(Some(list.place));
        record.token(list.open);
        record.token(list.items[0].place());
        let mut fields = Vec::new();
        let name = match list.items.get(1) {
            Some(head @ SExpr::List { .. }) => {
                let head = self.list(head, "a demonstrated rule's name and fields")?;
                if head.items.len() == 1 {
                    return self.refuse("a demonstrated rule with no field is named by its bare name", head.place);
                }
                record.token(head.open);
                let name = self.dollar_name(head.items.first(), "a demonstrated rule's name", head.place, &mut record)?;
                for item in &head.items[1..] {
                    let (text, place) = self.symbol(Some(item), "a field's label", head.place)?;
                    match self.label(text, place, &scope)? {
                        LabelUse::Fresh(id) => fields.push(id),
                        _ => return self.refuse("a field of a demonstrated rule is a made label, `*` and a name", place),
                    }
                    record.token(place);
                }
                record.token(head.close);
                name
            }
            other => self.dollar_name(other, "a demonstrated rule's name", list.place, &mut record)?,
        };
        let mut rest = &list.items[2..];
        let mut text = None;
        if let Some(SExpr::String { text: t, place }) = rest.first() {
            text = Some(Text(t.clone()));
            record.token(*place);
            rest = &rest[1..];
        }
        let forms = self.forms(rest, path, 0, Some(&scope));
        record.token(list.close);
        record.labels = scope.names();
        self.save(path, record);
        Ok(Node::new(DemoRule { name: DemoRuleName(name), fields: relation_columns(&fields, &scope), text, forms: forms.into() }))
    }

    /// The body of a registry definition, `exprs`, read in `scope`.
    pub(super) fn body(&mut self, exprs: &[SExpr], scope: &LabelScope) -> Node<Body> {
        self.conjuncts(exprs, &NodePath::default(), scope, Record::new(None), None)
    }
}

