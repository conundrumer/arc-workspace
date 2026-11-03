"""Feature families of a table on hop1, in two namespaces: out.* point toward the task's output, and link.* show a table working with the tables it reads.

A family is a set of keys of one module. FAMILIES gives (module, function, key prefixes). The fit sees each key as <family>.<rest of the key>. STRUCTURE names the families that read the
gold prefix's own shape through `available`: on hop1 every available table is gold, so they don't carry over to a live pool as they stand.
"""
import importlib.util
import os

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/policy4'  # the data folder
FAMILIES = {
    'out.code': ('output_coding', 'ha', ('ha_gain', 'ha_attr', 'ha_cover', 'ha_lav', 'ha_L0')),
    'out.variants': ('output_coding', 'ha', ('ha_n_variants', 'ha_var')),
    'out.frame': ('output_coding', 'ha', ('ha_dims', 'ha_frame', 'ha_box')),
    'out.ring': ('output_coding', 'ha', ('ha_ring', 'ha_line')),
    'out.reach': ('output_reach', 'hb', ('hb1_',)),
    'out.predict': ('output_reach', 'hb', ('hb2_',)),
    'out.paint': ('output_reach', 'hb', ('hb3_',)),
    'out.extent': ('output_reach', 'hb', ('hb4_',)),
    'out.residual': ('output_reach', 'hb', ('hb5_',)),
    'out.space': ('output_reach', 'hb', ('hb6_',)),
    'out.size': ('output_reach', 'hb', ('hb7_',)),
    'link.carry': ('link_columns', 'hc_carry', ('',)),
    'link.front': ('link_columns', 'hc_front', ('',)),
    'link.chain': ('link_structure', 'hd', ('hd_g_',)),
    'link.join': ('link_structure', 'hd', ('hd_j_',)),
    'link.repeat': ('link_structure', 'hd', ('hd_r_',)),
    'link.fit': ('link_structure', 'hd', ('hd_p_',)),
}
STRUCTURE = ('link.front', 'link.chain')


def load():
    """{(module, function): callable}."""
    mods = {}
    for mod, fn, _ in FAMILIES.values():
        if (mod, fn) not in mods:
            spec = importlib.util.spec_from_file_location(mod, f'{HERE}/{mod}.py')
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            mods[(mod, fn)] = m.FEATURE_FUNCS[fn]
    return mods


def rename(mod, fn, d):
    """The keys of one module function's result, under their family names."""
    out = {}
    for fam, (m, f, pre) in FAMILIES.items():
        if (m, f) == (mod, fn):
            for k, v in d.items():
                p = next((x for x in pre if k.startswith(x)), None)
                if p is not None:
                    out[f"{fam}.{k[len(p):].lstrip('_')}" if p else f'{fam}.{k}'] = v
    return out
