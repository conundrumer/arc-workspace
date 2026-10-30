//! The naming of the labels that a program form and a trace form give to the
//! labels the engine makes at a site.

/// The name of a label made at a site on the column `base`: the column's name
/// in PascalCase, with the least digit suffix from 2 that `taken` does not
/// refuse where the name itself is taken.
pub(crate) fn label_name(base: &str, taken: impl Fn(&str) -> bool) -> String {
    let base = pascal_case(base);
    if !taken(&base) {
        return base;
    }
    (2..).map(|n| format!("{base}{n}")).find(|name| !taken(name)).expect("an unbounded range")
}

/// `text` with the first letter of each part between `_` and `-` upper case.
fn pascal_case(text: &str) -> String {
    text.split(['_', '-'])
        .map(|part| {
            let mut chars = part.chars();
            chars.next().map(|first| first.to_uppercase().chain(chars).collect::<String>()).unwrap_or_default()
        })
        .collect()
}
