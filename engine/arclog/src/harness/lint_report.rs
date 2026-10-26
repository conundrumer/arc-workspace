//! The Python lint's report over the corpus, read from the output of
//! `src/arclog_convert/lint.py --all`.

use std::path::{Path, PathBuf};

/// The Python lint's report over the corpus: the output of
/// `src/arclog_convert/lint.py --all`, whose `main` prints one line
/// `<path>:<line>: <code>: <message>` per error, then a blank line, one
/// line `  <code> <n> in <k> files` per code, and one line
/// `<clean> of <n> <suffix> files clean` per file suffix. Without `--all`,
/// over more than 20 files, the lint prints at most four error lines of
/// each code, and [`LintReport::parse`] refuses that output.
#[derive(Clone, Debug, Default)]
pub struct LintReport {
    /// Each error of the report, in the report's order.
    pub errors: Vec<LintError>,
}

/// One error of the Python lint's report.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct LintError {
    pub path: PathBuf,
    pub line: u32,
    pub check: LintCode,
    pub message: String,
}

/// The table of [`LintCode`]: each variant with its spelling in the lint's
/// report.
macro_rules! lint_codes {
    ($($variant:ident => $spelling:literal,)*) => {
        /// A code that `src/arclog_convert/lint.py` reports: one variant per
        /// code that it passes to an `err` call.
        #[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
        pub enum LintCode {
            $($variant,)*
        }

        impl LintCode {
            /// Every code, in the order of their spellings.
            pub const ALL: &[LintCode] = &[$(LintCode::$variant,)*];

            /// The code's spelling in the lint's report.
            pub fn spelling(self) -> &'static str {
                match self {
                    $(LintCode::$variant => $spelling,)*
                }
            }
        }
    };
}

lint_codes! {
    All => "all",
    AltClaim => "alt-claim",
    AltCols => "alt-cols",
    AltCombination => "alt-combination",
    AltSame => "alt-same",
    AltTail => "alt-tail",
    Alts => "alts",
    AltsEmpty => "alts-empty",
    Approximated => "approximated",
    ArcdataHead => "arcdata-head",
    ArcdataName => "arcdata-name",
    ArcdataOrder => "arcdata-order",
    Assign => "assign",
    Atom => "atom",
    BareInit => "bare-init",
    Body => "body",
    BroadcastInside => "broadcast-inside",
    Choose => "choose",
    ChooseNoNever => "choose-no-never",
    ChooseOne => "choose-one",
    Claim => "claim",
    ClaimText => "claim-text",
    Clause => "clause",
    ClauseTwice => "clause-twice",
    Column => "column",
    Component => "component",
    ConceptEmpty => "concept-empty",
    Constraint => "constraint",
    Count => "count",
    CountPlace => "count-place",
    Cycle => "cycle",
    DemoRule => "demo-rule",
    DetOrRule => "det-or-rule",
    Elide => "elide",
    EmptyGloss => "empty-gloss",
    EqMake => "eq-make",
    EqMark => "eq-mark",
    EqOrder => "eq-order",
    EqSameList => "eq-same-list",
    EqSite => "eq-site",
    EqUnexported => "eq-unexported",
    Exclude => "exclude",
    FieldCase => "field-case",
    Form => "form",
    FreshHere => "fresh-here",
    GridLayout => "grid-layout",
    HeadSite => "head-site",
    HeadZero => "head-zero",
    If => "if",
    InitOrder => "init-order",
    Input => "input",
    InputTwice => "input-twice",
    Instance => "instance",
    KeyForm => "key-form",
    KeyLocal => "key-local",
    Label => "label",
    LabelClash => "label-clash",
    Mark => "mark",
    Name => "name",
    NeverReads => "never-reads",
    NoOutput => "no-output",
    Not => "not",
    NotUndefined => "not-undefined",
    One => "one",
    OnePlace => "one-place",
    Or => "or",
    OrImplied => "or-implied",
    OrLineTwice => "or-line-twice",
    Order => "order",
    OutputTail => "output-tail",
    OwnRead => "own-read",
    Param => "param",
    ParamGrid => "param-grid",
    ParamTypes => "param-types",
    Parse => "parse",
    ParseHead => "parse-head",
    Proposer => "proposer",
    ProposerUnknown => "proposer-unknown",
    RecordField => "record-field",
    RecordPosition => "record-position",
    Recursion => "recursion",
    Relation => "relation",
    Remade => "remade",
    RemadeExport => "remade-export",
    Render => "render",
    RenderHead => "render-head",
    RenderPlace => "render-place",
    RepeatForm => "repeat-form",
    Representative => "representative",
    Rigid => "rigid",
    RigidPart => "rigid-part",
    Safety => "safety",
    SceneAlts => "scene-alts",
    SceneArclog => "scene-arclog",
    SceneBlock => "scene-block",
    SceneClaim => "scene-claim",
    SceneForm => "scene-form",
    SceneParse => "scene-parse",
    ScenePick => "scene-pick",
    SceneTaskSide => "scene-task-side",
    SharedCols => "shared-cols",
    Side => "side",
    Site => "site",
    SiteTwice => "site-twice",
    Spelling => "spelling",
    StandsUnder => "stands-under",
    Syntax => "syntax",
    TopOrder => "top-order",
    Unbound => "unbound",
    Undeclared => "undeclared",
    Wildcard => "wildcard",
    Witness => "witness",
    WitnessId => "witness-id",
    WitnessNoInput => "witness-no-input",
    WitnessNoSeparates => "witness-no-separates",
    WitnessOther => "witness-other",
    WitnessRef => "witness-ref",
    Zero => "zero",
    ZeroSite => "zero-site",
}

impl LintCode {
    /// The code whose spelling is `spelling`, where the lint has one.
    pub fn parse(spelling: &str) -> Option<LintCode> {
        LintCode::ALL.iter().copied().find(|code| code.spelling() == spelling)
    }
}

impl std::fmt::Display for LintCode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.spelling())
    }
}

/// A refusal of [`LintReport::parse`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum LintReportError {
    /// The line of number `number`, counted from 1, whose text is `text`,
    /// is no line of the report's forms, or is an error line or a summary
    /// line of a code that [`LintCode`] does not hold.
    Line { number: usize, text: String },
    /// The report holds `errors` error lines of `code`, and its summary
    /// gives `count` errors of it.
    Count { code: LintCode, errors: usize, count: usize },
}

impl std::fmt::Display for LintReportError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LintReportError::Line { number, text } => write!(f, "line {number} is no line of the lint's report: {text}"),
            LintReportError::Count { code, errors, count } => {
                write!(f, "the report holds {errors} error lines of {code}, and its summary gives {count}")
            }
        }
    }
}

impl std::error::Error for LintReportError {}

impl LintError {
    /// The error that `line` gives, where it has the form
    /// `<path>:<line>: <code>: <message>` and [`LintCode`] holds its code.
    fn parse(line: &str) -> Option<LintError> {
        let (path, rest) = line.split_once(':')?;
        let (number, rest) = rest.split_once(": ")?;
        let (check, message) = rest.split_once(": ")?;
        Some(LintError {
            path: PathBuf::from(path),
            line: number.parse().ok()?,
            check: LintCode::parse(check)?,
            message: message.to_owned(),
        })
    }
}

/// The code and the count of `line`, where it has the form
/// `  <code> <n> in <k> files` and [`LintCode`] holds its code.
fn summary_count(line: &str) -> Option<(LintCode, usize)> {
    let words: Vec<&str> = line.strip_prefix("  ")?.split_whitespace().collect();
    let [code, count, "in", files, "files"] = words[..] else { return None };
    files.parse::<usize>().ok()?;
    Some((LintCode::parse(code)?, count.parse().ok()?))
}

/// Whether `line` has the form `<clean> of <n> <suffix> files clean`.
fn is_clean_line(line: &str) -> bool {
    let words: Vec<&str> = line.split(' ').collect();
    let [clean, "of", n, suffix, "files", "clean"] = words[..] else { return false };
    clean.parse::<usize>().is_ok() && n.parse::<usize>().is_ok() && suffix.starts_with('.')
}

impl LintReport {
    /// The report that `text` gives. Refuses a line of none of the forms
    /// that [`LintReport`] gives, and a code whose error lines are not as
    /// many as its summary line gives, a code with no summary line giving
    /// none.
    pub fn parse(text: &str) -> Result<LintReport, LintReportError> {
        let mut errors = Vec::new();
        let mut counts = std::collections::BTreeMap::new();
        for (index, line) in text.lines().enumerate() {
            if let Some(error) = LintError::parse(line) {
                errors.push(error);
            } else if let Some((code, count)) = summary_count(line) {
                counts.insert(code, count);
            } else if !line.is_empty() && !is_clean_line(line) {
                return Err(LintReportError::Line { number: index + 1, text: line.to_owned() });
            }
        }
        let mut found = std::collections::BTreeMap::<LintCode, usize>::new();
        for error in &errors {
            *found.entry(error.check).or_default() += 1;
        }
        for code in LintCode::ALL {
            let errors = found.get(code).copied().unwrap_or(0);
            let count = counts.get(code).copied().unwrap_or(0);
            if errors != count {
                return Err(LintReportError::Count { code: *code, errors, count });
            }
        }
        Ok(LintReport { errors })
    }

    /// The report that the file at `path` holds, as [`LintReport::parse`]
    /// reads it. Fails where the file does not read or the parse refuses it.
    pub fn read(path: &Path) -> Result<LintReport, Box<dyn std::error::Error>> {
        Ok(LintReport::parse(&std::fs::read_to_string(path)?)?)
    }

    /// Whether the lint reports no error in the file at `path`: no error's
    /// path names the file that `path` names, once each resolves to its
    /// canonical path. An error whose path resolves to no file names none.
    /// Fails where `path` resolves to no file.
    pub fn passes(&self, path: &Path) -> std::io::Result<bool> {
        let file = std::fs::canonicalize(path)?;
        Ok(!self.errors.iter().any(|error| std::fs::canonicalize(&error.path).is_ok_and(|p| p == file)))
    }
}

#[cfg(test)]
mod tests {
    use super::{LintCode, LintReport, LintReportError};

    const WHOLE: &str = "gen/a.arclog:3: safety: X is unbound\ngen/b.arclog:7: safety: Y is unbound\ngen/b.arcdata:2: witness-no-input: witness w has no input\n\n  safety                  2 in 2 files\n  witness-no-input        1 in 1 files\n0 of 2 .arcdata files clean\n0 of 2 .arclog files clean\n";

    #[test]
    fn reads_a_whole_report() {
        let report = LintReport::parse(WHOLE).unwrap();
        let codes: Vec<LintCode> = report.errors.iter().map(|e| e.check).collect();
        assert_eq!(codes, [LintCode::Safety, LintCode::Safety, LintCode::WitnessNoInput]);
    }

    #[test]
    fn refuses_a_report_that_leaves_errors_out() {
        let cut = WHOLE.replacen("gen/b.arclog:7: safety: Y is unbound\n", "", 1);
        assert!(matches!(LintReport::parse(&cut), Err(LintReportError::Count { code: LintCode::Safety, .. })));
    }

    #[test]
    fn refuses_a_line_of_no_form_and_a_code_the_type_does_not_hold() {
        for line in ["Traceback (most recent call last):", "gen/a.arclog:3: no-such-code: X"] {
            let text = format!("{line}\n{WHOLE}");
            assert_eq!(LintReport::parse(&text).unwrap_err(), LintReportError::Line { number: 1, text: line.to_owned() });
        }
    }
}
