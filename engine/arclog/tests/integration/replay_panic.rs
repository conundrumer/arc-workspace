//! A panic in the replay of one solver of a corpus is that solver's fault,
//! and the replay of another solver gives its record.

use arclog::decode::corpus::replay_solver;
use arclog::stream::DecodeSettings;
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;

const ARCLOG: &str = "\
;; tie

(DET &seed RarestColor)

(RULE &seed_cell
  (input *P *Col)
  (&seed (:C Col)))

(INIT &state Unfold
  (start ((:t P))
    (&seed_cell *P))
  (initial_untaken ((:item P))
    (input *P)
    (NOT (&seed_cell P)))
  (score ((:t P) (:item X) (:S K))
    (&seed_cell *P)
    (input (:P *X))
    (NOT (&seed_cell (:P X)))
    (= *K 0)))

(RULE &taken
  (&state.take (:item *P)))

(RULE &output
  (OR ((input *P *Col)
       (NOT (&taken P)))
      ((&taken P)
       (&seed (:C Col)))))

(OUT (&output ^P ^Col))
";

const ARCDATA: &str = "\
;; tie

(param &seed Color (2))
";

#[test]
fn a_panic_in_a_replay_is_the_fault_of_its_solver() {
    let dir = std::env::temp_dir().join(format!("arclog-replay-panic-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 2, 1]], "output": [[2, 2, 1]]}"#;
    for id in ["tie", "calm"] {
        std::fs::write(dir.join(format!("{id}.arclog")), ARCLOG).expect("the arclog file");
        std::fs::write(dir.join(format!("{id}.arcdata")), ARCDATA).expect("the arcdata file");
        std::fs::write(dir.join(format!("{id}.json")), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    }
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let panicking = replay_solver(&dir, &dir, "tie", false, &constructions, &DecodeSettings::default(), false, &|_: &mut usize, _, _| panic!("the construction's inputs break its domain"));
    let calm = replay_solver(&dir, &dir, "calm", false, &constructions, &DecodeSettings::default(), false, &|steps: &mut usize, _, _| *steps += 1);
    std::fs::remove_dir_all(&dir).ok();
    let fault = panicking.err().expect("the panic is the solver's fault");
    assert!(fault.contains("the construction's inputs break its domain"), "{fault}");
    let calm = calm.expect("the other solver replays");
    assert!(calm.cases[0].outcome.as_ref().is_ok_and(|steps| *steps > 0), "{calm:?}");
}
