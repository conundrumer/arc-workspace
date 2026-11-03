# Prediction, written before any read

- A model per lib relation, component or concept saves .35 to .6 bits per gold-alive pick, against .25 for the one model across relations. It stays under the 1 bit bar over all picks.
- Lib relations gain most, from .67 to about 1.2 bits per pick, and some single relations pass 1 bit with a clear interval.
- Derived relations gain least, since a derived relation has no name across tasks and needs a key built from its form.
- Content features add above noise inside a per-relation model, unlike the general model.
