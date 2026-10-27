//! The partial atom: an atom with the sites given so far.

use super::super::*;

impl Node<Atom> {
    /// The atom with `site` added. Added to a positive atom, a site gives a
    /// subset of its rows.
    pub fn with_site(&self, site: Site) -> Node<Atom> {
        let atom = self.value();
        let sites = atom.sites.iter().cloned().chain([site]).collect();
        Node::new(Atom { relation: atom.relation.clone(), sites })
    }
}
