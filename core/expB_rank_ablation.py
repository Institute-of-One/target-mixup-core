"""Experiment B, post hoc ablation (Codex review 2026-09-26): the frozen v1 rule reader with only its rank
constraint removed. Shows how many R1 resolutions depended on the misread rank, and whether the v1 double
reading (D1) removed exactly the rank-dependent wrong resolutions. Also: A2/A3 with the author's first
label versions (before any correction). Writes rank_ablation.json.

    python expB_rank_ablation.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
from pathlib import Path

from expB_readers import read_model, read_rules, resolve
from expB_readers_v2 import resolve_v2
from expB_readers_v3 import resolve_v3
from expB_score import load_jsonl
from expB_score_v2 import author_to_v2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    B = args.expb
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    for uid, per in json.loads((B / 'lobes.json').read_text()).items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    reg2 = json.loads((B / 'regions.json').read_text())
    reg3 = json.loads((B / 'regions_v3.json').read_text())
    m1 = {r['id']: r.get('response') for r in load_jsonl(B / 'model_responses.jsonl')}
    first_label, last_label = {}, {}
    for r in load_jsonl(B / 'author_specs.jsonl'):
        first_label.setdefault(r['id'], r['spec'])
        last_label[r['id']] = r['spec']
    out = {}
    for s in (1, 2, 3):
        c = dict(r1_correct=0, r1_wrong=0, norank_correct=0, norank_wrong=0, correct_kept=0, wrong_kept=0,
                 wrong_rank_dependent=0, d1_wrong=0, d1_wrong_rank_dependent=0,
                 a2_first=[0, 0], a2_last=[0, 0], a3_first=[0, 0], a3_last=[0, 0], labels_changed=0)
        for q in load_jsonl(B / 'requests_expert.jsonl'):
            if q.get('set', 1) != s:
                continue
            tg, sid = table[q['ct_series']]['targets'], q['saved_utc']
            spec = read_rules(q['text'])
            t_r1 = resolve(tg, spec)
            t_nr = resolve(tg, dict(spec, ordinal=None)) if spec else None
            t_m1 = resolve(tg, read_model(m1[sid]))
            ok = lambda t: t == q['target']
            bad = lambda t: t is not None and t != q['target']
            c['r1_correct'] += ok(t_r1)
            c['r1_wrong'] += bad(t_r1)
            c['norank_correct'] += ok(t_nr)
            c['norank_wrong'] += bad(t_nr)
            c['correct_kept'] += ok(t_r1) and ok(t_nr)
            c['wrong_kept'] += bad(t_r1) and bad(t_nr)
            dep = bad(t_r1) and not bad(t_nr)
            c['wrong_rank_dependent'] += dep
            d1 = t_r1 if t_r1 is not None and t_r1 == t_m1 else None
            c['d1_wrong'] += bad(d1)
            c['d1_wrong_rank_dependent'] += bad(d1) and dep
            g2 = {int(k): v for k, v in reg2[q['ct_series']].items()}
            g3 = {int(k): v for k, v in reg3[q['ct_series']].items()}
            c['labels_changed'] += first_label[sid] != last_label[sid]
            for key, lab in (('first', first_label[sid]), ('last', last_label[sid])):
                a = author_to_v2(lab)
                for name, t in (('a2', resolve_v2(tg, a, g2)), ('a3', resolve_v3(tg, a, g3))):
                    c[f'{name}_{key}'][0] += ok(t)
                    c[f'{name}_{key}'][1] += bad(t)
        out[s] = c
    (B / 'rank_ablation.json').write_text(json.dumps(out, indent=1))
    for s, c in out.items():
        print(s, c)


if __name__ == '__main__':
    main()
