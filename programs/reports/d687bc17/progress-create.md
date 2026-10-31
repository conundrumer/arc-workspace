# d687bc17 create progress

- interference: [Develop](#develop) step 6, "Run the audit ... and resolve the findings". After the `@derive DominantColor` line was added, the audit reported that the group `concept`, `$Stack`, `$MoveObjects`, `$Stack & $MoveObjects`, `$NearerWall` in witness `background=DominantColor` covered the derived-background case. Only the Witness step's `record --all` can fix that, so the finding could not be resolved in Develop. Cost: one extra audit run and a check of the order of operations. The output was wrong until `record --all` ran. It is fixed now.
