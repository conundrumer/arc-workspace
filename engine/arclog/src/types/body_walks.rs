//! The walks over a body's sites and conjuncts, which the checks and the
//! type of a label read: the label uses at a site with their column paths,
//! and the conjuncts and atoms of a body at any depth.

/// Visits each label use at `site`, at any depth, as [`each_site_label`]
/// does, without building its column path.
pub fn each_site_use(site: &crate::program::Site, visit: &mut dyn FnMut(crate::program::LabelUse)) {
    use crate::program::SiteArg;
    for arg in site.value.args.iter() {
        match arg {
            SiteArg::Label(use_) | SiteArg::NamedLabel { label: use_, .. } => visit(*use_),
            SiteArg::Field(field) => each_site_use(field, visit),
        }
    }
}

/// Visits each label use at `site`, at any depth of the site, with its
/// column path, as [`super::label_type`] gives it, after `path`.
pub fn each_site_label(
    site: &crate::program::Site,
    path: &mut Vec<crate::program::ColumnName>,
    visit: &mut dyn FnMut(crate::program::LabelUse, &[crate::program::ColumnName]),
) {
    use crate::program::SiteArg;
    path.push(site.column.clone());
    for arg in site.value.args.iter() {
        match arg {
            SiteArg::Label(use_) => visit(*use_, path),
            SiteArg::NamedLabel { name, label } => {
                path.push(name.clone());
                visit(*label, path);
                path.pop();
            }
            SiteArg::Field(field) => each_site_label(field, path, visit),
        }
    }
    path.pop();
}

/// The label of a label use, where it has one.
pub fn use_label(use_: crate::program::LabelUse) -> Option<crate::program::LabelId> {
    use crate::program::LabelUse;
    match use_ {
        LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => Some(label),
        LabelUse::Zero => None,
    }
}

/// Visits each conjunct of `body` at any depth, a conjunct inside a `NOT`
/// included.
pub fn each_conjunct(body: &crate::program::Body, visit: &mut dyn FnMut(&crate::program::Conjunct)) {
    use crate::program::{Conjunct, Negated};
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

/// Visits each atom of `body` at any depth, a negated atom included.
pub fn each_atom(body: &crate::program::Body, visit: &mut dyn FnMut(&crate::program::Atom)) {
    each_conjunct(body, &mut |conjunct| {
        if let Some(atom) = conjunct.atom() {
            visit(atom.value());
        }
    });
}

/// The label that `atom` gives at its site on `column`, a column of one
/// label.
pub(crate) fn column_label(atom: &crate::program::Atom, column: &crate::program::ColumnName) -> Option<crate::program::LabelId> {
    let site = atom.sites.iter().find(|site| site.column == *column)?;
    match &site.value.args[..] {
        [arg] => arg.label().and_then(use_label),
        _ => None,
    }
}
