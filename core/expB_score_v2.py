"""Experiment B scoring across both request sets and both reader versions (frozen before set 2).

Sets: 1 = development (written before v2 existed; v2 was designed on it), 2 = evaluation (written
after FREEZE_v2_before_set2.json). Results are always reported per set; set 1 under v2 is post hoc.

Readers (each yields a specification; the gate authorizes only a unique surviving target):
  R1 / M1  frozen v1 rules / v1 model request (model_responses.jsonl), v1 gate
  R2 / M2  v2 rules / v2 model request (model_responses_v2b.jsonl), v2 gate with in-lung regions
  A2       the author's own labelled intent (author_specs.jsonl), v2 gate — reference reading
Each request gives two episodes: the intended target offered, and the nearest other target offered.
Strata by the author's labels: used unverifiable information or not. (Amendment v2.1: no 'relied on
a marking' label — every nodule was chosen among outlined annotations, so the author would answer yes
for all; the marking condition is carried by the set instead: set 1 assumed the recipient sees the
marking, set 2 was text only by instruction.)
Intervals: bootstrap over series (2000 resamples, seed 20260926).

    python expB_score_v2.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np

from expB_readers import gate, read_model, read_rules
from expB_readers_v2 import gate_v2, read_model_v2, read_rules_v2
from expB_score import load_jsonl

MODEL_V1, MODEL_V2 = 'model_responses.jsonl', 'model_responses_v2b.jsonl'


def author_to_v2(a):
    if a is None:
        return None
    spec = dict(side=a['side'], lobe=a['lobe'], ordinal=a['ordinal'], size=a['size'],
                regions=sorted(v for v in (a.get('ap'), a.get('ml'), a.get('cc')) if v), measurement=None,
                marker=None, unverifiable=bool(a['unverifiable']))
    return spec if any((spec['side'], spec['lobe'], spec['ordinal'], spec['size'], spec['regions'])) else None


def summarize(rs):
    return dict(n=len(rs), correct_authorization=sum(r['intended'] == 'authorize' for r in rs),
                inappropriate_authorization=sum(r['other'] == 'authorize' for r in rs))


def boot(rs, key, reps=2000):
    by = {}
    for r in rs:
        by.setdefault(r['series'], []).append(r)
    if not by:
        return None
    keys, rng, vals = sorted(by), random.Random(20260926), []
    for _ in range(reps):
        s = [r for k in (rng.choice(keys) for _ in keys) for r in by[k]]
        vals.append(summarize(s)[key] / len(s))
    vals.sort()
    return [round(vals[int(.025 * reps)], 3), round(vals[int(.975 * reps) - 1], 3)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    regions = json.loads((args.expb / 'regions.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    reqs = load_jsonl(args.expb / 'requests_expert.jsonl')
    m1 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V1)}
    m2 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V2)}
    author = {r['id']: r['spec'] for r in load_jsonl(args.expb / 'author_specs.jsonl')}  # last label wins
    readers = dict(
        R1=('v1', lambda q: read_rules(q['text'])),
        M1=('v1', lambda q: read_model(m1[q['saved_utc']]) if q['saved_utc'] in m1 else 'MISSING'),
        R2=('v2', lambda q: read_rules_v2(q['text'])),
        M2=('v2', lambda q: read_model_v2(m2[q['saved_utc']]) if q['saved_utc'] in m2 else 'MISSING'),
        A2=('v2', lambda q: author_to_v2(author[q['saved_utc']]) if q['saved_utc'] in author else 'MISSING'))
    rows = []
    for q in reqs:
        targets = table[q['ct_series']]['targets']
        reg = {int(k): v for k, v in regions.get(q['ct_series'], {}).items()}
        me = next(t for t in targets if t['target'] == q['target'])
        other = min((t for t in targets if t['target'] != q['target']),
                    key=lambda t: np.linalg.norm(np.subtract(t['centroid_lps_mm'], me['centroid_lps_mm'])))
        a = author.get(q['saved_utc'])
        for name, (version, read) in readers.items():
            spec = read(q)
            if spec == 'MISSING':
                continue
            g = (lambda off: gate(spec, targets, off)) if version == 'v1' else (lambda off: gate_v2(spec, targets, reg, off))
            rows.append(dict(reader=name, set=q.get('set', 1), series=q['ct_series'], id=q['saved_utc'],
                             unverifiable=None if a is None else bool(a['unverifiable']),
                             intended=g(q['target']), other=g(other['target'])))
    out = {}
    for s in sorted({r['set'] for r in rows}):
        per = {}
        for name in readers:
            rs = [r for r in rows if r['reader'] == name and r['set'] == s]
            if not rs:
                continue
            res = summarize(rs)
            res['correct_ci'] = boot(rs, 'correct_authorization')
            res['inappropriate_ci'] = boot(rs, 'inappropriate_authorization')
            if all(r['unverifiable'] is not None for r in rs):
                for label, val in (('used_unverifiable', True), ('no_unverifiable', False)):
                    res[label] = summarize([r for r in rs if r['unverifiable'] is val])
            per[name] = res
        out[f'set{s}'] = dict(role='development (v2 designed on it; v2 results post hoc)' if s == 1 else 'evaluation',
                              n_requests=len({r['id'] for r in rows if r['set'] == s}), readers=per)
    (args.expb / 'results_v2.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
