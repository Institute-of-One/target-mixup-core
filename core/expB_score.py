"""Experiment B scoring (frozen gate and readers from expB_readers).

Each expert request yields two episodes: the intended target's SEG offered, and the nearest other
target's SEG offered. Readers: R (rules), M (model; needs model_responses.jsonl), A (the author's own
specification; needs author_specs.jsonl — the oracle-like reference, labelled after all requests were
written). Intervals are bootstrap over series.

    python expB_score.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np

from expB_readers import gate, read_model, read_rules, resolve

FIELDS = ('side', 'lobe', 'ordinal', 'size', 'unverifiable')


def load_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()] if path.exists() else []


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    reqs = load_jsonl(args.expb / 'requests_expert.jsonl')
    model = {r['id']: r for r in load_jsonl(args.expb / 'model_responses.jsonl')}
    author = {r['id']: r['spec'] for r in load_jsonl(args.expb / 'author_specs.jsonl')}
    readers = {'R': lambda q: read_rules(q['text'])}
    if len(model) == len(reqs):
        readers['M'] = lambda q: read_model(model[q['saved_utc']].get('response'))
    if len(author) == len(reqs):
        readers['A'] = lambda q: author[q['saved_utc']]
    rows = []
    for q in reqs:
        targets = table[q['ct_series']]['targets']
        me = next(t for t in targets if t['target'] == q['target'])
        other = min((t for t in targets if t['target'] != q['target']),
                    key=lambda t: np.linalg.norm(np.subtract(t['centroid_lps_mm'], me['centroid_lps_mm'])))
        a_spec = author.get(q['saved_utc'])
        stratum = dict(resolvable=None if a_spec is None else resolve(targets, a_spec) == q['target'],
                       unverifiable=None if a_spec is None else bool(a_spec['unverifiable']))
        for name, read in readers.items():
            spec = read(q)
            rows.append(dict(reader=name, series=q['ct_series'], id=q['saved_utc'], **stratum,
                             intended=gate(spec, targets, q['target']), other=gate(spec, targets, other['target']),
                             agree={f: (spec or {}).get(f) == a_spec.get(f) for f in FIELDS} if a_spec else None))

    def summarize(rs):
        n = len(rs)
        return dict(n=n, correct_authorization=sum(r['intended'] == 'authorize' for r in rs),
                    inappropriate_authorization=sum(r['other'] == 'authorize' for r in rs))

    def boot(rs, key, reps=2000):
        by = {}
        for r in rs:
            by.setdefault(r['series'], []).append(r)
        keys, rng, vals = sorted(by), random.Random(20260926), []
        for _ in range(reps):
            s = [r for k in (rng.choice(keys) for _ in keys) for r in by[k]]
            vals.append(summarize(s)[key] / len(s))
        vals.sort()
        return [round(vals[int(.025 * reps)], 3), round(vals[int(.975 * reps) - 1], 3)]

    out = {}
    for name in readers:
        rs = [r for r in rows if r['reader'] == name]
        res = summarize(rs)
        res['correct_ci'] = boot(rs, 'correct_authorization')
        if author:
            for label, sel in (('resolvable_by_author_spec', lambda r: r['resolvable']),
                               ('not_resolvable_by_author_spec', lambda r: r['resolvable'] is False),
                               ('with_unverifiable_content', lambda r: r['unverifiable'])):
                res[label] = summarize([r for r in rs if sel(r)])
            res['field_agreement'] = {f: sum(r['agree'][f] for r in rs) for f in FIELDS}
        out[name] = res
    (args.expb / 'results.json').write_text(json.dumps(dict(readers=out, n_requests=len(reqs)), indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
