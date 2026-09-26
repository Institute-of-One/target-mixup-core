"""Experiment B per-request diagnosis (descriptive, after scoring): for each request the text, the
intended and nearest other target (lobe, in-lung fractions, size), each reader's specification and gate
outcome. Writes diag.json; prints the requests where any reader authorized the other target, and a
compact table for the given set.

    python expB_diag.py --expb <expB dir> --expa <expA dir> [--set 2]
"""
import argparse
import json
from pathlib import Path

import numpy as np

from expB_readers import gate, read_model, read_rules
from expB_readers_v2 import gate_v2, read_model_v2, read_rules_v2
from expB_score import load_jsonl
from expB_score_v2 import MODEL_V1, MODEL_V2, author_to_v2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--set', type=int, default=2)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    regions = json.loads((args.expb / 'regions.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    m1 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V1)}
    m2 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V2)}
    author = {r['id']: r['spec'] for r in load_jsonl(args.expb / 'author_specs.jsonl')}
    rows = []
    for q in load_jsonl(args.expb / 'requests_expert.jsonl'):
        targets = table[q['ct_series']]['targets']
        reg = {int(k): v for k, v in regions.get(q['ct_series'], {}).items()}
        me = next(t for t in targets if t['target'] == q['target'])
        other = min((t for t in targets if t['target'] != q['target']),
                    key=lambda t: np.linalg.norm(np.subtract(t['centroid_lps_mm'], me['centroid_lps_mm'])))
        desc = lambda t: dict(target=t['target'], lobe=t['lobe'], side=t['side'], size_mm=round(t['size_mm'], 1),
                              frac=reg.get(t['target']))
        sid = q['saved_utc']
        specs = dict(R1=read_rules(q['text']), M1=read_model(m1.get(sid)), R2=read_rules_v2(q['text']),
                     M2=read_model_v2(m2.get(sid)), A2=author_to_v2(author.get(sid)))
        out = {}
        for k, s in specs.items():
            g = (lambda off: gate(s, targets, off)) if k in ('R1', 'M1') else (lambda off: gate_v2(s, targets, reg, off))
            out[k] = dict(spec=s, intended=g(q['target']), other=g(other['target']))
        rows.append(dict(set=q.get('set', 1), case=q['case'], text=q['text'], n_targets=len(targets),
                         intended=desc(me), other=desc(other), author_label=author.get(sid), readers=out,
                         m2_raw={k: (v['choice'], round(v['confidence'], 2)) for k, v in
                                 ((m2.get(sid) or {}).get('answers') or {}).items()}))
    (args.expb / 'diag.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in rows:
        bad = [k for k, v in r['readers'].items() if v['other'] == 'authorize']
        if bad:
            print(f"\n[set{r['set']} {r['case']}] wrong-target authorization by {bad}\n  {r['text']}")
            print('  intended', r['intended'], '\n  other   ', r['other'])
            for k in bad:
                print(' ', k, r['readers'][k]['spec'])
    print(f'\n--- set {args.set}: C = correct authorization, x = wrong target, . = defer')
    for r in rows:
        if r['set'] == args.set:
            marks = ''.join('x' if v['other'] == 'authorize' else 'C' if v['intended'] == 'authorize' else '.'
                            for v in r['readers'].values())
            print(r['case'], marks, r['n_targets'], r['text'][:60])


if __name__ == '__main__':
    main()
