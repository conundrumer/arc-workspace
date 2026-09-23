/-!
# Core

The core of the solver theory: a model, a fit, a family, equivalent
models, equivariance, a case, a parameterization as a product, and a parameter
of a case.

A model is `Θ → G → Grids G`: at an assignment and an input it gives the set
of accepted output grids. A plain solver's set is a singleton. A tiebreak
leaves content free, and every resolution of it is accepted, so the set holds
one grid per resolution. The empty set is an ill-formed output: `out` is not a
grid, or it is not total. Grids and assignments are opaque.

A task splits into the evidence and the test outputs. The evidence is the train
pairs and the test inputs. A case's stored assignment reads the evidence
only. The test outputs are held out, and they enter through `Fit`.

A pair carries the candidate accepted sets rather than one of them. A pair whose
accepted outputs differ by more than a tiebreak carries two candidates, each a
singleton, and every other pair carries one. A split task selects one candidate
at every pair, and `Alts` relates a task to its split tasks. `Fits` is stated on
a split task, and `Fam` and `Case.Fit` quantify over the split tasks.

Two assignments agree when, at every input, the two models give the same set of
grids, or neither is defined. Two models are equivalent when each assignment of
either has an assignment of the other that it agrees with. A divergence witness
is an input where, at some assignment, the two models give different sets, or
one is defined and the other is not.

A parameter of a case admits the values a fitting assignment gives it.
`Common` is the One parameter test on a collection: every task all of their
cases fit admits a value common to every member. `Meets` is that test on two
parameters, and `Same` is a stronger test that implies it. Pairwise `Meets`
does not give `Common` on a class of three.

The file takes no dependency, so the set operations it needs are defined here.
-/

namespace Core

/-- A set of grids, as a predicate. -/
abbrev Grids (G : Type) := G → Prop

/-- The image of a set of grids under a map on grids. -/
def Grids.image (f : G → G) (S : Grids G) : Grids G := fun y => ∃ z, S z ∧ f z = y

/-- `M : Θ × G ⇀ 𝒫(G)`. -/
abbrev Model (Θ G : Type) := Θ → G → Grids G

/-- What a pair accepts: its candidate accepted sets. A pair whose accepted
outputs differ by more than a tiebreak carries two candidates, each a singleton;
every other pair carries one, which a tiebreak fills with one grid per
resolution. -/
abbrev Accepts (G : Type) := List (Grids G)

/-- The evidence a case may read: the train pairs and the test inputs. Each
train pair carries what it accepts. -/
structure Given (G : Type) where
  train : List (G × Accepts G)
  testIn : List G

/-- A task: the evidence plus the test outputs. -/
structure Task (G : Type) where
  given : Given G
  testOut : List (Accepts G)

/-- Every pair of a task, test pairs included. -/
def Task.pairs (T : Task G) : List (G × Accepts G) :=
  T.given.train ++ List.zip T.given.testIn T.testOut

variable {Θ Θ₁ Θ₂ G : Type}

/-- `M(θ, x)↓`: the model accepts some grid there. -/
def Defined (M : Model Θ G) (θ : Θ) (x : G) : Prop := ∃ y, M θ x y

/-- `M(θ) ⊨ T`: at every pair, the pair carries one candidate and it is the
model's set. A task with a two-candidate pair fits nothing, so `Fits` holds only
of a split task. -/
def Fits (M : Model Θ G) (θ : Θ) (T : Task G) : Prop :=
  ∀ p ∈ T.pairs, p.2 = [M θ p.1]

/-- `As'` selects one candidate from each entry of `As`. -/
def Selected : List (Accepts G) → List (Accepts G) → Prop
  | [], [] => True
  | A :: As, A' :: As' => (∃ Y, Y ∈ A ∧ A' = [Y]) ∧ Selected As As'
  | _, _ => False

/-- The same, over train pairs, which keep their inputs. -/
def SelectedTrain : List (G × Accepts G) → List (G × Accepts G) → Prop
  | [], [] => True
  | p :: ps, q :: qs => q.1 = p.1 ∧ (∃ Y, Y ∈ p.2 ∧ q.2 = [Y]) ∧ SelectedTrain ps qs
  | _, _ => False

/-- `T' ∈ alts(T)`: `T'` selects one candidate at every pair of `T` and keeps its
inputs. A task with one candidate at every pair is its own only split task. -/
def Alts (T T' : Task G) : Prop :=
  SelectedTrain T.given.train T'.given.train ∧
    T'.given.testIn = T.given.testIn ∧
    Selected T.testOut T'.testOut

/-- `fam(M) = { T : ∃T′ ∈ alts(T). ∃θ. M(θ) ⊨ T′ }`, as a predicate on tasks. -/
def Fam (M : Model Θ G) (T : Task G) : Prop := ∃ T', Alts T T' ∧ ∃ θ, Fits M θ T'

/-- Two assignments agree: at every input, the two models give the same set of
grids, or neither is defined. -/
def Agree (A : Model Θ₁ G) (B : Model Θ₂ G) (θ : Θ₁) (φ : Θ₂) : Prop :=
  ∀ x, A θ x = B φ x ∨ (¬ Defined A θ x ∧ ¬ Defined B φ x)

/-- Equivalent models: each assignment of either has an assignment of the other
that it agrees with. -/
def Equivalent (A : Model Θ₁ G) (B : Model Θ₂ G) : Prop :=
  (∀ θ, ∃ φ, Agree A B θ φ) ∧ (∀ φ, ∃ θ, Agree A B θ φ)

/-- An assignment of one model that agrees with no assignment of the other
refutes equivalence. Against each assignment of the other model it has a
divergence witness: an input where the two sets differ and at least one model
is defined. -/
theorem not_equivalent_of_witness {A : Model Θ₁ G} {B : Model Θ₂ G}
    (h : ∃ θ, ∀ φ, ∃ x, A θ x ≠ B φ x ∧ (Defined A θ x ∨ Defined B φ x)) :
    ¬ Equivalent A B := by
  intro ⟨hfwd, _⟩
  obtain ⟨θ, hθ⟩ := h
  obtain ⟨φ, hφ⟩ := hfwd θ
  obtain ⟨x, hne, hdef⟩ := hθ φ
  rcases hφ x with heq | ⟨hnA, hnB⟩
  · exact hne heq
  · rcases hdef with hA | hB
    · exact hnA hA
    · exact hnB hB

/-! ## Equivariance

`∀g ∈ Γ. M(g·θ, g·x) = g·M(θ, x)`, with Γ acting on assignments and grids, and
on a set of grids member by member. The results below use no group law, so Γ is
any type with an action. -/

structure Action (Γ Θ G : Type) where
  onΘ : Γ → Θ → Θ
  onG : Γ → G → G

variable {Γ : Type}

def Equivariant (act : Action Γ Θ G) (M : Model Θ G) : Prop :=
  ∀ g θ x, M (act.onΘ g θ) (act.onG g x) = Grids.image (act.onG g) (M θ x)

/-- The action on what a pair accepts: on each candidate. -/
def Action.onAccepts (act : Action Γ Θ G) (g : Γ) (A : Accepts G) : Accepts G :=
  A.map (Grids.image (act.onG g))

/-- The action on the evidence: on the input of every train pair and on what it
accepts, and on every test input. -/
def Action.onGiven (act : Action Γ Θ G) (g : Γ) (D : Given G) : Given G where
  train := D.train.map fun p => (act.onG g p.1, act.onAccepts g p.2)
  testIn := D.testIn.map (act.onG g)

/-- The action on a task: on the evidence, and on every test output. -/
def Action.onTask (act : Action Γ Θ G) (g : Γ) (T : Task G) : Task G where
  given := act.onGiven g T.given
  testOut := T.testOut.map (act.onAccepts g)

/-- Zipping two mapped lists is the map over the zipped list. -/
private theorem zip_map_map {α β α' β' : Type} (f : α → α') (h : β → β')
    (l : List α) (m : List β) :
    List.zip (l.map f) (m.map h) = (List.zip l m).map fun p => (f p.1, h p.2) := by
  induction l generalizing m with
  | nil => simp
  | cons a l _ih => cases m with
    | nil => simp
    | cons b m => simp [List.zip, List.zipWith]

/-- The pairs of a task commute with the action. -/
theorem Action.pairs_onTask (act : Action Γ Θ G) (g : Γ) (T : Task G) :
    (act.onTask g T).pairs
      = T.pairs.map fun p => (act.onG g p.1, act.onAccepts g p.2) := by
  simp [Action.onTask, Action.onGiven, Task.pairs, zip_map_map]

/-- Invariance: a transformed task fits under the transformed assignment. -/
theorem fits_equivariant {act : Action Γ Θ G} {M : Model Θ G} {θ : Θ} {T : Task G}
    (h : Equivariant act M) (hf : Fits M θ T) (g : Γ) :
    Fits M (act.onΘ g θ) (act.onTask g T) := by
  intro p hp
  rw [act.pairs_onTask] at hp
  simp only [List.mem_map] at hp
  obtain ⟨q, hq, rfl⟩ := hp
  simp only [Action.onAccepts, hf q hq, List.map_cons, List.map_nil]
  exact congrArg (fun S => [S]) (h g θ q.1).symm

/-- Selection commutes with the action. -/
private theorem selected_map {act : Action Γ Θ G} {g : Γ} :
    ∀ {As As' : List (Accepts G)}, Selected As As' →
      Selected (As.map (act.onAccepts g)) (As'.map (act.onAccepts g))
  | [], [], _ => trivial
  | _ :: _, _ :: _, ⟨⟨Y, hY, rfl⟩, hs⟩ =>
      ⟨⟨Grids.image (act.onG g) Y, List.mem_map_of_mem hY, rfl⟩, selected_map hs⟩

/-- The same over train pairs. -/
private theorem selectedTrain_map {act : Action Γ Θ G} {g : Γ} :
    ∀ {ps qs : List (G × Accepts G)}, SelectedTrain ps qs →
      SelectedTrain (ps.map fun p => (act.onG g p.1, act.onAccepts g p.2))
        (qs.map fun p => (act.onG g p.1, act.onAccepts g p.2))
  | [], [], _ => trivial
  | _ :: _, _ :: _, ⟨hx, ⟨Y, hY, hq⟩, hs⟩ =>
      ⟨by simp [hx], ⟨Grids.image (act.onG g) Y, List.mem_map_of_mem hY,
        by simp [hq, Action.onAccepts]⟩, selectedTrain_map hs⟩

/-- A split task of a transformed task is the transform of a split task. -/
theorem alts_equivariant {act : Action Γ Θ G} {T T' : Task G} (h : Alts T T')
    (g : Γ) : Alts (act.onTask g T) (act.onTask g T') := by
  obtain ⟨ht, hi, ho⟩ := h
  exact ⟨selectedTrain_map ht, by simp [Action.onTask, Action.onGiven, hi],
    selected_map ho⟩

/-- The family of an equivariant model is closed under Γ. -/
theorem fam_equivariant {act : Action Γ Θ G} {M : Model Θ G} {T : Task G}
    (h : Equivariant act M) (hT : Fam M T) (g : Γ) : Fam M (act.onTask g T) := by
  obtain ⟨T', hA, θ, hθ⟩ := hT
  exact ⟨act.onTask g T', alts_equivariant hA g, act.onΘ g θ,
    fits_equivariant h hθ g⟩

/-! ## Cases -/

/-- A case of a solver: a model with the assignment it stores for each evidence,
`θ(D)`. -/
structure Case (Θ G : Type) where
  M : Model Θ G
  stored : Given G → Θ

/-- Fit at one task: `Fit(S_M, T) ⇔ ∃T′ ∈ alts(T). M(θ(D′)) ⊨ T′`, for the
evidence `D′` of the split task. The stored assignment reads the split task's
own evidence, so a train pair that splits stores per split task. -/
def Case.Fit (S : Case Θ G) (T : Task G) : Prop :=
  ∃ T', Alts T T' ∧ Fits S.M (S.stored T'.given) T'

/-- The stored assignment is blind to the test outputs: two tasks with the same
evidence get the same assignment. -/
theorem stored_blind (S : Case Θ G) (T T' : Task G) (h : T.given = T'.given) :
    S.stored T.given = S.stored T'.given := by
  rw [h]

/-- A parameterization as a product: `Θ = ∏ᵢ Θᵢ`. -/
abbrev Product {I : Type} (Θi : I → Type) := (i : I) → Θi i

/-! ## Parameters

A parameter of a case is one component of its parameterization, read off an
assignment. Parameters of different cases are compared by the values each
admits in a task: the values a fitting assignment gives it. `Common` is the One
parameter test, `Meets` is its two-parameter form, and `Same` is a stronger
test. -/

variable {V : Type}

/-- A parameter: a parameterization, a model on it, and the value the parameter
takes at an assignment. A component of a product is `Param.ofProduct`. The
parameterization is a field, so two parameters of different cases compare at
their shared value type. -/
structure Param (G V : Type) : Type 1 where
  Assign : Type
  M : Model Assign G
  read : Assign → V

/-- The component at `i` of a product parameterization, as a parameter of a
model on that product. -/
def Param.ofProduct {I : Type} {Θi : I → Type} (M : Model (Product Θi) G) (i : I) :
    Param G (Θi i) :=
  ⟨Product Θi, M, fun θ => θ i⟩

/-- `p` fits `T`: some assignment of its model fits the task. -/
def Param.Fitted (p : Param G V) (T : Task G) : Prop := ∃ θ, Fits p.M θ T

/-- The values `p` admits in `T`: the values it takes at an assignment that fits
the task. A set of values, in the style of `Grids`. -/
def Param.Admits (p : Param G V) (T : Task G) : V → Prop :=
  fun v => ∃ θ, p.read θ = v ∧ Fits p.M θ T

/-- A fitting assignment gives a value the parameter admits. -/
theorem Param.admits_read (p : Param G V) {T : Task G} {θ : p.Assign}
    (h : Fits p.M θ T) : p.Admits T (p.read θ) := ⟨θ, rfl, h⟩

/-- In a task its model fits, a parameter admits at least one value. So the
nonemptiness of the admitted values is not a further hypothesis: it follows
from the fit. -/
theorem Param.admits_nonempty {p : Param G V} {T : Task G} (h : p.Fitted T) :
    ∃ v, p.Admits T v := by
  obtain ⟨θ, hθ⟩ := h
  exact ⟨p.read θ, p.admits_read hθ⟩

/-- The One parameter test on a collection: in every task all of their models
fit, some one value is admitted by every member. Using one parameter across
the collection's cases asserts this. -/
def Common {K : Type} (P : K → Param G V) : Prop :=
  ∀ T, (∀ k, (P k).Fitted T) → ∃ v, ∀ k, (P k).Admits T v

/-- The two-parameter form of `Common`: in every task both models fit, some
one value is admitted by both parameters. -/
def Meets (a b : Param G V) : Prop :=
  ∀ T, a.Fitted T → b.Fitted T → ∃ v, a.Admits T v ∧ b.Admits T v

/-- `Meets` is `Common` on the two-member collection. -/
theorem common_pair_iff_meets {a b : Param G V} :
    Common (fun i : Bool => bif i then a else b) ↔ Meets a b := by
  constructor
  · intro h T ha hb
    obtain ⟨v, hv⟩ := h T (fun i => by cases i <;> assumption)
    exact ⟨v, hv true, hv false⟩
  · intro h T hk
    obtain ⟨v, hva, hvb⟩ := h T (hk true) (hk false)
    exact ⟨v, fun i => by cases i <;> assumption⟩

/-- A stronger test: in every task both models fit, the two parameters admit
the same values. -/
def Same (a b : Param G V) : Prop :=
  ∀ T, a.Fitted T → b.Fitted T → ∀ v, (a.Admits T v ↔ b.Admits T v)

/-- `Same` implies `Meets`. The quantifier already gives a fitting assignment
of the first model, and that assignment gives the parameter a value it admits,
so the value both admit needs no further hypothesis. -/
theorem meets_of_same {a b : Param G V} (h : Same a b) : Meets a b := by
  intro T ha hb
  obtain ⟨v, hv⟩ := Param.admits_nonempty ha
  exact ⟨v, hv, (h T ha hb v).1 hv⟩

/-- `Same` is reflexive. -/
theorem same_refl (a : Param G V) : Same a a := fun _ _ _ _ => Iff.rfl

/-- `Same` is symmetric. -/
theorem same_symm {a b : Param G V} (h : Same a b) : Same b a :=
  fun T hb ha v => (h T ha hb v).symm

/-- `Same` is transitive on the tasks the middle parameter fits. The quantifier
of `Same` ranges over the tasks both models fit, so a task fit by the outer two
reaches neither hypothesis unless the middle model fits it as well.
`not_same_trans` shows the hypothesis cannot be dropped. -/
theorem same_trans_of_fitted {a b c : Param G V} (hab : Same a b) (hbc : Same b c)
    (hmid : ∀ T, a.Fitted T → c.Fitted T → b.Fitted T) : Same a c := by
  intro T ha hc v
  exact (hab T ha (hmid T ha hc) v).trans (hbc T (hmid T ha hc) hc v)

/-- Under `Same`, a class of any size has a common admitted value in each task
every member fits, so collapsing the class into one parameter is sound. The
class is given by a base parameter and members each `Same` as the base. -/
theorem same_common {K : Type} (base : Param G V) (P : K → Param G V)
    (h : ∀ k, Same base (P k)) {T : Task G} (hb : base.Fitted T)
    (hk : ∀ k, (P k).Fitted T) : ∃ v, base.Admits T v ∧ ∀ k, (P k).Admits T v := by
  obtain ⟨v, hv⟩ := Param.admits_nonempty hb
  exact ⟨v, hv, fun k => (h k T hb (hk k) v).1 hv⟩

/-- A collection whose members are pairwise `Same` is `Common`, given a member
to draw the value from. -/
theorem common_of_same {K : Type} (P : K → Param G V) (k₀ : K)
    (h : ∀ k k', Same (P k) (P k')) : Common P := by
  intro T hk
  obtain ⟨v, hv⟩ := Param.admits_nonempty (hk k₀)
  exact ⟨v, fun k => (h k₀ k T (hk k₀) (hk k) v).1 hv⟩

/-- The same for three parameters, stated on the pairwise relation. -/
theorem same_common₃ {a b c : Param G V} (hab : Same a b) (hbc : Same b c)
    {T : Task G} (ha : a.Fitted T) (hb : b.Fitted T) (hc : c.Fitted T) :
    ∃ v, a.Admits T v ∧ b.Admits T v ∧ c.Admits T v := by
  obtain ⟨v, hv⟩ := Param.admits_nonempty ha
  have hvb : b.Admits T v := (hab T ha hb v).1 hv
  exact ⟨v, hv, hvb, (hbc T hb hc v).1 hvb⟩

/-! ## Three sets that meet pairwise

The set-level core of the failure of `Meets`: three sets can meet pairwise and
still have no common member. -/

/-- A three-element type, for the counterexamples below. -/
inductive Hue where
  | red
  | blue
  | green
deriving DecidableEq

/-- Three sets meet pairwise and have no common member: `{red, blue}`,
`{blue, green}`, `{red, green}`. This is the set-level step of
`meets_not_common`. -/
theorem three_pairwise_no_common :
    ∃ S₁ S₂ S₃ : Hue → Prop,
      (∃ v, S₁ v ∧ S₂ v) ∧ (∃ v, S₂ v ∧ S₃ v) ∧ (∃ v, S₁ v ∧ S₃ v) ∧
        ¬ ∃ v, S₁ v ∧ S₂ v ∧ S₃ v := by
  refine ⟨fun h => h ≠ Hue.green, fun h => h ≠ Hue.red, fun h => h ≠ Hue.blue,
    ⟨Hue.blue, by decide, by decide⟩, ⟨Hue.green, by decide, by decide⟩,
    ⟨Hue.red, by decide, by decide⟩, ?_⟩
  rintro ⟨v, h₁, h₂, h₃⟩
  cases v
  · exact h₂ rfl
  · exact h₃ rfl
  · exact h₁ rfl

/-! ## Hue models

A model on hues, used to carry the set-level counterexample up to parameters.
`hueModel S` ignores its input grid. At a hue in `S` it gives the full set of
grids, and at a hue outside `S` it gives that hue alone. So a task with a pair
that carries the full set is fit exactly by the hues in `S`, and the values the
parameter admits there are `S` itself. -/

/-- The other hue, used to separate the full set from a singleton. -/
def Hue.other : Hue → Hue
  | .red => .blue
  | .blue => .green
  | .green => .red

/-- The other hue is another hue. -/
theorem Hue.other_ne (θ : Hue) : θ.other ≠ θ := by cases θ <;> decide

/-- The set a hue model gives at `θ`: every grid when `θ` is in `S`, and `θ`
alone otherwise. -/
def hueSet (S : Hue → Bool) (θ : Hue) : Grids Hue :=
  if S θ then fun _ => True else fun y => y = θ

/-- A model on hues, reading `hueSet` and ignoring the input grid. -/
def hueModel (S : Hue → Bool) : Model Hue Hue := fun θ _ => hueSet S θ

/-- A hue parameter: the model `hueModel S` with the assignment read as the
value. -/
def hueParam (S : Hue → Bool) : Param Hue Hue := ⟨Hue, hueModel S, id⟩

/-- Inside `S` the set is everything. -/
theorem hueSet_true {S : Hue → Bool} {θ : Hue} (h : S θ = true) :
    hueSet S θ = fun _ => True := by simp [hueSet, h]

/-- Outside `S` the set is one hue. -/
theorem hueSet_false {S : Hue → Bool} {θ : Hue} (h : S θ = false) :
    hueSet S θ = fun y => y = θ := by simp [hueSet, h]

/-- The full set is not a singleton. -/
theorem top_ne_singleton (θ : Hue) : (fun _ : Hue => True) ≠ fun y => y = θ := by
  intro h
  exact θ.other_ne (cast (congrFun h θ.other) trivial)

/-- A singleton names its hue. -/
theorem singleton_inj {θ θ' : Hue} (h : (fun y => y = θ) = fun y : Hue => y = θ') :
    θ = θ' := cast (congrFun h θ) rfl

/-- Two hue sets agree only inside both sets, or outside both at one hue. -/
theorem hueSet_eq {S S' : Hue → Bool} {θ θ' : Hue} (h : hueSet S θ = hueSet S' θ') :
    (S θ = true ∧ S' θ' = true) ∨ (S θ = false ∧ S' θ' = false ∧ θ = θ') := by
  cases hS : S θ <;> cases hS' : S' θ'
  · rw [hueSet_false hS, hueSet_false hS'] at h
    exact Or.inr ⟨rfl, rfl, singleton_inj h⟩
  · rw [hueSet_false hS, hueSet_true hS'] at h
    exact absurd h.symm (top_ne_singleton θ)
  · rw [hueSet_true hS, hueSet_false hS'] at h
    exact absurd h (top_ne_singleton θ')
  · exact Or.inl ⟨rfl, rfl⟩

/-- A hue parameter admits the assignments of its model that fit. -/
theorem hueAdmits_iff {S : Hue → Bool} {T : Task Hue} {v : Hue} :
    (hueParam S).Admits T v ↔ Fits (hueModel S) v T := by
  constructor
  · rintro ⟨θ, rfl, h⟩
    exact h
  · intro h
    exact ⟨v, rfl, h⟩

/-- At a pair of a task two fitting hues give the same set. -/
theorem hueSet_eq_of_fits {S S' : Hue → Bool} {θ θ' : Hue} {T : Task Hue}
    {p : Hue × Accepts Hue} (hp : p ∈ T.pairs) (hθ : Fits (hueModel S) θ T)
    (hθ' : Fits (hueModel S') θ' T) : hueSet S θ = hueSet S' θ' := by
  have h : [hueSet S θ] = [hueSet S' θ'] := (hθ p hp).symm.trans (hθ' p hp)
  injection h with h _

/-- A hue with the same set as a fitting hue fits as well. -/
theorem hueFits_of_set {S : Hue → Bool} {θ v : Hue} {T : Task Hue}
    (hθ : Fits (hueModel S) θ T) (h : hueSet S v = hueSet S θ) :
    Fits (hueModel S) v T := by
  intro p hp
  rw [hθ p hp]
  exact congrArg (fun A => [A]) h.symm

/-- A task with one pair that carries the full set of grids. -/
def topTask : Task Hue :=
  { given := { train := [(Hue.red, [fun _ : Hue => True])], testIn := [] }
    testOut := [] }

/-- The pairs of `topTask`. -/
theorem topTask_pairs : topTask.pairs = [(Hue.red, [fun _ : Hue => True])] := rfl

/-- A hue model fits `topTask` exactly at the hues of its set. -/
theorem hueFits_topTask {S : Hue → Bool} {θ : Hue} :
    Fits (hueModel S) θ topTask ↔ S θ = true := by
  constructor
  · intro h
    have hm : ((Hue.red, [fun _ : Hue => True]) : Hue × Accepts Hue) ∈ topTask.pairs := by
      rw [topTask_pairs]; exact List.mem_cons_self
    have he : [fun _ : Hue => True] = [hueSet S θ] := h _ hm
    injection he with he _
    cases hS : S θ
    · rw [hueSet_false hS] at he
      exact absurd he (top_ne_singleton θ)
    · rfl
  · intro h p hp
    rw [topTask_pairs] at hp
    have : p = (Hue.red, [fun _ : Hue => True]) := by
      cases hp with
      | head => rfl
      | tail _ hp => cases hp
    subst this
    exact congrArg (fun A => [A]) (hueSet_true h).symm

/-- Two hue parameters meet when their sets cover the hues and share one. -/
theorem hue_meets {S S' : Hue → Bool} (hcov : ∀ θ, S θ = true ∨ S' θ = true)
    {w : Hue} (hw : S w = true) (hw' : S' w = true) :
    Meets (hueParam S) (hueParam S') := by
  rintro T ⟨θ, hθ⟩ ⟨θ', hθ'⟩
  have key : ∀ p ∈ T.pairs, S θ = true ∧ S' θ' = true := by
    intro p hp
    rcases hueSet_eq (hueSet_eq_of_fits hp hθ hθ') with h | ⟨h, h', hee⟩
    · exact h
    · subst hee
      rcases hcov θ with hc | hc
      · exact absurd hc (by rw [h]; exact Bool.noConfusion)
      · exact absurd hc (by rw [h']; exact Bool.noConfusion)
  refine ⟨w, hueAdmits_iff.2 ?_, hueAdmits_iff.2 ?_⟩
  · intro p hp
    have h : hueSet S θ = hueSet S w :=
      (hueSet_true (key p hp).1).trans (hueSet_true hw).symm
    show p.2 = [hueSet S w]
    rw [show p.2 = [hueSet S θ] from hθ p hp, h]
  · intro p hp
    have h : hueSet S' θ' = hueSet S' w :=
      (hueSet_true (key p hp).2).trans (hueSet_true hw').symm
    show p.2 = [hueSet S' w]
    rw [show p.2 = [hueSet S' θ'] from hθ' p hp, h]

/-- `{red, blue}`. -/
def hueS₁ : Hue → Bool
  | .green => false
  | _ => true

/-- `{blue, green}`. -/
def hueS₂ : Hue → Bool
  | .red => false
  | _ => true

/-- `{red, green}`. -/
def hueS₃ : Hue → Bool
  | .blue => false
  | _ => true

/-- The key result: pairwise `Meets` does not give `Common`. Three parameters
meet pairwise, each of their models fits `topTask`, and no value is admitted by
all three there. The set-level step is `three_pairwise_no_common`:
the values admitted in `topTask` are the three sets `{red, blue}`,
`{blue, green}` and `{red, green}`, which meet pairwise and share nothing. -/
theorem meets_not_common :
    ∃ a b c : Param Hue Hue,
      Meets a b ∧ Meets b c ∧ Meets a c ∧
        a.Fitted topTask ∧ b.Fitted topTask ∧ c.Fitted topTask ∧
        ¬ ∃ v, a.Admits topTask v ∧ b.Admits topTask v ∧ c.Admits topTask v := by
  refine ⟨hueParam hueS₁, hueParam hueS₂, hueParam hueS₃,
    hue_meets (fun θ => by cases θ <;> decide) (w := Hue.blue) rfl rfl,
    hue_meets (fun θ => by cases θ <;> decide) (w := Hue.green) rfl rfl,
    hue_meets (fun θ => by cases θ <;> decide) (w := Hue.red) rfl rfl,
    ⟨Hue.red, hueFits_topTask.2 rfl⟩, ⟨Hue.blue, hueFits_topTask.2 rfl⟩,
    ⟨Hue.red, hueFits_topTask.2 rfl⟩, ?_⟩
  rintro ⟨v, h₁, h₂, h₃⟩
  have k₁ := hueFits_topTask.1 (hueAdmits_iff.1 h₁)
  have k₂ := hueFits_topTask.1 (hueAdmits_iff.1 h₂)
  have k₃ := hueFits_topTask.1 (hueAdmits_iff.1 h₃)
  cases v
  · exact Bool.noConfusion (k₂.symm.trans rfl)
  · exact Bool.noConfusion (k₃.symm.trans rfl)
  · exact Bool.noConfusion (k₁.symm.trans rfl)

/-! ## Transitivity of `Same`

`Same` is quantified over the tasks both models fit, so the middle parameter of
a chain can miss a task the outer two share. The counterexample below is a model
whose set is empty: it fits no task with a pair that carries the full set of
grids, so it meets neither outer parameter there. -/

/-- The empty set of hues. -/
def hueEmpty : Hue → Bool := fun _ => false

/-- `{red}`. -/
def hueRed : Hue → Bool
  | .red => true
  | _ => false

/-- `{blue}`. -/
def hueBlue : Hue → Bool
  | .blue => true
  | _ => false

/-- A hue parameter is `Same` as the parameter of the empty set. A task both fit
has every pair carrying one hue, and both admit that hue alone. -/
theorem hue_same_of_empty (S : Hue → Bool) :
    Same (hueParam S) (hueParam hueEmpty) := by
  rintro T ⟨θ, hθ0⟩ ⟨θ', hθ0'⟩ v
  have hθ : Fits (hueModel S) θ T := hθ0
  have hθ' : Fits (hueModel hueEmpty) θ' T := hθ0'
  cases hpairs : T.pairs with
  | nil =>
      have hany : ∀ (S' : Hue → Bool) (u : Hue), Fits (hueModel S') u T := by
        intro S' u p hp
        rw [hpairs] at hp
        cases hp
      exact Iff.intro (fun _ => hueAdmits_iff.2 (hany _ v))
        (fun _ => hueAdmits_iff.2 (hany _ v))
  | cons q qs =>
      have hq : q ∈ T.pairs := by rw [hpairs]; exact List.mem_cons_self
      rcases hueSet_eq (hueSet_eq_of_fits hq hθ hθ') with ⟨_, h'⟩ | ⟨h, _, hee⟩
      · exact Bool.noConfusion h'
      · subst hee
        have hS : ∀ u, Fits (hueModel S) u T ↔ u = θ := by
          intro u
          constructor
          · intro hu
            rcases hueSet_eq (hueSet_eq_of_fits hq hu hθ) with ⟨_, h2⟩ | ⟨_, _, h2⟩
            · exact Bool.noConfusion (h.symm.trans h2)
            · exact h2
          · rintro rfl
            exact hθ
        have hE : ∀ u, Fits (hueModel hueEmpty) u T ↔ u = θ := by
          intro u
          constructor
          · intro hu
            rcases hueSet_eq (hueSet_eq_of_fits hq hu hθ') with ⟨h2, _⟩ | ⟨_, _, h2⟩
            · exact Bool.noConfusion h2
            · exact h2
          · rintro rfl
            exact hθ'
        calc (hueParam S).Admits T v ↔ Fits (hueModel S) v T := hueAdmits_iff
          _ ↔ v = θ := hS v
          _ ↔ Fits (hueModel hueEmpty) v T := (hE v).symm
          _ ↔ (hueParam hueEmpty).Admits T v := hueAdmits_iff.symm

/-- `Same` is not transitive on its own: the parameter of `{red}` and the
parameter of `{blue}` are each `Same` as the parameter of the empty set, and
they are not `Same` as each other, since `topTask` is fit by both and they
admit different hues there. So `same_trans_of_fitted` needs its hypothesis. -/
theorem not_same_trans :
    ∃ a b c : Param Hue Hue, Same a b ∧ Same b c ∧ ¬ Same a c := by
  refine ⟨hueParam hueRed, hueParam hueEmpty, hueParam hueBlue,
    hue_same_of_empty _, same_symm (hue_same_of_empty _), ?_⟩
  intro h
  have hr : (hueParam hueRed).Admits topTask Hue.red :=
    hueAdmits_iff.2 (hueFits_topTask.2 rfl)
  have hb : (hueParam hueBlue).Admits topTask Hue.red :=
    (h topTask ⟨Hue.red, hueFits_topTask.2 rfl⟩ ⟨Hue.blue, hueFits_topTask.2 rfl⟩
      Hue.red).1 hr
  exact Bool.noConfusion (hueFits_topTask.1 (hueAdmits_iff.1 hb))

end Core
