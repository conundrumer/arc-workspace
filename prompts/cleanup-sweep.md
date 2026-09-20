# Cleanup sweep briefs
- The brief the cleanup sweep sends its agent, one section per stage.

* comment
    - A section carries the name `cleanup-sweep.js` asks for, and the workflow fills its `{{variables}}` with the run's values.
    - A value that is a list is built by the script and arrives as one text value.

## cleanup
- Files: programs/solvers/{{stem}}.dl.
- Regions: the lines the findings below name.
- Each finding states a direct form; write it.
    - A `negated-value` finding's comparison becomes the negated primitive.
    - A `negated-use` finding's wrapper relation goes, and the use that negated it negates the primitive.
- Then run Simplify and Prune over those regions.
- Every finding is rewritten. A finding you leave as written is reported under `kept`, with the reason.
- Findings:
```
{{findings}}
```
