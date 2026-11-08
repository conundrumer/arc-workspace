"""Table observations with cross-table equality of opaque object IDs intact.

The display rows keep the engine adapter's table-local labels. The auxiliary
map is used only for equality joins, never as an ordered or numeric feature.
Old caches lack it and cannot support cross-table Ident correspondences.
"""
import engine as E


class Solver(E.Solver):
    def read(self, tb, best):
        out = super().read(tb, best)
        for t, name in enumerate(tb.names):
            if name in out and 'Ident' in tb.T['column_types'][t]:
                out[name]['ident_values'] = {label: str(raw) for raw, label in tb.labels.get(t, {}).items()}
        return out
