"""Experiment B v3 per-request trace (descriptive, after scoring): for each request of a set, the target
each v3 reader resolves to, the intended and nearest other target with lobe and slice-local position, and
the conditions each reader used. Writes diag_v3_set<N>.json.

    python expB_diag_v3.py --expb <expB dir> --expa <expA dir> --set 3
"""
import argparse
import json
from pathlib import Path

import numpy as np

from expB_readers_v2 import read_rules_v2
from expB_readers_v3 import read_model_v3, resolve_v3, same_reason
from expB_score import load_jsonl
from expB_score_v2 import MODEL_V2, author_to_v2

KEYS = ('side', 'lobe', 'ordinal', 'size', 'regions')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--set', type=int, default=3)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    reg3 = json.loads((args.expb / 'regions_v3.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    m2 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V2)}
    author = {r['id']: r['spec'] for r in load_jsonl(args.expb / 'author_specs.jsonl')}
    rows = []
    for q in load_jsonl(args.expb / 'requests_expert.jsonl'):
        if q.get('set', 1) != args.set:
            continue
        sid, targets = q['saved_utc'], table[q['ct_series']]['targets']
        g3 = {int(k): v for k, v in reg3[q['ct_series']].items()}
        me = next(t for t in targets if t['target'] == q['target'])
        other = min((t for t in targets if t['target'] != q['target']),
                    key=lambda t: np.linalg.norm(np.subtract(t['centroid_lps_mm'], me['centroid_lps_mm'])))
        r, m, a = read_rules_v2(q['text']), read_model_v3(m2.get(sid)), author_to_v2(author.get(sid))
        tr, tm, ta = resolve_v3(targets, r, g3), resolve_v3(targets, m, g3), resolve_v3(targets, a, g3)
        d3t = tr if tr is not None and tr == tm else None
        desc = lambda t: dict(target=t['target'], lobe=t['lobe'], side=t['side'], size_mm=round(t['size_mm'], 1),
                              ap=g3[t['target']]['ap'], ml=g3[t['target']]['ml'], cc=g3[t['target']]['cc'])
        rows.append(dict(case=q['case'], text=q['text'], intended=desc(me), other=desc(other),
                         all_targets=[desc(t) for t in targets],
                         R3=dict(target=tr, spec={k: (r or {}).get(k) for k in KEYS}),
                         M3=dict(target=tm, spec={k: (m or {}).get(k) for k in KEYS}),
                         A3=dict(target=ta, spec={k: (a or {}).get(k) for k in KEYS}),
                         D3t=d3t, D3r=d3t if same_reason(r, m) else None))
    (args.expb / f'diag_v3_set{args.set}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    for x in rows:
        t = x['intended']['target']
        flag = lambda v: '-' if v is None else 'OK' if v == t else f'WRONG({v})'
        print(f"{x['case']} intended {t} {x['intended']['lobe']} ap{x['intended']['ap']} ml{x['intended']['ml']} "
              f"cc{x['intended']['cc']} {x['intended']['size_mm']}mm | R3 {flag(x['R3']['target'])} "
              f"M3 {flag(x['M3']['target'])} A3 {flag(x['A3']['target'])} D3t {flag(x['D3t'])}")


if __name__ == '__main__':
    main()
