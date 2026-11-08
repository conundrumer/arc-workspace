//! A feature expression as a term of the grammar of
//! `docs/feature-spec/feature-spec.md#the-generating-set`, its reader from an
//! s-expression, and its text, which is the name of a vector entry.
//!
//! A column is written by its name. A ground expression has every table and every
//! column bound to a name, so its text says what it computes on one state.

use std::fmt;

use arclog::layout::SourceFile;
use arclog::read::{read_sexprs, SExpr};
use arclog::registry::{LibEntry, LibName, Macro, ProposerKind, Registry};

use crate::library::{Library, MacroKind};

/// A column of a relation in an expression: its name, or a hole.
pub type Column = String;

/// A comparison of a `select`.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug, PartialOrd, Ord, serde::Serialize, serde::Deserialize)]
pub enum Op {
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
}

impl Op {
    pub const ALL: [Op; 6] = [Op::Eq, Op::Ne, Op::Lt, Op::Le, Op::Gt, Op::Ge];

    pub fn text(self) -> &'static str {
        match self {
            Op::Eq => "=",
            Op::Ne => "!=",
            Op::Lt => "<",
            Op::Le => "<=",
            Op::Gt => ">",
            Op::Ge => ">=",
        }
    }

    fn parse(text: &str) -> Option<Op> {
        Op::ALL.into_iter().find(|op| op.text() == text)
    }
}

/// What a `select` compares a column with.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub enum Operand {
    Column(Column),
    Zero,
}

/// A relation the expression does not compute.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub enum Leaf {
    /// A table of the state, by the name its program gives it: `&ink`,
    /// `&rays.ray`.
    Table(String),
    Input,
    Output,
    ExInput,
    ExOutput,
    /// A relation that the program holds as data: `query_kind`, `column_type`.
    Program(String),
    /// A lib relation that needs no bound column.
    Lib(String),
    /// A proposer with no `domain` mark, read as the whole set of its rows.
    Proposer(String),
}

impl Leaf {
    fn text(&self) -> &str {
        match self {
            Leaf::Table(name) | Leaf::Program(name) | Leaf::Lib(name) | Leaf::Proposer(name) => name,
            Leaf::Input => "input",
            Leaf::Output => "output",
            Leaf::ExInput => "ex_input",
            Leaf::ExOutput => "ex_output",
        }
    }
}

/// A field of an input binding: a column, or a list that fills a type
/// parameter's column with a record.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub enum Field {
    One(Column),
    Record(Vec<Column>),
    /// The value `0`, at a column whose type has one.
    Zero,
}

/// One input of a `component`, written from a relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub struct Binding {
    pub input: String,
    pub relation: Rel,
    pub key: Vec<Column>,
    pub fields: Vec<Field>,
}

/// A relation-valued term.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub enum Rel {
    Leaf(Leaf),
    Project(Box<Rel>, Vec<Column>),
    Select(Box<Rel>, Column, Op, Operand),
    Join(Box<Rel>, Box<Rel>, Vec<(Column, Column)>),
    Antijoin(Box<Rel>, Box<Rel>, Vec<(Column, Column)>),
    /// The left relation's rows that have a match in the right.
    Semijoin(Box<Rel>, Box<Rel>, Vec<(Column, Column)>),
    /// The values of the outer columns at which the domain has a row and each of
    /// its rows there has a match in the body.
    All(Box<Rel>, Box<Rel>, Vec<Column>, Vec<(Column, Column)>),
    Union(Box<Rel>, Box<Rel>, Vec<(Column, Operand)>),
    LibJoin(Box<Rel>, String, Vec<(String, Column)>),
    Component(String, Vec<Binding>, String),
    /// A call of a fragment of the library, with each argument as written.
    Call(String, Vec<Written>),
}

/// An argument of a macro, as the call writes it.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub enum Written {
    Symbol(String),
    List(Vec<Written>),
}

impl Written {
    fn of(expr: &SExpr) -> Result<Written, String> {
        match expr {
            SExpr::Symbol { text, .. } => Ok(Written::Symbol(text.to_string())),
            SExpr::List { items, .. } => Ok(Written::List(items.iter().map(Written::of).collect::<Result<_, _>>()?)),
            SExpr::String { text, .. } => Err(format!("a quoted string `{text}` stands in no expression")),
        }
    }
}

impl fmt::Display for Written {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Written::Symbol(text) => f.write_str(text),
            Written::List(items) => {
                f.write_str("(")?;
                for (index, item) in items.iter().enumerate() {
                    if index > 0 {
                        f.write_str(" ")?;
                    }
                    write!(f, "{item}")?;
                }
                f.write_str(")")
            }
        }
    }
}

/// A feature expression: one aggregate over a relation.
#[derive(Clone, PartialEq, Eq, Hash, Debug, PartialOrd, Ord)]
pub enum Feature {
    Nonempty(Rel),
    Cardinality(Rel),
    ValueSet(Rel, Vec<Column>),
    /// The first relation's count of rows over the second's, as an exact fraction.
    Ratio(Rel, Rel),
    /// A call of a `feature` of the library, with each argument as written.
    Call(String, Vec<Written>),
}

impl Rel {
    /// Calls `visit` on each leaf of the term, those that a call of a macro reads included.
    pub fn each_leaf(&self, visit: &mut dyn FnMut(&Leaf)) {
        match self {
            Rel::Leaf(leaf) => visit(leaf),
            Rel::Project(rel, _) | Rel::Select(rel, ..) | Rel::LibJoin(rel, ..) => rel.each_leaf(visit),
            Rel::Join(left, right, _) | Rel::Antijoin(left, right, _) | Rel::Semijoin(left, right, _) | Rel::All(left, right, ..) | Rel::Union(left, right, _) => {
                left.each_leaf(visit);
                right.each_leaf(visit);
            }
            Rel::Component(_, bindings, _) => {
                for binding in bindings {
                    binding.relation.each_leaf(visit);
                }
            }
            Rel::Call(name, args) => {
                for leaf in crate::library::call_leaves(name, args) {
                    visit(&leaf);
                }
            }
        }
    }

    /// Calls `visit` on each call of a macro in the term.
    pub fn each_call<'r>(&'r self, visit: &mut dyn FnMut(&'r str, &'r [Written])) {
        match self {
            Rel::Leaf(_) => {}
            Rel::Project(rel, _) | Rel::Select(rel, ..) | Rel::LibJoin(rel, ..) => rel.each_call(visit),
            Rel::Join(left, right, _) | Rel::Antijoin(left, right, _) | Rel::Semijoin(left, right, _) | Rel::All(left, right, ..) | Rel::Union(left, right, _) => {
                left.each_call(visit);
                right.each_call(visit);
            }
            Rel::Component(_, bindings, _) => {
                for binding in bindings {
                    binding.relation.each_call(visit);
                }
            }
            Rel::Call(name, args) => visit(name, args),
        }
    }

    /// The count of the term's operators, leaves left out.
    pub fn size(&self) -> usize {
        match self {
            Rel::Leaf(_) => 0,
            Rel::Call(name, args) => crate::library::call_size(name, args),
            Rel::Project(rel, _) | Rel::Select(rel, ..) | Rel::LibJoin(rel, ..) => 1 + rel.size(),
            Rel::Join(left, right, _) | Rel::Antijoin(left, right, _) | Rel::Semijoin(left, right, _) | Rel::All(left, right, ..) | Rel::Union(left, right, _) => 1 + left.size() + right.size(),
            // Each bound input past the first combines one more relation, as a `join` does.
            Rel::Component(_, bindings, _) => bindings.len().max(1) + bindings.iter().map(|binding| binding.relation.size()).sum::<usize>(),
        }
    }
}

impl Rel {
    /// The count of the term's distinct operators: a subexpression that appears
    /// twice counts once.
    pub fn distinct_size(&self) -> usize {
        let mut seen = crate::lookup::LookupSet::new();
        self.add_distinct(&mut seen)
    }

    /// The count of the distinct operators of this term that `seen` does not hold.
    pub fn add_distinct<'r>(&'r self, seen: &mut crate::lookup::LookupSet<&'r Rel>) -> usize {
        if matches!(self, Rel::Leaf(_)) || !seen.insert(self) {
            return 0;
        }
        match self {
            Rel::Leaf(_) => 0,
            Rel::Call(name, args) => crate::library::call_size(name, args),
            Rel::Project(rel, _) | Rel::Select(rel, ..) | Rel::LibJoin(rel, ..) => 1 + rel.add_distinct(seen),
            Rel::Join(left, right, _) | Rel::Antijoin(left, right, _) | Rel::Semijoin(left, right, _) | Rel::All(left, right, ..) | Rel::Union(left, right, _) => {
                1 + left.add_distinct(seen) + right.add_distinct(seen)
            }
            Rel::Component(_, bindings, _) => bindings.len().max(1) + bindings.iter().map(|binding| binding.relation.add_distinct(seen)).sum::<usize>(),
        }
    }
}

impl Feature {
    /// The relation under the root, for a root the grammar names.
    pub fn relation(&self) -> Option<&Rel> {
        match self {
            Feature::Nonempty(rel) | Feature::Cardinality(rel) | Feature::ValueSet(rel, _) => Some(rel),
            Feature::Ratio(..) | Feature::Call(..) => None,
        }
    }

    /// The count of the expression's operators, leaves and the root left out.
    /// A macro's call has the size of its expansion.
    pub fn size(&self) -> usize {
        match self {
            Feature::Call(name, args) => crate::library::call_size(name, args),
            Feature::Ratio(first, second) => {
                let mut seen = crate::lookup::LookupSet::new();
                first.add_distinct(&mut seen) + second.add_distinct(&mut seen)
            }
            _ => self.relation().map_or(0, Rel::size),
        }
    }
}

/// The reader of a term, which reads the registry for the names of a leaf.
pub struct Reader<'r> {
    pub registry: &'r Registry,
    /// The macros of the library, which a relation or a root takes.
    pub library: &'r Library,
    /// The names of the program relations, which a leaf takes.
    pub program_relations: &'r dyn Fn(&str) -> bool,
}

fn symbol(expr: &SExpr) -> Result<&str, String> {
    match expr {
        SExpr::Symbol { text, .. } => Ok(text),
        _ => Err(format!("a symbol is expected at {}", show(expr))),
    }
}

fn show(expr: &SExpr) -> String {
    Written::of(expr).map_or_else(|error| error, |written| written.to_string())
}

fn items(expr: &SExpr) -> Result<&[SExpr], String> {
    match expr {
        SExpr::List { items, .. } => Ok(items),
        _ => Err(format!("a list is expected at {}", show(expr))),
    }
}

fn pairs(exprs: &[SExpr]) -> Result<Vec<(String, String)>, String> {
    exprs
        .iter()
        .map(|expr| match items(expr)? {
            [a, b] => Ok((symbol(a)?.to_string(), symbol(b)?.to_string())),
            _ => Err(format!("a pair of columns is expected at {}", show(expr))),
        })
        .collect()
}

fn columns(exprs: &[SExpr]) -> Result<Vec<String>, String> {
    exprs.iter().map(|expr| symbol(expr).map(str::to_string)).collect()
}

impl Reader<'_> {
    /// The one term that `text` writes.
    pub fn one(&self, text: &str) -> Result<SExpr, String> {
        let (mut exprs, _) = read_sexprs(text, SourceFile::Arclog).map_err(|diagnostics| format!("{diagnostics:?}"))?;
        match exprs.len() {
            1 => Ok(exprs.remove(0)),
            count => Err(format!("{count} terms where one is expected: {text}")),
        }
    }

    /// The feature expression that `text` writes.
    pub fn feature_text(&self, text: &str) -> Result<Feature, String> {
        self.feature(&self.one(text)?)
    }

    /// The relation that `text` writes.
    pub fn rel_text(&self, text: &str) -> Result<Rel, String> {
        self.rel(&self.one(text)?)
    }

    /// The feature expression that `expr` writes.
    pub fn feature(&self, expr: &SExpr) -> Result<Feature, String> {
        let list = items(expr)?;
        let head = list.first().map(symbol).transpose()?.unwrap_or_default();
        match (head, &list[1..]) {
            ("nonempty", [rel]) => Ok(Feature::Nonempty(self.rel(rel)?)),
            ("cardinality", [rel]) => Ok(Feature::Cardinality(self.rel(rel)?)),
            ("ratio", [first, second]) => Ok(Feature::Ratio(self.rel(first)?, self.rel(second)?)),
            ("value-set", [rel, cols @ ..]) if !cols.is_empty() => Ok(Feature::ValueSet(self.rel(rel)?, columns(cols)?)),
            (name, args) if self.library.get(name).is_some_and(|found| found.kind == MacroKind::Feature) => Ok(Feature::Call(name.to_string(), args.iter().map(Written::of).collect::<Result<_, _>>()?)),
            _ => Err(format!("no aggregate at {}", show(expr))),
        }
    }

    /// The relation that `expr` writes.
    pub fn rel(&self, expr: &SExpr) -> Result<Rel, String> {
        if let SExpr::Symbol { text, .. } = expr {
            return self.leaf(text).map(Rel::Leaf);
        }
        let list = items(expr)?;
        let head = list.first().map(symbol).transpose()?.unwrap_or_default();
        let boxed = |rel: &SExpr| self.rel(rel).map(Box::new);
        match (head, &list[1..]) {
            ("project", [rel, cols @ ..]) if !cols.is_empty() => Ok(Rel::Project(boxed(rel)?, columns(cols)?)),
            ("select", [rel, column, op, operand]) => {
                let op = Op::parse(symbol(op)?).ok_or_else(|| format!("no comparison at {}", show(expr)))?;
                let operand = match symbol(operand)? {
                    "0" => Operand::Zero,
                    name => Operand::Column(name.to_string()),
                };
                Ok(Rel::Select(boxed(rel)?, symbol(column)?.to_string(), op, operand))
            }
            ("join", [left, right, rest @ ..]) => Ok(Rel::Join(boxed(left)?, boxed(right)?, pairs(rest)?)),
            ("antijoin", [left, right, rest @ ..]) => Ok(Rel::Antijoin(boxed(left)?, boxed(right)?, pairs(rest)?)),
            ("semijoin", [left, right, rest @ ..]) => Ok(Rel::Semijoin(boxed(left)?, boxed(right)?, pairs(rest)?)),
            ("all", [domain, body, outer, rest @ ..]) => Ok(Rel::All(boxed(domain)?, boxed(body)?, columns(items(outer)?)?, pairs(rest)?)),
            // Whether each row of the two stands at a row of the other, on the columns that the tokens `a=b` pair. A token with no `=` is a
            // column of the first that the paired columns determine.
            ("rows-equal" | "rows-project" | "rows-extend", [left, right, rest @ ..]) => {
                let (mut forward, mut back, mut free) = (Vec::new(), Vec::new(), Vec::new());
                for token in rest {
                    let token = symbol(token)?;
                    match token.split_once('=') {
                        Some((a, b)) => {
                            forward.push((a.to_string(), b.to_string()));
                            back.push((b.to_string(), a.to_string()));
                        }
                        None => free.push(token.to_string()),
                    }
                }
                let keys: Vec<Written> = forward.iter().map(|(a, _)| Written::Symbol(a.clone())).collect();
                let mut out = Rel::Join(Box::new(Rel::All(boxed(left)?, boxed(right)?, Vec::new(), forward)), Box::new(Rel::All(boxed(right)?, boxed(left)?, Vec::new(), back)), Vec::new());
                for column in free {
                    let determined = Rel::Call("determines".to_string(), vec![Written::of(left)?, Written::List(keys.clone()), Written::Symbol(column)]);
                    out = Rel::Join(Box::new(out), Box::new(determined), Vec::new());
                }
                Ok(out)
            }
            ("union", [left, right, rest @ ..]) if !rest.is_empty() => {
                let pairs = pairs(rest)?.into_iter().map(|(column, operand)| (column, if operand == "0" { Operand::Zero } else { Operand::Column(operand) })).collect();
                Ok(Rel::Union(boxed(left)?, boxed(right)?, pairs))
            }
            ("lib-join", [rel, name, rest @ ..]) => Ok(Rel::LibJoin(boxed(rel)?, symbol(name)?.to_string(), pairs(rest)?)),
            ("component", [name, rest @ ..]) if !rest.is_empty() => {
                let (port, bindings) = rest.split_last().expect("a component holds its port");
                let bindings = bindings.iter().map(|binding| self.binding(binding)).collect::<Result<_, _>>()?;
                Ok(Rel::Component(symbol(name)?.to_string(), bindings, symbol(port)?.to_string()))
            }
            (name, args) if self.library.get(name).is_some_and(|found| found.kind == MacroKind::Fragment) => Ok(Rel::Call(name.to_string(), args.iter().map(Written::of).collect::<Result<_, _>>()?)),
            _ => Err(format!("no operator at {}", show(expr))),
        }
    }

    fn binding(&self, expr: &SExpr) -> Result<Binding, String> {
        let read = |input: &SExpr, relation: &SExpr, key: &SExpr, fields: &[SExpr]| -> Result<Binding, String> {
            let fields = fields
                .iter()
                .map(|field| match field {
                    SExpr::Symbol { text, .. } if &**text == "0" => Ok(Field::Zero),
                    SExpr::Symbol { text, .. } => Ok(Field::One(text.to_string())),
                    list => Ok(Field::Record(columns(items(list)?)?)),
                })
                .collect::<Result<_, String>>()?;
            Ok(Binding { input: symbol(input)?.to_string(), relation: self.rel(relation)?, key: columns(items(key)?)?, fields })
        };
        match items(expr)? {
            [input, relation, key, fields] => read(input, relation, key, items(fields)?),
            // An input with no column but `key` writes no fields.
            [input, relation, key] => read(input, relation, key, &[]),
            _ => Err(format!("an input binding holds an input, a relation, its key columns and its fields, at {}", show(expr))),
        }
    }

    fn leaf(&self, text: &str) -> Result<Leaf, String> {
        match text {
            "input" => return Ok(Leaf::Input),
            "output" => return Ok(Leaf::Output),
            "ex_input" => return Ok(Leaf::ExInput),
            "ex_output" => return Ok(Leaf::ExOutput),
            _ => {}
        }
        if text.starts_with('&') {
            return Ok(Leaf::Table(text.to_string()));
        }
        if (self.program_relations)(text) {
            return Ok(Leaf::Program(text.to_string()));
        }
        match self.registry.entry(&LibName(text.into())) {
            Some(LibEntry::Relation(_) | LibEntry::Macro(Macro::Relation { .. })) => Ok(Leaf::Lib(text.to_string())),
            Some(LibEntry::Proposer(proposer)) => match proposer.kind {
                ProposerKind::Native { domain: true } => Err(format!("`{text}` is a domain, which belongs to determinations")),
                _ => Ok(Leaf::Proposer(text.to_string())),
            },
            Some(LibEntry::Component(_)) => Err(format!("`{text}` is a component, and no leaf")),
            None => Err(format!("`{text}` names no leaf")),
        }
    }
}

fn list(f: &mut fmt::Formatter<'_>, names: &[String]) -> fmt::Result {
    f.write_str("(")?;
    f.write_str(&names.join(" "))?;
    f.write_str(")")
}

fn write_pairs(f: &mut fmt::Formatter<'_>, pairs: &[(String, String)]) -> fmt::Result {
    for (a, b) in pairs {
        write!(f, " ({a} {b})")?;
    }
    Ok(())
}

impl fmt::Display for Field {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Field::One(name) => f.write_str(name),
            Field::Record(names) => list(f, names),
            Field::Zero => f.write_str("0"),
        }
    }
}

impl fmt::Display for Binding {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "({} {} ", self.input, self.relation)?;
        list(f, &self.key)?;
        f.write_str(" (")?;
        for (index, field) in self.fields.iter().enumerate() {
            if index > 0 {
                f.write_str(" ")?;
            }
            write!(f, "{field}")?;
        }
        f.write_str("))")
    }
}

impl fmt::Display for Rel {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Rel::Leaf(leaf) => f.write_str(leaf.text()),
            Rel::Project(rel, cols) => write!(f, "(project {rel} {})", cols.join(" ")),
            Rel::Select(rel, column, op, operand) => {
                let operand = match operand {
                    Operand::Column(name) => name.as_str(),
                    Operand::Zero => "0",
                };
                write!(f, "(select {rel} {column} {} {operand})", op.text())
            }
            Rel::Join(left, right, rest) => {
                write!(f, "(join {left} {right}")?;
                write_pairs(f, rest)?;
                f.write_str(")")
            }
            Rel::Antijoin(left, right, rest) => {
                write!(f, "(antijoin {left} {right}")?;
                write_pairs(f, rest)?;
                f.write_str(")")
            }
            Rel::Semijoin(left, right, rest) => {
                write!(f, "(semijoin {left} {right}")?;
                write_pairs(f, rest)?;
                f.write_str(")")
            }
            Rel::All(domain, body, outer, rest) => {
                write!(f, "(all {domain} {body} ({})", outer.join(" "))?;
                write_pairs(f, rest)?;
                f.write_str(")")
            }
            Rel::Union(left, right, rest) => {
                write!(f, "(union {left} {right}")?;
                for (column, operand) in rest {
                    match operand {
                        Operand::Column(name) => write!(f, " ({column} {name})")?,
                        Operand::Zero => write!(f, " ({column} 0)")?,
                    }
                }
                f.write_str(")")
            }
            Rel::LibJoin(rel, name, rest) => {
                write!(f, "(lib-join {rel} {name}")?;
                write_pairs(f, rest)?;
                f.write_str(")")
            }
            Rel::Component(name, bindings, port) => {
                write!(f, "(component {name}")?;
                for binding in bindings {
                    write!(f, " {binding}")?;
                }
                write!(f, " {port})")
            }
            Rel::Call(name, args) => {
                write!(f, "({name}")?;
                for arg in args {
                    write!(f, " {arg}")?;
                }
                f.write_str(")")
            }
        }
    }
}

impl fmt::Display for Feature {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Feature::Nonempty(rel) => write!(f, "(nonempty {rel})"),
            Feature::Cardinality(rel) => write!(f, "(cardinality {rel})"),
            Feature::ValueSet(rel, cols) => write!(f, "(value-set {rel} {})", cols.join(" ")),
            Feature::Ratio(first, second) => write!(f, "(ratio {first} {second})"),
            Feature::Call(name, args) => {
                write!(f, "({name}")?;
                for arg in args {
                    write!(f, " {arg}")?;
                }
                f.write_str(")")
            }
        }
    }
}
