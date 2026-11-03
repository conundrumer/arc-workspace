import sys
sys.path.insert(0, '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-ident-block-read-heldout37-ramp22')
import ib_lib as L
extra = dict(
    bundle_check=dict(
        refit_kit_tarball='/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/kits/search-refit-r1-kit-0729e4943.tar.gz',
        bundle_arm='models-tk (manifest.json: "bundle": "models-tk, seeds 0 and 1000, 59 tasks")',
        result='the priors and the three steer files of the tarball models-tk have the same sha256 as the kit models-tk (live_priors 7dafa0ce1e97502779b0007d934955f60f20760c8c64208532732b4824b1051b, relR4_o 3015d409597fff4224b2f91437e8c0a715b3d7eb2f457383132ff33e5c391012, choice5_o 04a895269d26541e3e6687cc5fdc9efd93c28ba91262775f2bfa8eccb5fa980a, tilt_v1.json ca858276d4713e927b6d7a3f956df2d6213f9728d0239ed1be8dc4bed7506a3d). The kit models-tkf steers have those hashes too. The tarball has no models-tkf; the bundle arm ran the ramp tasks on models-tk. So the kit models are used, not the tarball ones.',
    ),
    gold=dict(
        held_and_ramp='%s (sha256 af855438abe27a5be851d51490048788642204294619e0d530e60aa2e959b014) and %s (08ec1bc4d836c650dcdfdfa87ee0cbd9708efe737988952a93083b7d67d3ca23)' % (L.HELD_GOLD, L.IDENT_LIST),
        corpus='%s/<stem>/pairs.jsonl.gz, first row gold_sexp; pin in corpus-pin.json' % L.CORPUS_GOLD,
    ),
    compare_against=['4.2% (INIT reads an Ident form on 4.2% of search tries in an Ident scope, gold 31.6%)', '.04 (INIT reads Ident, keeps Ident: pool share over gold share on the 37)'],
    checks_run=dict(env='pass', C1='pass (135a2760: 29..34)', C2='pass (6 forms)', C3='pass (5 clauses)', smoke='pass (rows for forms 30 and 31, n=32; rerun printed "2 done")', C4='pass (20 stems)', corpus_limit8='ran, 8 stems', C5='needs about 70 s: handed back'),
    processes='4 at most at once on this Mac',
)
L.write_manifest(extra)
print('ok')
