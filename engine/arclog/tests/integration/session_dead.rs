//! A call that panics marks its session dead: every later call on the session,
//! and on the sessions that share its state, is refused at its start, and none
//! reads the state that the panic left.

use arclog::eval::Caps;
use arclog::session::{SessionBound, SessionDead, TaskSession};

fn session() -> TaskSession {
    TaskSession::new(SessionBound { bytes: 1 << 20 }, Caps::CORPUS)
}

#[test]
fn a_call_that_ends_leaves_its_session_alive() {
    let session = session();
    drop(session.enter().expect("a live session"));
    assert!(!session.is_dead());
    assert!(session.enter().is_ok());
}

#[test]
fn a_call_that_panics_marks_its_session_and_the_sessions_that_share_its_state_dead() {
    let session = session();
    let clone = session.clone();
    let sharing_terms = session.sharing_terms();
    let own_facts = session.with_own_facts();
    let apart = self::session();
    let panicked = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let _entry = session.enter().expect("a live session");
        panic!("a call on the session panics");
    }));
    assert!(panicked.is_err());
    for held in [&session, &clone, &sharing_terms, &own_facts] {
        assert!(held.is_dead());
        assert_eq!(held.enter().err(), Some(SessionDead));
    }
    assert!(apart.enter().is_ok(), "a session of its own is not dead");
}
