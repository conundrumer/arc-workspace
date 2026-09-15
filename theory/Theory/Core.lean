/-!
# Core

The core of the solver theory: a model, a fit, a family, equivalent
models, equivariance, a case, and a parameterization as a product.

A model is `Θ → G → Option G`. `none` is an ill-formed output: `out` is not a
grid, not total, or multi-valued. Grids and assignments are opaque.

A task splits into the evidence and the test outputs. The evidence is the train
pairs and the test inputs. A case's stored assignment reads the evidence
only. The test outputs are held out, and they enter through `Fit`.
-/

namespace Core

/-- `M : Θ × G ⇀ G`. -/
abbrev Model (Θ G : Type) := Θ → G → Option G

/-- The evidence a case may read: the train pairs and the test inputs. -/
structure Given (G : Type) where
  train : List (G × G)
  testIn : List G

/-- A task: the evidence plus the test outputs. -/
structure Task (G : Type) where
  given : Given G
  testOut : List G

/-- Every pair of a task, test pairs included. -/
def Task.pairs (T : Task G) : List (G × G) :=
  T.given.train ++ List.zip T.given.testIn T.testOut

variable {Θ Θ₁ Θ₂ G : Type}

/-- `M(θ, x)↓`. -/
def Defined (M : Model Θ G) (θ : Θ) (x : G) : Prop := (M θ x).isSome

/-- `M(θ) ⊨ T`. -/
def Fits (M : Model Θ G) (θ : Θ) (T : Task G) : Prop :=
  ∀ p ∈ T.pairs, M θ p.1 = some p.2

/-- `fam(M) = { T : ∃θ. M(θ) ⊨ T }`, as a predicate on tasks. -/
def Fam (M : Model Θ G) (T : Task G) : Prop := ∃ θ, Fits M θ T

/-- Equivalent models, within one parameterization: the same outputs for every
input under every assignment. -/
def Equivalent (A B : Model Θ G) : Prop := ∀ θ x, A θ x = B θ x

/-- A divergence witness at one assignment refutes equivalence. -/
theorem not_equivalent_of_witness {A B : Model Θ G}
    (h : ∃ θ x, A θ x ≠ B θ x) : ¬ Equivalent A B := by
  intro hs
  obtain ⟨θ, x, hne⟩ := h
  exact hne (hs θ x)

/-- An isomorphism of parameterizations: a bijection between their
assignments. -/
structure Iso (Θ₁ Θ₂ : Type) where
  to : Θ₁ → Θ₂
  inv : Θ₂ → Θ₁
  left_inv : ∀ θ, inv (to θ) = θ
  right_inv : ∀ θ, to (inv θ) = θ

/-- Equivalent models across two parameterizations: some isomorphism of the
parameterizations carries every assignment of one to an assignment of the
other on which the outputs agree for every input. -/
def EquivalentAcross (A : Model Θ₁ G) (B : Model Θ₂ G) : Prop :=
  ∃ e : Iso Θ₁ Θ₂, ∀ θ x, A θ x = B (e.to θ) x

/-- Within one parameterization, the identity isomorphism makes the two
readings agree. -/
theorem equivalentAcross_of_equivalent {A B : Model Θ G} (h : Equivalent A B) :
    EquivalentAcross A B :=
  ⟨⟨id, id, fun _ => rfl, fun _ => rfl⟩, h⟩

/-- A divergence witness under every isomorphism of the parameterizations
refutes equivalence across them. -/
theorem not_equivalentAcross_of_witness {A : Model Θ₁ G} {B : Model Θ₂ G}
    (h : ∀ e : Iso Θ₁ Θ₂, ∃ θ x, A θ x ≠ B (e.to θ) x) : ¬ EquivalentAcross A B := by
  intro ⟨e, hs⟩
  obtain ⟨θ, x, hne⟩ := h e
  exact hne (hs θ x)

/-! ## Equivariance

`∀g ∈ Γ. M(g·θ, g·x) = g·M(θ, x)`, with Γ acting on assignments and grids. -/

structure Action (Γ Θ G : Type) where
  onΘ : Γ → Θ → Θ
  onG : Γ → G → G

variable {Γ : Type}

def Equivariant (act : Action Γ Θ G) (M : Model Θ G) : Prop :=
  ∀ g θ x, M (act.onΘ g θ) (act.onG g x) = (M θ x).map (act.onG g)

/-- The action on the evidence: on both sides of every train pair, and on every
test input. -/
def Action.onGiven (act : Action Γ Θ G) (g : Γ) (D : Given G) : Given G where
  train := D.train.map fun p => (act.onG g p.1, act.onG g p.2)
  testIn := D.testIn.map (act.onG g)

/-- The action on a task: on the evidence, and on every test output. -/
def Action.onTask (act : Action Γ Θ G) (g : Γ) (T : Task G) : Task G where
  given := act.onGiven g T.given
  testOut := T.testOut.map (act.onG g)

/-- Zipping two mapped lists is the map over the zipped list. -/
private theorem zip_map_map (f : G → G) (l m : List G) :
    List.zip (l.map f) (m.map f) = (List.zip l m).map fun p => (f p.1, f p.2) := by
  induction l generalizing m with
  | nil => simp
  | cons a l _ih => cases m with
    | nil => simp
    | cons b m => simp [List.zip, List.zipWith]

/-- The pairs of a task commute with the action. -/
theorem Action.pairs_onTask (act : Action Γ Θ G) (g : Γ) (T : Task G) :
    (act.onTask g T).pairs = T.pairs.map fun p => (act.onG g p.1, act.onG g p.2) := by
  simp [Action.onTask, Action.onGiven, Task.pairs, zip_map_map]

/-- Invariance: a transformed task fits under the transformed assignment. -/
theorem fits_equivariant {act : Action Γ Θ G} {M : Model Θ G} {θ : Θ} {T : Task G}
    (h : Equivariant act M) (hf : Fits M θ T) (g : Γ) :
    Fits M (act.onΘ g θ) (act.onTask g T) := by
  intro p hp
  rw [act.pairs_onTask] at hp
  simp only [List.mem_map] at hp
  obtain ⟨q, hq, rfl⟩ := hp
  rw [h, hf q hq]
  rfl

/-- The family of an equivariant model is closed under Γ. -/
theorem fam_equivariant {act : Action Γ Θ G} {M : Model Θ G} {T : Task G}
    (h : Equivariant act M) (hT : Fam M T) (g : Γ) : Fam M (act.onTask g T) := by
  obtain ⟨θ, hθ⟩ := hT
  exact ⟨act.onΘ g θ, fits_equivariant h hθ g⟩

/-! ## Cases -/

/-- A case of a solver: a model with the assignment it stores for each evidence,
`θ(D)`. -/
structure Case (Θ G : Type) where
  M : Model Θ G
  stored : Given G → Θ

/-- Fit: `M(θ(D)) ⊨ T`, for the evidence `D` of `T`. -/
def Case.Fit (S : Case Θ G) (T : Task G) : Prop := Fits S.M (S.stored T.given) T

/-- The stored assignment is blind to the test outputs: two tasks with the same
evidence get the same assignment. -/
theorem stored_blind (S : Case Θ G) (T T' : Task G) (h : T.given = T'.given) :
    S.stored T.given = S.stored T'.given := by
  rw [h]

/-- A parameterization as a product: `Θ = ∏ᵢ Θᵢ`. -/
abbrev Product {I : Type} (Θi : I → Type) := (i : I) → Θi i

end Core
