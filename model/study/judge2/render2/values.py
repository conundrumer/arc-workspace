"""Use the existing table value printer and engine orientation registry."""
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from native import require

VIEW = Path(__file__).resolve().parents[1]/'support/tableview.py'
_view = None


def printer():
    global _view
    if _view is None:
        spec = importlib.util.spec_from_file_location('_render2_table_values', VIEW)
        view = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(view)
        _view = view
    return _view


@dataclass(frozen=True)
class GridSelection:
    axis: str
    frame: tuple
    payload: tuple
    rows: object
    order: tuple
    lines: tuple


class Values:
    def __init__(self, facts):
        self.f = facts
        self.v = printer()
        self.cells = self.v.Cells(facts['task_data'], facts['orientations'])
        self.row_cache = {}
        self.row_cache_cells = 0
        self.ids = {}
        self.cache = {}
        self.orientation_inverse = {}
        for ty,domain in facts.get('orientation_types',{}).items():
            bytext = {}
            for encoding in domain:
                if encoding in self.cells.orient:
                    short = self.v.short_orient(self.cells.orient[encoding])
                    bytext.setdefault(short, set()).add(encoding)
            self.orientation_inverse[ty] = bytext

    def example(self, name):
        if name == 'task': return -1
        if name.startswith('train'): return int(name[5:])-1
        return len(self.f['task_data']['train'])+int(name[4:])-1

    def text(self, cell, schema, example):
        key = (schema['type'], schema.get('frame',''), tuple(cell['value']),tuple(cell.get('extent',[])),cell.get('extent_status'),example)
        if key in self.cache:
            return self.cache[key]
        text = self._text(cell, schema, example)
        require(self.parse(text, schema, example) == cell['value'],
                'decoded display value does not round-trip to native data: '+text)
        if len(self.cache) < 16384:
            self.cache[key] = text
        return text

    def parse(self, text, schema, example):
        ty = schema['type']
        if ty == 'Unit': return [0]
        if ty == 'Example': return [self.example(text)]
        if ty in ('Number', 'Color'): return [int(text)]
        if ty == 'Ident':
            matches = [k for k,v in self.ids.items() if v == text]
            require(len(matches) == 1, 'ambiguous displayed Ident')
            return matches
        if ty in ('Box','Position','Offset'):
            suffix=' (frame extent unavailable/ambiguous)'
            if text.endswith(suffix):text=text[:-len(suffix)]
            if text == 'ZERO': return [0,0,0,0]
            m = re.fullmatch(r'\((-?\d+),(-?\d+)\)/(\d+)x(\d+)',text)
            if m:
                t,l,h,w = map(int,m.groups()); return [t,h-1-t,l,w-1-l]
            m = re.fullmatch(r'r(-?\d+)-(-?\d+) c(-?\d+)-(-?\d+)/(\d+)x(\d+)',text)
            if m:
                t,b,l,r,h,w=map(int,m.groups()); return [t,h-1-b,l,w-1-r]
            m = re.fullmatch(r'\+\((-?\d+),(-?\d+)\)',text)
            if m:
                t,l=map(int,m.groups()); return [t,-t,l,-l]
            m = re.fullmatch(r'\[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]',text)
            if m:return list(map(int,m.groups()))
            raise ValueError('unreadable geometric value: '+text)
        require(ty in self.orientation_inverse, 'missing native orientation type domain: '+ty)
        matches = list(self.orientation_inverse[ty].get(text,[]))
        require(len(matches)==1, 'ambiguous displayed orientation: '+text)
        return matches

    def _text(self, cell, schema, example):
        ty, value = schema['type'], cell['value']
        ex = self.example(example)
        if ty == 'Unit': return 'unit'
        if ty == 'Example':
            n = value[0]
            return 'train'+str(n+1) if n < len(self.f['task_data']['train']) else 'test'+str(n-len(self.f['task_data']['train'])+1)
        if ty in ('Box', 'Position', 'Offset'):
            status=cell.get('extent_status')
            if status=='no_grid' and ty in ('Position','Box'):
                return '['+' '.join(map(str,value))+']'
            extent = cell.get('extent')
            if status=='unresolved':extent=[-1,-1]
            if status=='resolved':require(extent is not None and len(extent)==2 and min(extent)>0,'resolved cell lacks native extent')
            if extent is None and ty in ('Position','Box') and not (schema.get('frame') in ('input','output') and ex>=0):extent=[-1,-1]
            if ty=='Offset' and status=='no_grid':extent=None
            if extent==[-1,-1]:
                return '['+' '.join(map(str,value))+'] (frame extent unavailable/ambiguous)'
            frame = schema.get('frame', '')
            if extent is None and frame in ('input', 'output') and ex >= 0:
                extent = self.cells.inp[ex] if frame == 'input' else (self.cells.out[ex] if ex < len(self.cells.out) else None)
            if extent is not None and ty != 'Offset':
                t,b,l,r = value
                if min(value) >= 0 and (extent[0]-t-b, extent[1]-l-r) == (1,1):
                    return f'({t},{l})/{extent[0]}x{extent[1]}'
                return self.v.framed_box_text(value, extent, self.cells, ex)
            if ty == 'Offset' and (value[0] != -value[1] or value[2] != -value[3]):
                return '['+' '.join(map(str,value))+']'
            return self.v.box_text(value, ex, self.cells, 'offset' if ty == 'Offset' else 'cell' if ty == 'Position' else 'box')
        if ty not in ('Color', 'Number', 'Ident'):
            require(value[0] in self.cells.orient, 'unknown native orientation encoding')
        return self.v.value_text(self.cells, ty, value, ex, self.ids)

    def rows(self, table, entry, order):
        cache_key=(id(table),id(entry),tuple(order))
        if cache_key in self.row_cache:return self.row_cache[cache_key]
        schema = {c['source_label'] or '@slot:'+str(c['slot']):c for c in table['schema']}
        rows = []
        for row in entry['rows']:
            text, keys, cells = {}, {}, {}
            for name in order:
                if name not in schema:
                    text[name] = '<absent>'; continue
                c = schema[name]; cell = row[c['index']]
                text[name] = self.text(cell, c, entry['example'])
                keys[name] = tuple(cell['value'])+tuple(cell.get('extent', []))
                if c['type'] in ('Position', 'Box'):
                    value = cell['value']; t,b,l,r = value
                    extent = cell.get('extent')
                    if extent and min(extent)>0 and min(value) >= 0 and (extent[0]-t-b, extent[1]-l-r) == (1,1):
                        cells[name] = (t,l,*extent)
            # Hidden Unit cells still participate in exact row identity.
            for name,c in schema.items():
                if c['type']=='Unit':
                    cell=row[c['index']];require(cell['value']==[0],'invalid native Unit cell')
                    keys[name]=tuple(cell['value'])+tuple(cell.get('extent',[]))
            rows.append(self.v.V.Row(text, keys, cells))
        size=len(rows)*len(order)
        if self.row_cache_cells+size<=250000:
            self.row_cache[cache_key]=rows;self.row_cache_cells+=size
        return rows

    def grid_layout(self, rows, order):
        for name in order:
            others=[n for n in order if n!=name]
            if not others or any(not any(r.text[n].strip() for n in others) for r in rows):continue
            if rows and all(name in r.cell for r in rows):
                frames={r.cell[name][2:] for r in rows}
                if len(frames)!=1:continue
                h,w=next(iter(frames))
                if h*w>900 or w>30:continue
                counts={}
                for r in rows:
                    p=r.cell[name][:2];counts[p]=counts.get(p,0)+1
                if max(counts.values())>2:continue
                cell_width=max(sum(len(r.text[n])+2 for n in order if n!=name) for r in rows)
                if cell_width>24 or w*(max(cell_width,1)+1)>120:continue
                lines=self.v.V.render(rows,[self.v.V.Grid(name),self.v.V.Table(tuple(others))])
                if any(len(line)>120 for line in lines):continue
                return GridSelection(name,(h,w),tuple(others),rows,tuple(order),tuple(lines))
        return None

    def layout(self, rows, order, allow_grid=True, selection=None):
        if not order:return ['{} (empty record)' for row in rows]
        if selection is not None:
            require(allow_grid and selection.rows is rows and selection.order==tuple(order),
                    'grid selection does not belong to these complete rows and columns')
            label=lambda n:self.f.get('column_names',{}).get(n,n)
            h,w=selection.frame
            return [f'Grid over {label(selection.axis)}, {h}x{w}; cells: '+', '.join(map(label,selection.payload))]+list(selection.lines)
        lines=self.v.V.render(rows, [self.v.V.Table(tuple(order))])
        if all(len(line)<=120 for line in lines):return lines
        lines=[]
        label=lambda n:self.f.get('column_names',{}).get(n,n)
        for i,row in enumerate(rows,1):
            line=f'row {i}: '
            for name in order:
                field=label(name)+'='+row.text[name]
                if len(line)+len(field)>116:
                    lines.append(line.rstrip(' |'));line='  '
                line+=field+' | '
            lines.append(line.rstrip(' |'))
        return lines
