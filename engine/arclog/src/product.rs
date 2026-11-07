//! The lazy product of sequences whose elements are found as the product
//! reaches them, in lexicographic order, the first factor the most
//! significant: from one element, the last factor that has a next element
//! takes it, and each factor after it goes back to its first.

/// A product over `factors`, and where it stands in its elements.
pub(crate) struct Product<F> {
    factors: Vec<F>,
    state: State,
}

/// Where a [`Product`] stands in its elements.
enum State {
    /// No element is given yet.
    Before,
    /// The position of each factor's element in the last element given.
    At(Vec<usize>),
    /// The last element is given.
    Past,
}

impl<F> Product<F> {
    pub(crate) fn new(factors: Vec<F>) -> Self {
        Product { factors, state: State::Before }
    }

    /// The factors.
    pub(crate) fn factors(&self) -> &[F] {
        &self.factors
    }

    /// The next element, each factor with the position of its element in
    /// it, or `None` past the last. `has` reports whether a factor has an
    /// element at an index, finding it where needed.
    ///
    /// The first call calls `has` for every factor at index 0, with no stop
    /// at a factor that has none, and gives each factor at position 0 where
    /// each has an element there. A product of no factors has one element.
    /// Where `has` returns an error, `next` returns it and stands where it
    /// stood.
    pub(crate) fn next<E>(&mut self, mut has: impl FnMut(&mut F, usize) -> Result<bool, E>) -> Result<Option<impl Iterator<Item = (&F, usize)>>, E> {
        match &mut self.state {
            State::Before => {
                let mut all = true;
                for factor in &mut self.factors {
                    all &= has(factor, 0)?;
                }
                self.state = if all { State::At(vec![0; self.factors.len()]) } else { State::Past };
            }
            State::At(positions) => {
                let mut moved = false;
                for at in (0..self.factors.len()).rev() {
                    if has(&mut self.factors[at], positions[at] + 1)? {
                        positions[at] += 1;
                        positions[at + 1..].fill(0);
                        moved = true;
                        break;
                    }
                }
                if !moved {
                    self.state = State::Past;
                }
            }
            State::Past => {}
        }
        Ok(match &self.state {
            State::At(positions) => Some(self.factors.iter().zip(positions.iter().copied())),
            State::Before | State::Past => None,
        })
    }
}
