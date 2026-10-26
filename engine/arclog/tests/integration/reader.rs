//! The reader refuses a head site of an input that carries `*` or `^`, or
//! holds `0`, at that label's place, in each input of an `INIT` or a
//! `DEMONSTRATED` form (`docs/arclog/arclog.md#instance`).
//!
//! The reader refuses a `^` label at each site outside the body of a key
//! clause, at that label's place, and reads one at any depth of a key
//! clause's body.

use arclog::diagnostic::{Diagnostic, Location};
use arclog::layout::SourceFile;
use arclog::read::read_arclog;

/// Programs whose one input has the head site `SITE`: an input of an
/// `INIT` form and of a `DEMONSTRATED` form, each before and inside its
/// key clause.
const PROGRAMS: [&str; 4] = [
    "(RULE &cells (input *P *Col))\n\
     (INIT &obj Connectivity\n\
       (node (SITE)\n\
         (&cells *P *Col)))\n",
    "(RULE &cells (input *P *Col))\n\
     (INIT &obj Connectivity\n\
       (key ((&cells ^E *Q))\n\
         (node (SITE)\n\
           (&cells E *P))))\n",
    "(RULE &cells (input *P *Col))\n\
     (DEMONSTRATED &catalog\n\
       (value (SITE)\n\
         (&cells *P *Col)))\n",
    "(RULE &cells (input *P *Col))\n\
     (DEMONSTRATED &catalog\n\
       (key ((&cells ^E *Q))\n\
         (value (SITE)\n\
           (&cells E *P))))\n",
];

/// Each program with `site` at `SITE`, and the byte offset of `label`,
/// which `site` holds once.
fn programs<'a>(site: &'a str, label: &str) -> impl Iterator<Item = (String, u32)> + 'a {
    let within = site.find(label).expect("the site holds the label");
    PROGRAMS.into_iter().map(move |program| {
        let at = program.find("SITE").expect("the program has a head site");
        (program.replacen("SITE", site, 1), (at + within) as u32)
    })
}

fn diagnostics(text: &str) -> Vec<Diagnostic> {
    read_arclog(text, SourceFile::Arclog).expect("the program reads as s-expressions").diagnostics
}

fn starts(diagnostics: &[Diagnostic]) -> Vec<u32> {
    diagnostics
        .iter()
        .flat_map(|diagnostic| match &diagnostic.location {
            Location::Places(places) => places.iter().map(|place| place.place.start).collect(),
            Location::Path(_) => Vec::new(),
        })
        .collect()
}

#[test]
fn a_head_site_that_carries_a_mark_or_holds_zero_is_refused_at_the_label() {
    for (site, label) in [("*X", "*X"), ("(:t *X)", "*X"), ("(:t 0)", "0"), ("(:t (:a *X))", "*X"), ("(:t (:a 0))", "0"), ("^X", "^X"), ("(:t ^X)", "^X"), ("(:t (:a ^X))", "^X")] {
        for (text, at) in programs(site, label) {
            assert!(starts(&diagnostics(&text)).contains(&at), "{text}");
        }
    }
}

/// Programs that hold `^X` once, at a site outside the body of a key
/// clause.
const OUTSIDE_A_KEY_BODY: [&str; 13] = [
    "(RULE &cells (input ^X *Col))\n",
    "(RULE &cells (input (:P (:a ^X)) *Col))\n",
    "(RULE &cells (input *P *Col) (IF ((input (:P ^X))) ((input P)) ((input P))))\n",
    "(RULE &cells (input *P *Col) (OR ((input (:P ^X))) ((input P))))\n",
    "(RULE &cells (input *P *Col) (ALL ((input (:P ^X))) ((input P))))\n",
    "(RULE &cells (input *P *Col) (NOT (input (:P ^X))))\n",
    "(RULE &cells (input *P *Col))\n\
     (INIT &obj Connectivity\n\
       (node (P)\n\
         (&cells *P (:Col ^X))))\n",
    "(RULE &cells (input *P *Col))\n\
     (INIT &obj Connectivity\n\
       (key ((&cells ^E *Q))\n\
         (node (P)\n\
           (&cells E *P (:Col ^X)))))\n",
    "(RULE &cells (input *P *Col))\n\
     (DEMONSTRATED &catalog\n\
       (value (P)\n\
         (&cells *P (:Col ^X))))\n",
    "(RULE &cells (input *P *Col))\n\
     (DEMONSTRATED &catalog\n\
       (key ((&cells ^E *Q))\n\
         (value (P)\n\
           (&cells E *P (:Col ^X)))))\n",
    "(RULE &cells (input *P *Col))\n\
     (CHOOSE &pick\n\
       (from (&cells ^X *Col)))\n",
    "(RULE &cells (input *P *Col))\n\
     (CHOOSE &pick\n\
       (for ((&cells *P))\n\
         (from (&cells P (:Col ^X)))))\n",
    "(RULE &cells (input *P *Col))\n\
     (RIGID_DET &piece\n\
       (&cells ^X))\n",
];

/// Programs that hold `^X` at depth in the body of a key clause, inside an
/// `OR` of that body as well.
const IN_A_KEY_BODY: [&str; 5] = [
    "(RULE &cells (input *P *Col))\n\
     (INIT &obj Connectivity\n\
       (key ((&cells (:P (:a ^X)) *Q))\n\
         (node (P)\n\
           (&cells (:P (:a X)) *P))))\n",
    "(RULE &cells (input *P *Col))\n\
     (INIT &obj Connectivity\n\
       (key ((&cells *Q) (OR ((&cells Q (:Col (:a ^X)))) ((&cells Q (:Col (:a X))))))\n\
         (node (P)\n\
           (&cells X *P))))\n",
    "(RULE &cells (input *P *Col))\n\
     (DEMONSTRATED &catalog\n\
       (key ((&cells (:P (:a ^X)) *Q))\n\
         (value (P)\n\
           (&cells (:P (:a X)) *P))))\n",
    "(RULE &cells (input *P *Col))\n\
     (CHOOSE &pick\n\
       (for ((&cells (:P (:a ^X))))\n\
         (from (&cells (:P (:a X)) *Col))))\n",
    "(RULE &cells (input *P *Col))\n\
     (RIGID_DET &piece\n\
       (key ((&cells (:P (:a ^X))))\n\
         (&cells (:P (:a X)))))\n",
];

#[test]
fn a_key_label_outside_a_key_body_is_refused_at_the_label() {
    for text in OUTSIDE_A_KEY_BODY {
        let at = text.find("^X").expect("the program holds `^X`") as u32;
        assert!(starts(&diagnostics(text)).contains(&at), "{text}");
    }
}

#[test]
fn a_key_label_at_depth_in_a_key_body_is_read() {
    for text in IN_A_KEY_BODY {
        assert_eq!(diagnostics(text), Vec::new(), "{text}");
    }
}
