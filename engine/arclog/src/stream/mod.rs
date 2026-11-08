//! The token stream of a program, as `docs/engine/arclog-stream.md#token-stream`
//! gives it: its tokens in [`token`], the decode settings in [`settings`],
//! the ids of the tokens in [`vocabulary`], and the writer from a case
//! program to its stream in [`write`](mod@write).

pub mod corpus;
pub(crate) mod demonstrated;
pub mod settings;
pub mod token;
pub mod vocabulary;
pub mod write;

pub use settings::{DecodeSettings, VocabularyCaps, MEASURED_CAP};
pub use token::{Control, Emitter, Token, TokenKind};
pub use vocabulary::Vocabulary;
pub use write::{token_stream, token_stream_with_paths, written_stream, WrittenStream};
