//! The reader of the two lib files, which reads each form into the
//! registry's records and gives a diagnostic at the form of each fault: the
//! reader's state and its helpers, the completeness check of the accessors
//! and the assembly of the registry.

use super::records::{ArclogProposer, BodyInFile, WrittenRelation};
use super::*;
use super::spellings::*;

/// The reader of the two lib files. It reads each form whatever an earlier
/// one gave, and adds each fault of either file to one list.
#[derive(Default)]
pub(super) struct FileReader {
    pub(super) diagnostics: Vec<crate::diagnostic::Diagnostic>,
    pub(super) entries: StableHashMap<LibName, LibEntry>,
    /// Each name that a form of the entries declares, a relation macro's and
    /// an arclog proposer's among them, which take their entries later.
    pub(super) declared: StableHashSet<LibName>,
    pub(super) constants: StableHashMap<OrientationType, TypeConstants>,
    /// The names of the `C4` form, and its place.
    pub(super) c4: Option<(Box<[Box<str>]>, SourcePlace)>,
    pub(super) facts: StableHashMap<FactRelation, Box<[Column]>>,
    pub(super) relation_macros: Vec<WrittenRelation>,
    /// Each `(proposer <name> arclog (columns ...))` form, in file order.
    pub(super) arclog_proposers: Vec<ArclogProposer>,
    /// Each proposer written in arclog with its clause, in file order,
    /// before its declaration.
    pub(super) proposer_clauses: Vec<WrittenRelation>,
    pub(super) bodies: Vec<BodyInFile>,
}

impl FileReader {
    pub(super) fn fault(&mut self, check: CheckId, message: impl Into<Box<str>>, place: SourcePlace) {
        self.diagnostics.push(check_error(check, message, place));
    }

    /// Gives a diagnostic of the grammar, and `None`.
    pub(super) fn refuse<T>(&mut self, message: impl Into<Box<str>>, place: SourcePlace) -> Option<T> {
        self.fault(CheckId::Grammar, message, place);
        None
    }

    /// `result`'s value, or `None` with its diagnostics added.
    pub(super) fn read<T>(&mut self, result: Result<T, Vec<crate::diagnostic::Diagnostic>>) -> Option<T> {
        result.map_err(|diagnostics| self.diagnostics.extend(diagnostics)).ok()
    }

    /// The s-expressions of `text`, none where it does not read.
    pub(super) fn sexprs(&mut self, text: &str, file: SourceFile) -> Vec<SExpr> {
        self.read(read_sexprs(text, file)).map(|(exprs, _)| exprs).unwrap_or_default()
    }

    pub(super) fn symbol<'e>(&mut self, expr: Option<&'e SExpr>, what: &str, at: SourcePlace) -> Option<&'e str> {
        match expr {
            Some(SExpr::Symbol { text, .. }) => Some(text),
            Some(other) => self.refuse(format!("{what} is a symbol"), other.place()),
            None => self.refuse(format!("the form lacks {what}"), at),
        }
    }

    /// The items after the head of `expr`, a list headed by `head`.
    pub(super) fn headed<'e>(&mut self, expr: Option<&'e SExpr>, head: &str, at: SourcePlace) -> Option<&'e [SExpr]> {
        match expr {
            Some(expr) => match headed(expr, head) {
                Some(rest) => Some(rest),
                None => self.refuse(format!("a `({head} ...)` form stands here"), expr.place()),
            },
            None => self.refuse(format!("the form lacks its `({head} ...)` form"), at),
        }
    }

    /// Gives a diagnostic of the grammar at the first item of `exprs`, an
    /// item the form has no place for, and `None`; `Some(())` where `exprs`
    /// is empty.
    pub(super) fn no_more(&mut self, exprs: &[SExpr]) -> Option<()> {
        match exprs.first() {
            Some(expr) => self.refuse("the form has no place for this item", expr.place()),
            None => Some(()),
        }
    }

    /// Each relation macro, then each proposer written in arclog with its
    /// clause, before its declaration.
    pub(super) fn written_relations(&self) -> impl Iterator<Item = &WrittenRelation> {
        self.relation_macros.iter().chain(&self.proposer_clauses)
    }

    /// Records that a form at `place` declares `name`, or gives a fault
    /// where another form declares it.
    pub(super) fn declare(&mut self, name: &LibName, place: SourcePlace) -> bool {
        if self.declared.insert(name.clone()) {
            return true;
        }
        self.fault(CheckId::Scope, format!("`{}` is declared by two forms", name.0), place);
        false
    }

    /// Gives a diagnostic where an accessor of the registry would have no
    /// value to give: an orientation type with no `constants` form, no `C4`
    /// form or a `C4` constant that is no D4 constant, or a fact relation
    /// with no `fact` form.
    pub(super) fn check_complete(&mut self) {
        let start = file_start(SourceFile::LibRegistry);
        for (name, text) in spelling::TYPE_NAMES {
            if orientation_type(*name).is_some_and(|ty| !self.constants.contains_key(&ty)) {
                self.fault(CheckId::Scope, format!("the file has no `constants` form of `{text}`"), start);
            }
        }
        match &self.c4 {
            Some((names, place)) => {
                let d4 = self.constants.get(&OrientationType::D4);
                let outside: Vec<String> = names
                    .iter()
                    .filter(|name| d4.is_none_or(|d4| !d4.names.contains(name)))
                    .map(|name| format!("the `C4` constant `{name}` is no `D4` constant"))
                    .collect();
                let place = *place;
                for message in outside {
                    self.fault(CheckId::Scope, message, place);
                }
            }
            None => self.fault(CheckId::Scope, "the file has no `C4` form", start),
        }
        for (fact, text) in spelling::FACT_RELATIONS {
            if !self.facts.contains_key(fact) {
                self.fault(CheckId::Scope, format!("the file has no `fact` form of `{text}`"), start);
            }
        }
    }

    /// The registry read, or the diagnostics of each fault of either file.
    pub(super) fn registry(self) -> Result<Registry, RegistryError> {
        if !self.diagnostics.is_empty() {
            return Err(RegistryError { diagnostics: self.diagnostics });
        }
        let d4 = self.constants.get(&OrientationType::D4).expect("`check_complete` faults where `D4` has no `constants` form");
        let (names, _) = self.c4.as_ref().expect("`check_complete` faults where the file has no `C4` form");
        let c4 = names.iter().filter_map(|name| d4.constant(OrientationType::D4, name)).collect();
        Ok(Registry {
            entries: self.entries,
            constants: self.constants,
            c4: ConstantSet { constants: c4 },
            facts: self.facts,
        })
    }
}
