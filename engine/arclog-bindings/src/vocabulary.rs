//! The vocabulary of a decode, as Python gives it.


use arclog::hash::StableHashMap;
use arclog::stream::Vocabulary;
use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;

/// The token ids of a decode and their names. The name of a token is its
/// spelling in `docs/engine/arclog-stream.md#token-stream`: a control token's text,
/// a lib relation, relation macro, component, proposer or fact relation's
/// name, and `&r<slot>`, `:<position>` or `L<slot>` for a relation, column
/// or label slot. The kind of a token is `control`, `lib relation`,
/// `relation macro`, `component`, `proposer`, `fact relation`, `relation`,
/// `column` or `label`.
#[pyclass(name = "Vocabulary", frozen, module = "arclog")]
pub(crate) struct PyVocabulary {
    names: Box<[String]>,
    kinds: Box<[&'static str]>,
    ids: StableHashMap<String, u32>,
}

impl PyVocabulary {
    pub(crate) fn of(vocabulary: &Vocabulary<'_>) -> PyVocabulary {
        let names: Box<[String]> = (0..vocabulary.len() as u32).map(|id| vocabulary.token(id).expect("an id of the vocabulary").to_string()).collect();
        let ids = names.iter().enumerate().map(|(id, name)| (name.clone(), id as u32)).collect();
        let kinds = (0..vocabulary.len() as u32).map(|id| vocabulary.kind(id).expect("an id of the vocabulary").spelling()).collect();
        PyVocabulary { names, kinds, ids }
    }
}

#[pymethods]
impl PyVocabulary {
    fn __len__(&self) -> usize {
        self.names.len()
    }

    /// The name of the token with id `id`: its spelling in the token stream, as the class documents.
    fn name(&self, id: u32) -> PyResult<&str> {
        self.names.get(id as usize).map(String::as_str).ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))
    }

    /// The kind of the token with id `id`, as the class documents.
    fn kind(&self, id: u32) -> PyResult<&'static str> {
        self.kinds.get(id as usize).copied().ok_or_else(|| PyIndexError::new_err(format!("no token with id {id}")))
    }

    /// The id of the token named `name`, or `None` where the vocabulary holds no such token.
    fn id(&self, name: &str) -> Option<u32> {
        self.ids.get(name).copied()
    }
}
