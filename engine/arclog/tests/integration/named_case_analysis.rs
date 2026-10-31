//! A caller that asks for the cases of a solver one at a time gets each from one
//! analysis of the solver, as long as the solver's files stand as they were, and
//! each stream is the stream that asking for all the cases gives.

use std::path::{Path, PathBuf};
use std::rc::Rc;

use arclog::registry::Registry;
use arclog::stream::corpus::{shared_analysis, solver_streams, token_ids, SolverAnalysis, WantedCases};
use arclog::stream::{DecodeSettings, Vocabulary, WrittenStream};

const ARCLOG: &str = "\
;; pick

(RULE &output (input *P *Col))

(ALTS $cells \"which cells &extra holds\" $Whole
  (ALT $Dropped
    (RULE &extra (input *P *Col)))
  (ALT $Kept
    (RULE &extra (input *P *Col))))

(OUT (&output ^P ^Col))
";

const WIDER: &str = "\
;; pick

(RULE &output (input *P *Col))

(ALTS $cells \"which cells &extra holds\" $Whole
  (ALT $Dropped
    (RULE &extra (input *P *Col)))
  (ALT $Kept
    (RULE &extra (input *P *Col)))
  (ALT $Spare
    (RULE &extra (input *P *Col))))

(OUT (&output ^P ^Col))
";

/// A corpus directory that holds the solver `pick`, and is removed where the value drops.
struct Corpus(PathBuf);

impl Corpus {
    fn new(name: &str) -> Self {
        let dir = std::env::temp_dir().join(format!("arclog-{name}-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("a temporary directory");
        std::fs::write(dir.join("pick.arclog"), ARCLOG).expect("the arclog file");
        std::fs::write(dir.join("pick.arcdata"), ";; pick\n").expect("the arcdata file");
        Corpus(dir)
    }

    fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for Corpus {
    fn drop(&mut self) {
        std::fs::remove_dir_all(&self.0).ok();
    }
}

#[test]
fn the_cases_asked_one_at_a_time_come_from_one_analysis_and_give_the_streams_of_all_the_cases() {
    let corpus = Corpus::new("named-case-analysis");
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let all = solver_streams(corpus.path(), "pick", WantedCases::All, &vocabulary, false).expect("the solver's streams");
    assert_eq!(all.len(), 3, "{:?}", all.iter().map(|case| &case.case).collect::<Vec<_>>());
    let first = shared_analysis(corpus.path(), "pick").expect("the analysis");
    let ids = |stream: &Result<WrittenStream, String>| stream.as_ref().map(|written| token_ids(&written.tokens, &vocabulary)).map_err(String::clone);
    for case in &all {
        let analysis = shared_analysis(corpus.path(), "pick").expect("the analysis");
        assert!(Rc::ptr_eq(&first, &analysis), "{}", case.case);
        let named = analysis.streams(corpus.path(), "pick", WantedCases::Named(&case.case), &vocabulary, false).expect("the named case");
        assert_eq!(named.len(), 1, "{}", case.case);
        let named = &named[0];
        assert_eq!(named.case, case.case);
        assert_eq!(named.concept, case.concept, "{}", case.case);
        assert_eq!(named.labels, case.labels, "{}", case.case);
        assert_eq!(ids(&named.stream), ids(&case.stream), "{}", case.case);
    }
}

#[test]
fn an_analysis_is_read_again_where_a_file_of_the_solver_changes_or_the_solver_is_another() {
    let corpus = Corpus::new("named-case-analysis-changed");
    let vocabulary = Vocabulary::new(Registry::get(), &DecodeSettings::default());
    let cases = |analysis: &SolverAnalysis, id: &str| analysis.streams(corpus.path(), id, WantedCases::All, &vocabulary, false).expect("the streams").len();
    let first = shared_analysis(corpus.path(), "pick").expect("the analysis");
    assert_eq!(cases(&first, "pick"), 3);

    std::fs::write(corpus.path().join("pick.arclog"), WIDER).expect("the arclog file");
    let second = shared_analysis(corpus.path(), "pick").expect("the analysis");
    assert!(!Rc::ptr_eq(&first, &second));
    assert_eq!(cases(&second, "pick"), 4);

    let again = shared_analysis(corpus.path(), "pick").expect("the analysis");
    assert!(Rc::ptr_eq(&second, &again));

    std::fs::write(corpus.path().join("other.arclog"), ARCLOG).expect("the arclog file");
    std::fs::write(corpus.path().join("other.arcdata"), ";; other\n").expect("the arcdata file");
    let other = shared_analysis(corpus.path(), "other").expect("the analysis");
    assert!(!Rc::ptr_eq(&second, &other));
    assert_eq!(cases(&other, "other"), 3);
}

#[test]
fn a_solver_whose_files_do_not_read_gives_the_fault_and_no_analysis() {
    let corpus = Corpus::new("named-case-analysis-absent");
    let fault = shared_analysis(corpus.path(), "absent").err().expect("the files are absent");
    assert!(fault.starts_with("the solver's files do not read: "), "{fault}");
}
