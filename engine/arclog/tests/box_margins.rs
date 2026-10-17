//! `Term::encode` refuses a Box with a margin outside a signed byte, since a
//! silent wrap would give a wrong Box with no error.

use arclog::terms::{Margins, ReachedMarginBound, Term};

fn margins(top: i32) -> Margins {
    Margins { top, bottom: 0, left: 0, right: 0 }
}

#[test]
fn a_margin_outside_a_byte_is_refused() {
    for top in [128, -129] {
        assert_eq!(Term::Box(margins(top)).encode(), Err(ReachedMarginBound { margins: margins(top) }));
    }
}

#[test]
fn a_margin_at_the_bounds_of_a_byte_is_encoded() {
    for top in [-128, 127] {
        let id = Term::Box(margins(top)).encode().expect("a margin within a byte");
        assert_eq!(Term::decode(id, &arclog::types::ValueType::Box), Term::Box(margins(top)));
    }
}
