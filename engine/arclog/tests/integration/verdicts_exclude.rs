//! `solver_verdicts` gives a line for each case of a solver, and none for a
//! combination of alts that an `exclude` form of its arcdata file leaves out,
//! and names the relation of a `SeveralValues` verdict as the solver's file writes it.

use arclog::decode::corpus::{solver_verdicts, Verdict};
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;

const ARCLOG: &str = "\
;; pick

(RULE &output (input *P *Col))

(ALTS $cells \"which cells &extra holds\" $Whole
  (ALT $Dropped
    (RULE &extra (input *P *Col)))
  (ALT $Kept
    (RULE &extra (input *P *Col))))
";

const ARCDATA: &str = "\
;; pick

(exclude ($Dropped) \"$Dropped drops the colored cells.\")
";

#[test]
fn verdicts_leave_out_the_combinations_that_an_exclude_form_matches() {
    let dir = std::env::temp_dir().join(format!("arclog-verdicts-exclude-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 2, 1]], "output": [[1, 2, 1]]}"#;
    std::fs::write(dir.join("pick.arclog"), ARCLOG).expect("the arclog file");
    std::fs::write(dir.join("pick.arcdata"), ARCDATA).expect("the arcdata file");
    std::fs::write(dir.join("pick.json"), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let verdicts = solver_verdicts(&dir, &dir, "pick", &constructions);
    std::fs::remove_dir_all(&dir).ok();
    let cases: Vec<(String, bool)> = verdicts.expect("the solver's verdicts").into_iter().map(|case| (case.case, case.concept)).collect();
    assert_eq!(cases.len(), 2, "{cases:?}");
    assert!(cases.iter().any(|(_, concept)| *concept), "{cases:?}");
    assert!(cases.iter().any(|(case, _)| case.contains("Kept")), "{cases:?}");
    assert!(cases.iter().all(|(case, _)| !case.contains("Dropped")), "{cases:?}");
}

const SEVERAL: &str = "\
;; pick

(DET &c ColorDomain)
(RULE &output (input *P *Col) (&c (:C *Col)))
";

#[test]
fn a_verdict_of_several_values_names_the_declared_relation_as_the_file_writes_it() {
    let dir = std::env::temp_dir().join(format!("arclog-verdicts-several-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 2, 1]], "output": [[1, 2, 1]]}"#;
    std::fs::write(dir.join("pick.arclog"), SEVERAL).expect("the arclog file");
    std::fs::write(dir.join("pick.arcdata"), ";; pick\n").expect("the arcdata file");
    std::fs::write(dir.join("pick.json"), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let verdicts = solver_verdicts(&dir, &dir, "pick", &constructions);
    std::fs::remove_dir_all(&dir).ok();
    let verdicts = verdicts.expect("the solver's verdicts");
    let concept = verdicts.iter().find(|case| case.concept).expect("the concept case");
    assert_eq!(concept.verdict, Verdict::SeveralValues("&c".to_owned()), "{verdicts:?}");
}
