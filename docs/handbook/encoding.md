+ budget: 7200
* comment: when editing this doc
    - The notes at the head of [Principles](docs/handbook/principles.md) apply.

# Encoding
- What holds for the program that encodes a model.

## Definitions

### Structures and the lib
- **parse**: the structures that a model finds in the input.
- **setup**: the parse shared by every case, together with the clauses that encode it.
- **draft**: a solver that is not yet approved.
- **corpus**: the approved solvers.
- **precedent**: the encoding that the corpus already uses for a structure in the parse.
    - The solver that introduces or improves that encoding establishes the precedent.
    - A precedent covers how the structure is found and encoded.
    - It does not cover the tests performed inside that encoding.
- **component**: a comp declared in a module under `programs/lib/`, or a proposal comp.
- **construction**: a component whose outputs give another form of its inputs.
- **equivariant lib relation**: a lib relation whose output changes under each D4 element exactly as its input does.

## Fidelity
- The program states the task's concept without depending on how the task file or grid encodes it.
- The program states the concept's relations directly.

### ARC types
- The program works in the task's own types: colors and orientation types.

### Numbers
- **Grounding.** Every number in a solver counts concrete things the task has.
    - A distance counts the cells between something and an edge.
    - A size counts the members of a set.
    - A rank counts the members that come before a given member in an order.
- Clause arithmetic expresses a relation.
    - The program states that relation directly.
    - A wraparound shift is a walk around a cycle.
- **Zero is absence.** A `0` counts nothing that is present.
    - In a spatial setting, `0` represents the absence of a gap, offset, or distance.

### Component instances
- In the program, an instance of a component that is not a construction implements a claim and asserts that the task has that claim.
    - When the task has no such claim, the program expresses the needed step with lib relations or a local clause.
    - That instance may leave any other outputs unused.
- An instance of a construction asserts nothing about the task.

### Indirection

- A parameter has the form required by the clause or component that uses it.
- **Shared form.** A shared parameter has one form.
    - When the consumers require different forms, each case has its own parameter in the form read by its consumer.
    - 2013d3e2
        - The output is a corner region of the non-background bounding box. The quadrant case stores it as a tile position, and the fixed-window case stores it as a corner.
            + gloss
- A parameter is keyed by objects the program already has.
- A clause used only to translate one representation into another is evidence that one of those representations is unjustified.
    - Naming a position in a 2×2 tile by its corner creates a second name for the same key.
        - a68b268e
            - A parameter ranks the four positions of a 2×2 division by using those positions as keys.
                + gloss
                - Corner names would duplicate the keys.
    - Routing a flat correspondence through intermediate coordinates introduces another representation.
        - e633a9e5
            - A parameter pairs each input cell directly with its output cell.
                + gloss
    - Storing an order as successor edges requires closure to expand it before a comparison.
        - a68b268e
            - One rank per color stores the precedence relation.
                + gloss
                - Comparisons then need no expansion.
    - A stored map from a tile's places to the sections they fill uses each frame cell as its own key.
        - 8fff9e47
            + draft
            - Each place in a block directly indexes the output section filled at that place.
                + gloss
                - No stored correspondence is needed.
    - Storing an orientation as an `Axis`, `Sense`, or `Sym` requires conversion to the `D4` used by the clause.
        - 8ee62060
            - The parameter stores the D4 elements that fit.
                + gloss
                - The program applies them directly to block positions.
- Conversion is justified when its two sides differ in content.
    - A sparse set differs in content from its `Ordinal` ranking.
    - A cell set differs in content from its `Canon` class id when the program treats the class as a single thing.

### Performance
- The principled form is the right form regardless of performance.
- A form chosen for speed comes from constraints of the Datalog implementation and its runner.

## Equivariant lib relations
- An equivariant lib relation preserves the model's equivariance when its inputs derive from parameters, through an atom's arguments or a component instance's `@input` relations.
- A non-equivariant one introduces a hidden orientation into an otherwise symmetric program.
    - Mapping within a tile by distance modulo a period creates a hidden orientation.
        - It is observable unless the extent less one is a multiple of the period.
    - An explicit anchor parameter or an equivariant encoding removes that hidden orientation.
        - 332efdb3
            - The motif case places a period-2 motif at every corner of the grid, so no corner is distinguished.
                + gloss

## Corpus consistency

### Parse priority
- The priorities for choosing a parse are, in order:
    1. Fidelity.
    2. Reuse of facts and component instances already available to the program.
        - 1190bc91
            - Both cases use one connected-component instance for marker areas. The instance reuses the shared sequence and rays, and each case supplies a different set of area cells.
                + gloss
    3. The precedent for the structure.
        - 2dee498d
            - The input contains three identical panels along a stored axis. The setup divides them with `divide_slab` from that axis and a stored panel count, and one panel is the output.
                + gloss
        - f25ffba3
            - The input contains a data slab along the axis of a stored direction. One case divides the input with `divide_slab` from that axis and a stored panel count, as 2dee498d does, and another case divides it from a stored panel size.
                + gloss
