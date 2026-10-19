//! The writes of a form through a name writer other than [`AsWritten`],
//! kept on the form's node, each with the bytes that each call of its name
//! writer appended. A write's bytes depend on the form and on those bytes
//! alone, so a later write of the form whose name writer appends the same
//! bytes for each of those calls gives the kept form.

use std::sync::Mutex;

use super::*;

/// The writes a node keeps. A node keeps at most [`CACHED_WRITES`], the
/// latest first.
#[derive(Debug, Default)]
pub(super) struct WriteCache(Mutex<Vec<CachedWrite>>);

/// The number of writes a node keeps.
const CACHED_WRITES: usize = 8;

/// One write: each call its name writer took, with the bytes it appended,
/// and the form written.
#[derive(Debug)]
struct CachedWrite {
    calls: Box<[(NameCall, Box<[u8]>)]>,
    form: CanonicalForm,
}

/// A call of a [`NameWriter`], by its arguments.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
enum NameCall {
    Name(RelationRef),
    Own(DeclaredName),
    Column(RelationRef, Box<[ColumnName]>),
}

impl NameCall {
    /// The bytes `names` appends on this call.
    fn bytes(&self, names: &dyn NameWriter) -> Vec<u8> {
        let mut out = CanonicalWriter::default();
        match self {
            NameCall::Name(relation) => names.write_name(relation, &mut out),
            NameCall::Own(name) => names.write_own(name, &mut out),
            NameCall::Column(relation, column) => names.write_column(relation, column, &mut out),
        }
        out.bytes
    }
}

/// A name writer that records each distinct call of the writer it wraps,
/// with the bytes that writer appended.
struct Recording<'n> {
    names: &'n dyn NameWriter,
    calls: std::cell::RefCell<StableHashMap<NameCall, Box<[u8]>>>,
}

impl Recording<'_> {
    fn call(&self, call: NameCall, out: &mut CanonicalWriter) {
        if let Some(bytes) = self.calls.borrow().get(&call) {
            return out.write(bytes);
        }
        let bytes = call.bytes(self.names);
        out.write(&bytes);
        self.calls.borrow_mut().insert(call, bytes.into());
    }
}

impl NameWriter for Recording<'_> {
    fn write_name(&self, relation: &RelationRef, out: &mut CanonicalWriter) {
        self.call(NameCall::Name(relation.clone()), out);
    }

    fn write_own(&self, name: &DeclaredName, out: &mut CanonicalWriter) {
        self.call(NameCall::Own(name.clone()), out);
    }

    fn write_column(&self, relation: &RelationRef, column: &[ColumnName], out: &mut CanonicalWriter) {
        self.call(NameCall::Column(relation.clone(), column.into()), out);
    }
}

/// The form `write` gives through `names`, a write of `form`, or the form
/// of a write that the node of `form` keeps whose every call `names`
/// answers with the same bytes. `write` writes `form` alone and reads no
/// name but through the name writer it is given.
pub(crate) fn cached_write(form: &Form, names: &dyn NameWriter, write: impl FnOnce(&dyn NameWriter) -> CanonicalForm) -> CanonicalForm {
    let cache = &super::form::cache(form).writes.0;
    let matches = |found: &CachedWrite| found.calls.iter().all(|(call, bytes)| call.bytes(names)[..] == bytes[..]);
    if let Some(found) = cache.lock().expect("no write panics while it holds the cached writes").iter().find(|found| matches(found)) {
        return found.form.clone();
    }
    let recording = Recording { names, calls: Default::default() };
    let form_written = write(&recording);
    let calls: Box<[(NameCall, Box<[u8]>)]> = recording.calls.into_inner().into_iter().collect();
    let mut cached = cache.lock().expect("no write panics while it holds the cached writes");
    cached.insert(0, CachedWrite { calls, form: form_written.clone() });
    cached.truncate(CACHED_WRITES);
    form_written
}
