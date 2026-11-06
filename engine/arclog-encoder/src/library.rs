//! The reader of the feature library, `engine/lib/features.arclog`, and the
//! expansion of a call of one of its macros, by the rules of
//! `work/feature-spec/feature-spec.md#how-an-expression-expands`.
//!
//! A macro is a function from s-expressions to forms: each hole takes what
//! its kind declares, and each name the macro declares is fresh at each call.

use std::collections::HashMap;
use std::sync::OnceLock;

use arclog::layout::SourceFile;
use arclog::read::{read_sexprs, SExpr};

use crate::expand::{label_of, Col, Expander, Mark, Rows};
use crate::expression::Written;

/// The text of the library, which the crate embeds as the engine embeds the
/// registry.
pub const LIBRARY_TEXT: &str = include_str!("../../lib/features.arclog");

/// Whether a macro gives a relation or a feature's value.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MacroKind {
    Fragment,
    Feature,
}

/// What a hole takes.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum HoleKind {
    /// A table or another macro's call.
    Relation,
    /// A column of the relation that the hole of this name takes.
    Column(String),
    /// `input`, `output`, `ex_input` or `ex_output`.
    Grid,
    /// A list of columns of the relation that the hole of this name takes.
    Columns(String),
}

/// A hole of a macro's signature.
#[derive(Clone, Debug)]
pub struct Hole {
    pub name: String,
    pub kind: HoleKind,
}

/// A macro of the library.
#[derive(Clone, Debug)]
pub struct Macro {
    pub kind: MacroKind,
    pub name: String,
    pub text: String,
    pub holes: Vec<Hole>,
    pub forms: Vec<SExpr>,
}

/// The macros of the library.
#[derive(Debug, Default)]
pub struct Library {
    macros: HashMap<String, Macro>,
    /// Each name in the order of the file.
    order: Vec<String>,
}

fn symbol_of(expr: &SExpr) -> Result<&str, String> {
    match expr {
        SExpr::Symbol { text, .. } => Ok(text),
        other => Err(format!("a symbol is expected, at line {}", other.place().line)),
    }
}

fn items_of(expr: &SExpr) -> Result<&[SExpr], String> {
    match expr {
        SExpr::List { items, .. } => Ok(items),
        other => Err(format!("a list is expected, at line {}", other.place().line)),
    }
}

fn hole(expr: &SExpr) -> Result<Hole, String> {
    let list = items_of(expr)?;
    let name = symbol_of(list.first().ok_or("a hole holds its name")?)?;
    if !name.starts_with('?') {
        return Err(format!("`{name}` is no hole, `?` and a name"));
    }
    let word = |index: usize| list.get(index).ok_or_else(|| format!("the hole `{name}` lacks its kind")).and_then(symbol_of);
    let kind = match word(1)? {
        "relation" => HoleKind::Relation,
        "grid" => HoleKind::Grid,
        "column" => HoleKind::Column(word(2)?.to_string()),
        "columns" => HoleKind::Columns(word(2)?.to_string()),
        other => return Err(format!("`{other}` is no kind of hole")),
    };
    Ok(Hole { name: name.to_string(), kind })
}

impl Library {
    /// The library that `text` writes.
    pub fn parse(text: &str) -> Result<Library, String> {
        let (exprs, _) = read_sexprs(text, SourceFile::Arclog).map_err(|diagnostics| format!("{diagnostics:?}"))?;
        let mut library = Library::default();
        for expr in &exprs {
            let list = items_of(expr)?;
            let kind = match list.first().map(symbol_of).transpose()? {
                Some("fragment") => MacroKind::Fragment,
                Some("feature") => MacroKind::Feature,
                other => return Err(format!("`{other:?}` heads no form of the library")),
            };
            let signature = items_of(list.get(1).ok_or("a macro holds its signature")?)?;
            let name = symbol_of(signature.first().ok_or("a signature holds its name")?)?.to_string();
            let holes = signature[1..].iter().map(hole).collect::<Result<Vec<_>, _>>()?;
            let (doc, forms) = match list.get(2) {
                Some(SExpr::String { text, .. }) => (text.to_string(), &list[3..]),
                _ => return Err(format!("the macro `{name}` holds its text after its signature")),
            };
            let end = forms.last().ok_or_else(|| format!("the macro `{name}` holds no form"))?;
            let ends = items_of(end)?.first().map(symbol_of).transpose()?;
            match (kind, ends) {
                (MacroKind::Fragment, Some("gives")) | (MacroKind::Feature, Some("EXPORT")) => {}
                (MacroKind::Fragment, _) => return Err(format!("the fragment `{name}` ends in `gives`")),
                (MacroKind::Feature, _) => return Err(format!("the feature `{name}` ends in `EXPORT`")),
            }
            library.order.push(name.clone());
            library.macros.insert(name.clone(), Macro { kind, name, text: doc, holes, forms: forms.to_vec() });
        }
        Ok(library)
    }

    pub fn get(&self, name: &str) -> Option<&Macro> {
        self.macros.get(name)
    }

    /// Each macro of the library, in the order of the file.
    pub fn each(&self) -> impl Iterator<Item = &Macro> {
        self.order.iter().map(|name| &self.macros[name])
    }
}

/// The library of [`LIBRARY_TEXT`], read on first use.
pub fn library() -> &'static Library {
    static LIBRARY: OnceLock<Library> = OnceLock::new();
    LIBRARY.get_or_init(|| Library::parse(LIBRARY_TEXT).unwrap_or_else(|fault| panic!("the feature library does not read: {fault}")))
}

/// The size of a call: the operators of its expansion. Each `INIT` form is one
/// `component`, and each `QUERY` that reads no instance of the macro is one
/// operator, since a `QUERY` over an instance's output only labels its columns.
/// Each relation hole adds the size of what it takes.
pub fn call_size(name: &str, args: &[Written]) -> usize {
    let Some(found) = library().get(name) else { return 0 };
    let mut size = 0;
    for form in &found.forms {
        let Ok(list) = items_of(form) else { continue };
        match list.first().and_then(|head| symbol_of(head).ok()) {
            Some("INIT") => size += 1,
            Some("QUERY") => {
                let reads_instance = list[2..].iter().any(|atom| match items_of(atom).ok().and_then(|atom| atom.first()) {
                    Some(SExpr::Symbol { text, .. }) => text.starts_with('&') && text.contains('.'),
                    _ => false,
                });
                size += usize::from(!reads_instance);
            }
            _ => {}
        }
    }
    let registry = arclog::registry::Registry::get();
    let reader = crate::expression::Reader { registry, library: library(), program_relations: &crate::program_relations::is_program_relation };
    for (hole, arg) in found.holes.iter().zip(args) {
        if matches!(hole.kind, HoleKind::Relation) {
            size += reader.rel_text(&arg.to_string()).map_or(0, |rel| rel.size());
        }
    }
    size
}

/// What a hole holds at a call.
#[derive(Clone, Debug)]
pub enum Bound {
    Relation(Rows),
    /// A column by its name in the relation of the hole `of`.
    Column { of: String, name: String },
    Columns { of: String, names: Vec<String> },
}

/// One call's holes, the names it declares and the labels of the form in
/// progress.
struct Call {
    holes: HashMap<String, Bound>,
    /// The fresh name of each name that the macro declares.
    declared: HashMap<String, String>,
    /// The label of each column of each relation hole, in the form in progress.
    labels: HashMap<(String, String), String>,
    /// The labels the form in progress has given.
    taken: Vec<String>,
    /// Whether the atoms in progress stand in an `INIT` form.
    in_instance: bool,
}

impl Call {
    fn new_form(&mut self, in_instance: bool) {
        self.labels.clear();
        self.taken.clear();
        self.in_instance = in_instance;
    }

    /// The label of the column `name` of the relation hole `of`: named by the
    /// column, with a suffix where another column of the form has that name.
    fn label(&mut self, of: &str, name: &str) -> String {
        if let Some(held) = self.labels.get(&(of.to_string(), name.to_string())) {
            return held.clone();
        }
        let base = label_of(name);
        let mut label = base.clone();
        let mut suffix = 2;
        while self.taken.contains(&label) {
            label = format!("{base}_{suffix}");
            suffix += 1;
        }
        self.taken.push(label.clone());
        self.labels.insert((of.to_string(), name.to_string()), label.clone());
        label
    }

    fn rows(&self, hole: &str) -> Result<&Rows, String> {
        match self.holes.get(hole) {
            Some(Bound::Relation(rows)) => Ok(rows),
            _ => Err(format!("`{hole}` holds no relation")),
        }
    }

    /// The names of the columns of the relation hole `of` other than those
    /// that `excluded`, holes of columns, name.
    fn others(&self, of: &str, excluded: &[SExpr]) -> Result<Vec<String>, String> {
        let rows = self.rows(of)?;
        let mut out = Vec::new();
        let mut left_out: Vec<String> = Vec::new();
        for expr in excluded {
            match self.holes.get(symbol_of(expr)?) {
                Some(Bound::Column { name, .. }) => left_out.push(name.clone()),
                Some(Bound::Columns { names, .. }) => left_out.extend(names.iter().cloned()),
                _ => return Err(format!("`{}` holds no column", symbol_of(expr)?)),
            }
        }
        for column in &rows.columns {
            if !left_out.contains(&column.name) {
                out.push(column.name.clone());
            }
        }
        Ok(out)
    }

    fn renamed(&self, written: &str) -> Result<String, String> {
        let (owner, port) = written.split_once('.').map_or((written, None), |(owner, port)| (owner, Some(port)));
        let fresh = self.declared.get(owner).ok_or_else(|| format!("the macro declares no `{owner}`"))?;
        Ok(port.map_or_else(|| fresh.clone(), |port| format!("{fresh}.{port}")))
    }

    /// `*N`, with a suffix where the relation of the hole `of` already has
    /// that name.
    fn new_label(&mut self, name: &str, of: &[SExpr]) -> Result<String, String> {
        let mut held: Vec<String> = Vec::new();
        for expr in of {
            for column in &self.rows(symbol_of(expr)?)?.columns {
                held.push(column.name.clone());
            }
        }
        let mut label = name.to_string();
        let mut suffix = 2;
        while held.contains(&label) || self.taken.contains(&label) {
            label = format!("{name}_{suffix}");
            suffix += 1;
        }
        self.taken.push(label.clone());
        Ok(label)
    }
}

impl Expander<'_> {
    /// The rows that the call `name(args)` gives, each argument as written.
    pub(crate) fn call_written(&mut self, name: &str, args: &[Written]) -> Result<Rows, String> {
        let Some(found) = self.library.get(name) else { return Err(format!("the library has no macro `{name}`")) };
        let found: Macro = found.clone();
        if found.holes.len() != args.len() && !found.holes.last().is_some_and(|hole| matches!(hole.kind, HoleKind::Columns(_))) {
            return Err(format!("the macro `{name}` takes {} arguments, and the call writes {}", found.holes.len(), args.len()));
        }
        let mut holes: HashMap<String, Bound> = HashMap::new();
        for (index, hole) in found.holes.iter().enumerate() {
            let arg = args.get(index).ok_or_else(|| format!("the call of `{name}` lacks `{}`", hole.name))?;
            let bound = match &hole.kind {
                HoleKind::Relation | HoleKind::Grid => Bound::Relation(self.rows_written(arg)?),
                HoleKind::Column(of) => {
                    let name = written_symbol(arg)?.to_string();
                    Bound::Column { of: of.clone(), name }
                }
                HoleKind::Columns(of) => {
                    // The last hole takes the rest of the call, or one list.
                    let names: Vec<String> = match (arg, index + 1 == found.holes.len()) {
                        (Written::List(items), _) => items.iter().map(|item| written_symbol(item).map(str::to_string)).collect::<Result<_, _>>()?,
                        (Written::Symbol(_), true) => args[index..].iter().map(|item| written_symbol(item).map(str::to_string)).collect::<Result<_, _>>()?,
                        (Written::Symbol(one), false) => vec![one.clone()],
                    };
                    Bound::Columns { of: of.clone(), names }
                }
            };
            holes.insert(hole.name.clone(), bound);
        }
        self.call(&found, holes)
    }

    fn rows_written(&mut self, written: &Written) -> Result<Rows, String> {
        let text = written.to_string();
        let rel = self.reader().rel_text(&text)?;
        self.rel(&rel)
    }

    fn call(&mut self, found: &Macro, holes: HashMap<String, Bound>) -> Result<Rows, String> {
        for hole in &found.holes {
            let (of, names) = match holes.get(&hole.name) {
                Some(Bound::Column { of, name }) => (of, vec![name.clone()]),
                Some(Bound::Columns { of, names }) => (of, names.clone()),
                _ => continue,
            };
            let Some(Bound::Relation(rows)) = holes.get(of) else { return Err(format!("the hole `{}` names no relation", hole.name)) };
            for name in names {
                rows.index(&name)?;
            }
        }
        let mut call = Call { holes, declared: HashMap::new(), labels: HashMap::new(), taken: Vec::new(), in_instance: false };
        // Each name the macro declares is fresh at this call.
        for form in &found.forms {
            let list = items_of(form)?;
            if let [SExpr::Symbol { text: head, .. }, SExpr::Symbol { text: name, .. }, ..] = list {
                if matches!(&**head, "QUERY" | "INIT") {
                    let fresh = self.fresh();
                    call.declared.insert(name.to_string(), fresh);
                }
            }
        }
        let mut given = None;
        for form in &found.forms {
            let list = items_of(form)?;
            match list.first().map(symbol_of).transpose()? {
                Some("QUERY") => {
                    let name = call.renamed(symbol_of(list.get(1).ok_or("a `QUERY` holds its name")?)?)?;
                    call.new_form(false);
                    let body = list[2..].iter().map(|atom| self.conjunct(atom, &mut call)).collect::<Result<Vec<_>, _>>()?;
                    let columns = kept_labels(&body)?;
                    self.forms.push(format!("({} {name}\n  {})", self.keyword(), body.join("\n  ")));
                    given = Some(Rows { relation: name, columns: columns.into_iter().map(Col::plain).collect() });
                }
                Some("INIT") => {
                    let name = call.renamed(symbol_of(list.get(1).ok_or("an `INIT` holds its name")?)?)?;
                    let component = symbol_of(list.get(2).ok_or("an `INIT` holds its component")?)?.to_string();
                    call.new_form(true);
                    let mut clauses = Vec::new();
                    for clause in &list[3..] {
                        clauses.push(self.instance_clause(clause, &mut call)?);
                    }
                    self.forms.push(format!("(INIT {name} {component}\n  {})", clauses.join("\n  ")));
                }
                Some("EXPORT") => {
                    call.new_form(false);
                    let name = self.fresh();
                    let body = list[1..].iter().map(|atom| self.conjunct(atom, &mut call)).collect::<Result<Vec<_>, _>>()?;
                    let body: Vec<String> = body.iter().map(|atom| atom.replace('^', "*")).collect();
                    let columns = kept_labels(&body)?;
                    self.forms.push(format!("({} {name}\n  {})", self.keyword(), body.join("\n  ")));
                    given = Some(Rows { relation: name, columns: columns.into_iter().map(Col::plain).collect() });
                }
                Some("gives") => {
                    let name = call.renamed(symbol_of(list.get(1).ok_or("a `gives` names a relation")?)?)?;
                    let held = given.as_ref().filter(|rows: &&Rows| rows.relation == name);
                    if held.is_none() {
                        return Err(format!("the macro `{}` gives a relation that no `QUERY` before it derives", found.name));
                    }
                }
                other => return Err(format!("`{other:?}` heads no form of a macro")),
            }
        }
        given.ok_or_else(|| format!("the macro `{}` gives no relation", found.name))
    }

    /// A clause of an `INIT` form: a key clause or an input.
    fn instance_clause(&mut self, expr: &SExpr, call: &mut Call) -> Result<String, String> {
        let list = items_of(expr)?;
        let head = symbol_of(list.first().ok_or("an instance's clause holds its name")?)?;
        if head == "key" {
            let body = items_of(list.get(1).ok_or("a key clause holds its body")?)?;
            let body = body.iter().map(|atom| self.conjunct(atom, call)).collect::<Result<Vec<_>, _>>()?;
            let inputs = list[2..].iter().map(|input| self.instance_clause(input, call)).collect::<Result<Vec<_>, _>>()?;
            return Ok(format!("(key ({})\n    {})", body.join(" "), inputs.join("\n    ")));
        }
        let sites = items_of(list.get(1).ok_or("an input holds its head")?)?;
        let mut head_sites = Vec::new();
        for site in sites {
            head_sites.extend(self.literal_site(site, call)?);
        }
        let body = list[2..].iter().map(|atom| self.conjunct(atom, call)).collect::<Result<Vec<_>, _>>()?;
        Ok(format!("({head} ({})\n      {})", head_sites.join(" "), body.join("\n      ")))
    }

    /// A conjunct of a macro's form, as plain arclog.
    fn conjunct(&mut self, expr: &SExpr, call: &mut Call) -> Result<String, String> {
        let list = items_of(expr)?;
        let head = symbol_of(list.first().ok_or("a conjunct holds its head")?)?;
        match head {
            "NOT" | "OR" | "IF" | "ALL" => {
                let inner = list[1..].iter().map(|item| match item {
                    SExpr::List { items, .. } if items.first().is_some_and(|first| matches!(first, SExpr::List { .. })) => {
                        let parts = items.iter().map(|atom| self.conjunct(atom, call)).collect::<Result<Vec<_>, _>>()?;
                        Ok(format!("({})", parts.join(" ")))
                    }
                    atom => self.conjunct(atom, call),
                }).collect::<Result<Vec<_>, String>>()?;
                Ok(format!("({head} {})", inner.join(" ")))
            }
            hole if hole.starts_with('?') => self.hole_atom(hole, &list[1..], call),
            name if name.starts_with('&') => {
                let name = call.renamed(name)?;
                let mut sites = Vec::new();
                for site in &list[1..] {
                    sites.extend(self.literal_site(site, call)?);
                }
                Ok(if sites.is_empty() { format!("({name})") } else { format!("({name} {})", sites.join(" ")) })
            }
            // A constraint, or a lib relation: its sites are literal.
            other => {
                let mut sites = Vec::new();
                for site in &list[1..] {
                    match site {
                        SExpr::Symbol { text, .. } if text.starts_with('?') => sites.push(self.column_label(text, call)?),
                        SExpr::Symbol { text, .. } => sites.push(text.to_string()),
                        _ => sites.extend(self.literal_site(site, call)?),
                    }
                }
                Ok(format!("({other} {})", sites.join(" ")))
            }
        }
    }

    /// The label of the column that the hole `name` holds.
    fn column_label(&self, name: &str, call: &mut Call) -> Result<String, String> {
        match call.holes.get(name).cloned() {
            Some(Bound::Column { of, name }) => Ok(call.label(&of, &name)),
            _ => Err(format!("`{name}` holds no column")),
        }
    }

    /// An atom whose relation a hole holds.
    fn hole_atom(&mut self, hole: &str, sites: &[SExpr], call: &mut Call) -> Result<String, String> {
        let rows = call.rows(hole)?.clone();
        let mut marks: Vec<(usize, Mark)> = Vec::new();
        for site in sites {
            match site {
                // A bare column hole joins its label.
                SExpr::Symbol { text, .. } if text.starts_with('?') => {
                    let (of, name) = column_of(call, text)?;
                    let label = call.label(&of, &name);
                    marks.push((position_in(&rows, &of, &name, hole)?, Mark::Join(label)));
                }
                SExpr::List { items, .. } => {
                    let first = symbol_of(items.first().ok_or("a site holds its head")?)?;
                    if first == "*others" {
                        let of = symbol_of(items.get(1).ok_or("`*others` names a relation")?)?;
                        for name in call.others(of, &items[2..])? {
                            let label = call.label(of, &name);
                            marks.push((rows.index(&name)?, Mark::Fresh(label)));
                        }
                    } else if first.starts_with('?') {
                        // `(?x *)` makes the label, and `(?x ^)` makes it a label of the key.
                        let mark = symbol_of(items.get(1).ok_or("a hole's site holds its mark")?)?;
                        let names: Vec<(String, String)> = match call.holes.get(first).cloned() {
                            Some(Bound::Column { of, name }) => vec![(of, name)],
                            Some(Bound::Columns { of, names }) => names.into_iter().map(|name| (of.clone(), name)).collect(),
                            _ => return Err(format!("`{first}` holds no column")),
                        };
                        for (of, name) in names {
                            let label = call.label(&of, &name);
                            let at = position_in(&rows, &of, &name, hole)?;
                            marks.push((at, match mark {
                                "*" => Mark::Fresh(label),
                                "^" => Mark::Key(label),
                                other => return Err(format!("`{other}` is no mark of a hole's site")),
                            }));
                        }
                    } else if let Some(column) = first.strip_prefix(':') {
                        // A site that names a column of the hole's relation.
                        let at = rows.index(column)?;
                        let value = items.get(1).ok_or("a site holds its label")?;
                        marks.push((at, self.literal_mark(value, call)?));
                    } else {
                        return Err(format!("`{first}` heads no site"));
                    }
                }
                other => return Err(format!("no site at line {}", other.place().line)),
            }
        }
        // A macro states no pairs: its atom on a grid joins the example of the
        // macro's relation, and a body in an instance keeps a site on `E`.
        if let Ok(at) = rows.index("E") {
            if !marks.iter().any(|(held, _)| *held == at) {
                let joined = rows_is_grid(&rows) && call.taken.iter().any(|label| label == "E") && !call.in_instance;
                if joined {
                    marks.push((at, Mark::Join("E".to_string())));
                } else if call.in_instance {
                    marks.push((at, Mark::Fresh(unique_in(call, "E"))));
                }
            }
        }
        Ok(rows.atom(&marks))
    }

    /// The mark that a literal site's value writes.
    fn literal_mark(&mut self, value: &SExpr, call: &mut Call) -> Result<Mark, String> {
        match value {
            SExpr::Symbol { text, .. } if text.starts_with('?') => Ok(Mark::Join(self.column_label(text, call)?)),
            SExpr::Symbol { text, .. } if &**text == "0" => Ok(Mark::Zero),
            SExpr::Symbol { text, .. } => Ok(match text.strip_prefix('*') {
                Some(name) => Mark::Fresh(name.to_string()),
                None => match text.strip_prefix('^') {
                    Some(name) => Mark::Key(name.to_string()),
                    None => Mark::Join(text.to_string()),
                },
            }),
            SExpr::List { items, .. } if items.first().is_some_and(|head| matches!(head, SExpr::Symbol { text, .. } if &**text == "*new")) => {
                let name = symbol_of(items.get(1).ok_or("`*new` holds a name")?)?;
                Ok(Mark::Fresh(call.new_label(name, &items[2..])?))
            }
            other => Err(format!("no label at line {}", other.place().line)),
        }
    }

    /// A site of an atom whose relation is no hole, or of an input's head: its
    /// text, or none where it holds a splice with no column left.
    fn literal_site(&mut self, site: &SExpr, call: &mut Call) -> Result<Option<String>, String> {
        match site {
            SExpr::Symbol { text, .. } if text.starts_with('?') => Ok(Some(self.column_label(text, call)?)),
            SExpr::Symbol { text, .. } => Ok(Some(text.to_string())),
            SExpr::String { .. } => Err("a quoted string stands at no site".to_string()),
            SExpr::List { items, .. } => {
                let head = symbol_of(items.first().ok_or("a site holds its head")?)?;
                if let Some(column) = head.strip_prefix(':') {
                    let mut args = Vec::new();
                    for item in &items[1..] {
                        args.extend(self.site_argument(item, call)?);
                    }
                    if args.is_empty() {
                        return Ok(None);
                    }
                    return Ok(Some(format!("(:{column} {})", args.join(" "))));
                }
                Err(format!("`{head}` heads no site"))
            }
        }
    }

    /// The arguments that one argument of a literal site writes.
    fn site_argument(&mut self, item: &SExpr, call: &mut Call) -> Result<Vec<String>, String> {
        match item {
            SExpr::Symbol { text, .. } if text.starts_with('?') => match call.holes.get(&**text).cloned() {
                Some(Bound::Column { of, name }) => Ok(vec![call.label(&of, &name)]),
                Some(Bound::Columns { of, names }) => Ok(names.iter().map(|name| call.label(&of, name)).collect()),
                _ => Err(format!("`{text}` holds no column")),
            },
            SExpr::Symbol { text, .. } => Ok(vec![text.to_string()]),
            SExpr::String { .. } => Err("a quoted string stands at no site".to_string()),
            SExpr::List { items, .. } => {
                let head = symbol_of(items.first().ok_or("a site holds its head")?)?;
                match head {
                    // In a head, `(others ?R ?x)` writes the labels bare.
                    "others" | "*others" => {
                        let of = symbol_of(items.get(1).ok_or("a splice names a relation")?)?;
                        let names = call.others(of, &items[2..])?;
                        let mark = if head == "*others" { "*" } else { "" };
                        Ok(names.iter().map(|name| format!("{mark}{}", call.label(of, name))).collect())
                    }
                    "*new" => {
                        let name = symbol_of(items.get(1).ok_or("`*new` holds a name")?)?;
                        Ok(vec![format!("*{}", call.new_label(name, &items[2..])?)])
                    }
                    hole if hole.starts_with('?') => {
                        // A field site on a hole, named by the column's label.
                        let mark = symbol_of(items.get(1).ok_or("a hole's site holds its mark")?)?;
                        let label = self.column_label(hole, call)?;
                        Ok(vec![format!("(:{label} {mark}{label})")])
                    }
                    field if field.starts_with(':') => Ok(self.literal_site(item, call)?.into_iter().collect()),
                    other => Err(format!("`{other}` heads no site argument")),
                }
            }
        }
    }
}

fn written_symbol(written: &Written) -> Result<&str, String> {
    match written {
        Written::Symbol(text) => Ok(text),
        Written::List(_) => Err(format!("a column is expected at {written}")),
    }
}

fn column_of(call: &Call, hole: &str) -> Result<(String, String), String> {
    match call.holes.get(hole) {
        Some(Bound::Column { of, name }) => Ok((of.clone(), name.clone())),
        _ => Err(format!("`{hole}` holds no column")),
    }
}

/// The position in `rows`, the relation of the hole `at`, of the column `name`
/// of the relation hole `of`.
fn position_in(rows: &Rows, of: &str, name: &str, at: &str) -> Result<usize, String> {
    if of != at {
        return Err(format!("a site of `{at}` names a column of `{of}`"));
    }
    rows.index(name)
}

fn rows_is_grid(rows: &Rows) -> bool {
    matches!(rows.relation.as_str(), "ex_input" | "ex_output")
}

fn unique_in(call: &Call, name: &str) -> String {
    // A site that stands only to keep the instance task-wide holds a label of
    // its own body, unless another column of the form has that name.
    let mut label = name.to_string();
    let mut suffix = 2;
    while call.labels.values().any(|held| *held == label) {
        label = format!("{name}_{suffix}");
        suffix += 1;
    }
    label
}

/// The labels that the body of `conjuncts` keeps, which are the columns of its
/// relation: a label that a site makes outside a `NOT` and an `ALL`, and, in an
/// `OR`, one that its first branch makes and every later branch names, as
/// `docs/arclog/arclog.md#disjunction` gives. No label of a test is kept.
fn kept_labels(conjuncts: &[String]) -> Result<Vec<String>, String> {
    let text = conjuncts.join("\n");
    let (exprs, _) = read_sexprs(&text, SourceFile::Arclog).map_err(|diagnostics| format!("{diagnostics:?}"))?;
    let mut kept = Vec::new();
    for expr in &exprs {
        keep(expr, &mut kept);
    }
    Ok(kept)
}

fn keep(expr: &SExpr, kept: &mut Vec<String>) {
    match expr {
        SExpr::Symbol { text, .. } => {
            if let Some(label) = text.strip_prefix('*') {
                if !kept.iter().any(|held| held == label) {
                    kept.push(label.to_string());
                }
            }
        }
        SExpr::String { .. } => {}
        SExpr::List { items, .. } => {
            let head = items.first().and_then(|first| symbol_of(first).ok());
            match head {
                Some("NOT" | "ALL") => {}
                Some("OR") => {
                    let mut first = Vec::new();
                    if let Some(branch) = items.get(1) {
                        keep(branch, &mut first);
                    }
                    for label in first {
                        let named = |branch: &SExpr| names_label(branch, &label);
                        if items[2..].iter().all(named) && !kept.contains(&label) {
                            kept.push(label);
                        }
                    }
                }
                Some("IF") => {
                    let mut then = Vec::new();
                    if let Some(branch) = items.get(2) {
                        keep(branch, &mut then);
                    }
                    for label in then {
                        if items.get(3).is_some_and(|otherwise| names_label(otherwise, &label)) && !kept.contains(&label) {
                            kept.push(label);
                        }
                    }
                }
                _ => {
                    for item in items.iter() {
                        keep(item, kept);
                    }
                }
            }
        }
    }
}

fn names_label(expr: &SExpr, label: &str) -> bool {
    match expr {
        SExpr::Symbol { text, .. } => text.trim_start_matches(['*', '^']) == label,
        SExpr::String { .. } => false,
        SExpr::List { items, .. } => items.iter().any(|item| names_label(item, label)),
    }
}
