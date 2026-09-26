"""Experiment B, development set (set 1) under the v2 readers — post hoc, used only to settle v2
before it is frozen. Compares the v2 rule reader (R2) with the v2 model reader (M2) per request and
per field, and gates both against the intended target and the nearest other target.

    python expB_dev_v2.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
from pathlib import Path

import numpy as np

from expB_readers_v2 import gate_v2, read_model_v2, read_rules_v2
from expB_score import load_jsonl

FIELDS = ('side', 'lobe', 'ordinal', 'size', 'regions', 'measurement', 'marker', 'unverifiable')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--model-file', default='model_responses_v2.jsonl')
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    regions = json.loads((args.expb / 'regions.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    reqs = load_jsonl(args.expb / 'requests_expert.jsonl')
    model = {r['id']: r for r in load_jsonl(args.expb / args.model_file)}
    rows, tally = [], {k: dict(correct=0, inappropriate=0, defer_intended=0) for k in ('R2', 'M2')}
    for i, q in enumerate(reqs, 1):
        targets = table[q['ct_series']]['targets']
        reg = {int(k): v for k, v in regions.get(q['ct_series'], {}).items()}
        me = next(t for t in targets if t['target'] == q['target'])
        other = min((t for t in targets if t['target'] != q['target']),
                    key=lambda t: np.linalg.norm(np.subtract(t['centroid_lps_mm'], me['centroid_lps_mm'])))
        specs = dict(R2=read_rules_v2(q['text']), M2=read_model_v2((model.get(q['saved_utc']) or {}).get('response')))
        row = dict(n=i, text=q['text'])
        for name, spec in specs.items():
            g_me, g_other = gate_v2(spec, targets, reg, q['target']), gate_v2(spec, targets, reg, other['target'])
            tally[name]['correct'] += g_me == 'authorize'
            tally[name]['inappropriate'] += g_other == 'authorize'
            tally[name]['defer_intended'] += g_me == 'defer'
            row[name] = dict(spec=spec, intended=g_me, other=g_other)
        a, b = specs['R2'] or {}, specs['M2'] or {}
        row['disagree'] = [f for f in FIELDS if a.get(f) != b.get(f)]
        rows.append(row)
    agree = {f: sum(f not in r['disagree'] for r in rows) for f in FIELDS}
    out = dict(note='post hoc, development set only; not an evaluation result', n=len(rows), tally=tally,
               field_agreement_R2_M2=agree, rows=rows)
    (args.expb / ('dev_v2_results_' + Path(args.model_file).stem + '.json')).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(dict(tally=tally, field_agreement_R2_M2=agree), indent=1))
    for r in rows:
        if r['disagree'] or r['R2']['intended'] != r['M2']['intended']:
            print(r['n'], r['disagree'], r['R2']['intended'], r['M2']['intended'], '|', r['text'])


if __name__ == '__main__':
    main()
