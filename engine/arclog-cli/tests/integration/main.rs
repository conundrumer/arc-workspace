//! The integration tests of `arclog-cli`, built as the one test binary `integration`.
//! A new test goes in as a file `<name>.rs` beside this one and a line `mod <name>;` below,
//! not as a file at the top of `tests/`, which would build as a binary of its own.

mod instance_key_join;
mod keyed_input;
