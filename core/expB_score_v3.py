"""Experiment B scoring v3 (frozen before set 3). All three request sets, reported separately.

Set 1 = development (v2 designed on it), set 2 = evaluation of v2 (v3 designed on its results),
set 3 = confirmatory evaluation of v3 (written after FREEZE_v3_before_set3.json). v3 results on sets 1-2
are post hoc.

Single readers (spec -> unique surviving target):
  R1 / M1  frozen v1 rules / v1 model, v1 gate
  R2 / M2 / A2  v2 rules / v2b model / author's labels, v2 gate, whole-lung regions (regions.json)
  R3 / M3 / A3  the same readers, v3 gate: slice-local front/back and inner/outer (regions_v3.json), and
                position words exclude only clearly-outside candidates (expB_readers_v3.BAND);
                M3 reads the same v2b answers as a second reader (read_model_v3: a low-confidence
                value leaves only that field unspecified)
Dual-reader gates (double reading):
  D1   R1 and M1 resolve to the same target (v1)
  D3t  R3 and M3 resolve to the same target
  D3r  D3t and the same identifying conditions (reason consensus)
Pre-specified for set 3:
  primary safety  = wrong-target authorizations of D3t and D3r;
  primary utility = correct authorizations of D3t and D3r;
  secondary:
    - A3 versus A2 (slice-local versus whole-lung positions under the author's own intent);
    - D1 versus R1 (does double reading remove the v1 rank misreading);
    - every single reader.
No hypothesis test: counts with bootstrap intervals over series (2000 resamples, seed 20260926).

    python expB_score_v3.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
from pathlib import Path

import numpy as np

from expB_readers import read_model, read_rules, resolve
from expB_readers_v2 import read_model_v2, read_rules_v2, resolve_v2
from expB_readers_v3 import read_model_v3, resolve_v3, same_reason
from expB_score import load_jsonl
from expB_score_v2 import MODEL_V1, MODEL_V2, author_to_v2, boot, summarize

ROLE = {1: 'development (v2 designed on it); v3 post hoc', 2: 'evaluation of v2; v3 designed on it (post hoc)',
        3: 'confirmatory evaluation of v3'}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((args.expb / 'lobes.json').read_text())
    reg2 = json.loads((args.expb / 'regions.json').read_text())
    reg3 = json.loads((args.expb / 'regions_v3.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    m1 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V1)}
    m2 = {r['id']: r.get('response') for r in load_jsonl(args.expb / MODEL_V2)}
    author = {r['id']: r['spec'] for r in load_jsonl(args.expb / 'author_specs.jsonl')}  # last label wins
    rows = []
    for q in load_jsonl(args.expb / 'requests_expert.jsonl'):
        sid, targets = q['saved_utc'], table[q['ct_series']]['targets']
        if sid not in m1 or sid not in m2:
            continue                                            # model outputs not yet recorded
        me = next(t for t in targets if t['target'] == q['target'])
        other = min((t for t in targets if t['target'] != q['target']),
                    key=lambda t: np.linalg.norm(np.subtract(t['centroid_lps_mm'], me['centroid_lps_mm'])))
        g2 = {int(k): v for k, v in reg2.get(q['ct_series'], {}).items()}
        g3 = {int(k): v for k, v in reg3.get(q['ct_series'], {}).items()}
        r1, mm1 = read_rules(q['text']), read_model(m1[sid])
        r2, mm2, mm3 = read_rules_v2(q['text']), read_model_v2(m2[sid]), read_model_v3(m2[sid])
        a2 = author_to_v2(author[sid]) if sid in author else 'MISSING'
        t = dict(R1=resolve(targets, r1), M1=resolve(targets, mm1),
                 R2=resolve_v2(targets, r2, g2), M2=resolve_v2(targets, mm2, g2),
                 R3=resolve_v3(targets, r2, g3), M3=resolve_v3(targets, mm3, g3))
        if a2 != 'MISSING':
            t.update(A2=resolve_v2(targets, a2, g2), A3=resolve_v3(targets, a2, g3))
        t['D1'] = t['R1'] if t['R1'] is not None and t['R1'] == t['M1'] else None
        t['D3t'] = t['R3'] if t['R3'] is not None and t['R3'] == t['M3'] else None
        t['D3r'] = t['D3t'] if same_reason(r2, mm3) else None
        for name, chosen in t.items():
            rows.append(dict(reader=name, set=q.get('set', 1), series=q['ct_series'], id=sid,
                             intended='authorize' if chosen == q['target'] else 'defer',
                             other='authorize' if chosen == other['target'] else 'defer'))
    order = ('D3t', 'D3r', 'D1', 'R1', 'M1', 'R2', 'M2', 'A2', 'R3', 'M3', 'A3')
    out = {}
    for s in sorted({r['set'] for r in rows}):
        per = {}
        for name in order:
            rs = [r for r in rows if r['reader'] == name and r['set'] == s]
            if rs:
                res = summarize(rs)
                res['correct_ci'], res['inappropriate_ci'] = boot(rs, 'correct_authorization'), boot(rs, 'inappropriate_authorization')
                per[name] = res
        out[f'set{s}'] = dict(role=ROLE.get(s, ''), n_requests=len({r['id'] for r in rows if r['set'] == s}), readers=per)
    (args.expb / 'results_v3.json').write_text(json.dumps(out, indent=1))
    for s, x in out.items():
        print(s, x['n_requests'], x['role'])
        for k, v in x['readers'].items():
            print(f"  {k:4s} correct {v['correct_authorization']:2d}  wrong {v['inappropriate_authorization']}  {v['correct_ci']}")


if __name__ == '__main__':
    main()
