"""Experiment B: every quantity the manuscript quotes, from the frozen outputs (descriptive aggregation;
no reader, gate or threshold is changed here). Writes paper_results.json in the expB directory.

Per set and reader: the pre-specified episode outcome (nearest other target, from results_v3.json)
and, post hoc, correct resolution and resolution to any wrong target. Also the rank misreading of the
frozen v1 rules, request language, model calls, the B15 positions and the lobe adjudication.

    python expB_paper_results.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
import random
import re
import statistics
from pathlib import Path

from expB_readers import read_model, read_rules, resolve
from expB_readers_v2 import read_model_v2, read_rules_v2, resolve_v2
from expB_readers_v3 import read_model_v3, resolve_v3, same_reason
from expB_score import load_jsonl
from expB_score_v2 import MODEL_V1, MODEL_V2, author_to_v2

READERS = ('R1', 'M1', 'D1', 'R2', 'M2', 'A2', 'R3', 'M3', 'A3', 'D3t', 'D3r')


def boot(rows, key, reps=2000, seed=20260926):
    by = {}
    for r in rows:
        by.setdefault(r['series'], []).append(r)
    keys, rng, vals = sorted(by), random.Random(seed), []
    for _ in range(reps):
        s = [r for k in (rng.choice(keys) for _ in keys) for r in by[k]]
        vals.append(sum(r[key] for r in s) / len(s))
    vals.sort()
    return [round(vals[int(.025 * reps)], 3), round(vals[int(.975 * reps) - 1], 3)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    B = args.expb
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((B / 'lobes.json').read_text())
    reg2 = json.loads((B / 'regions.json').read_text())
    reg3 = json.loads((B / 'regions_v3.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    m1 = {r['id']: r for r in load_jsonl(B / MODEL_V1)}
    m2 = {r['id']: r for r in load_jsonl(B / MODEL_V2)}
    author = {r['id']: r['spec'] for r in load_jsonl(B / 'author_specs.jsonl')}
    reqs = load_jsonl(B / 'requests_expert.jsonl')
    rows, r1_rank = [], {}
    for q in reqs:
        s, sid, targets = q.get('set', 1), q['saved_utc'], table[q['ct_series']]['targets']
        g2 = {int(k): v for k, v in reg2[q['ct_series']].items()}
        g3 = {int(k): v for k, v in reg3[q['ct_series']].items()}
        r1, mm1 = read_rules(q['text']), read_model(m1[sid].get('response'))
        r2, mm2, mm3 = read_rules_v2(q['text']), read_model_v2(m2[sid].get('response')), read_model_v3(m2[sid].get('response'))
        a2 = author_to_v2(author[sid])
        t = dict(R1=resolve(targets, r1), M1=resolve(targets, mm1), R2=resolve_v2(targets, r2, g2),
                 M2=resolve_v2(targets, mm2, g2), A2=resolve_v2(targets, a2, g2), R3=resolve_v3(targets, r2, g3),
                 M3=resolve_v3(targets, mm3, g3), A3=resolve_v3(targets, a2, g3))
        t['D1'] = t['R1'] if t['R1'] is not None and t['R1'] == t['M1'] else None
        t['D3t'] = t['R3'] if t['R3'] is not None and t['R3'] == t['M3'] else None
        t['D3r'] = t['D3t'] if same_reason(r2, mm3) else None
        for name in READERS:
            v = t[name]
            rows.append(dict(set=s, reader=name, series=q['ct_series'], correct=int(v == q['target']),
                             wrong=int(v is not None and v != q['target'])))
        c = r1_rank.setdefault(s, dict(correct=0, correct_by_rank=0, wrong=0, wrong_by_rank=0))
        if t['R1'] is not None:
            key = 'correct' if t['R1'] == q['target'] else 'wrong'
            c[key] += 1
            c[key + '_by_rank'] += bool(r1 and r1.get('ordinal'))
    episode = json.loads((B / 'results_v3.json').read_text())
    out = dict(note='sets 1-2 development/evaluation of v2, set 3 confirmatory evaluation of v3; '
                    'any-wrong counts are post hoc', sets={})
    for s in (1, 2, 3):
        per = {}
        for name in READERS:
            rs = [r for r in rows if r['set'] == s and r['reader'] == name]
            ep = episode[f'set{s}']['readers'].get(name, {})
            per[name] = dict(n=len(rs), correct=sum(r['correct'] for r in rs), any_wrong=sum(r['wrong'] for r in rs),
                             correct_ci=boot(rs, 'correct'), any_wrong_ci=boot(rs, 'wrong'),
                             episode_wrong=ep.get('inappropriate_authorization'),
                             episode_wrong_ci=ep.get('inappropriate_ci'))
        out['sets'][s] = per
    out['r1_rank_misreading'] = r1_rank

    # Request language
    lang = {}
    for s in (1, 2, 3):
        texts = [q['text'] for q in reqs if q.get('set', 1) == s]
        lang[s] = dict(n=len(texts), marking=sum(bool(re.search(r'マーキング|マーク|矢印', x)) for x in texts),
                       segment=sum(bool(re.search(r'S\s?\d', x)) for x in texts),
                       longest_diameter=sum('最大径' in x for x in texts))
    out['language'] = lang
    labels = {s: [author[q['saved_utc']] for q in reqs if q.get('set', 1) == s] for s in (1, 2, 3)}
    out['author_labels'] = {s: dict(unverifiable=sum(bool(a['unverifiable']) for a in v),
                                    ordinal_none=sum(a['ordinal'] is None for a in v), n=len(v))
                            for s, v in labels.items()}
    corrections = {}
    for r in load_jsonl(B / 'author_specs.jsonl'):
        corrections[r['id']] = corrections.get(r['id'], 0) + 1
    out['author_label_corrections'] = sum(v > 1 for v in corrections.values())

    # Model calls (all recorded calls, including the development runs on set 1)
    lat, n_calls, ok = [], 0, 0
    for f in ('model_responses.jsonl', 'model_responses_v2.jsonl', 'model_responses_v2b.jsonl'):
        for r in load_jsonl(B / f):
            n_calls += 1
            ok += r['status'] == 200
            if r['status'] == 200:
                lat.append(r['latency_s'])
    out['model_calls'] = dict(n=n_calls, ok=ok, median_latency_s=round(statistics.median(lat), 2),
                              max_latency_s=round(max(lat), 2))

    # B15 (set 2): the expert's 'lateral' against whole-lung and slice-local inner-to-outer position
    q15 = next(q for q in reqs if q.get('set') == 2 and q['case'] == 'B15')
    uid, tgt = q15['ct_series'], str(q15['target'])
    out['b15'] = dict(ml_whole_lung=reg2[uid][tgt]['ml'], ml_slice_local=reg3[uid][tgt]['ml'])

    # Lobe adjudication (post hoc)
    items = {i['id']: i for i in json.loads((B / 'lobe_review' / 'items.json').read_text())['items']}
    answers = {}
    for r in load_jsonl(B / 'lobe_review' / 'answers.jsonl'):
        answers.setdefault(r['id'], {}).update({k: r[k] for k in ('q1', 'q2', 'note') if r.get(k) is not None})
    fis = {(r['set'], r['case']): r for r in json.loads((B / 'fissure.json').read_text(encoding='utf-8'))}
    adj = []
    for k, it in items.items():
        f, a = fis[(it['set'], it['case'])], answers.get(k, {})
        near = min(v for v in f['dist_to_other_lobes_mm'].values() if v is not None)
        adj.append(dict(item=k, role=it['role'], set=it['set'], case=it['case'], text_lobe=f['text_lobe'],
                        map_lobe=f['ts_lobe'], fissure_mm=near, q1=a.get('q1'), q2=a.get('q2'), note=a.get('note')))
    dis = [x for x in adj if x['role'] == 'disagree']
    ctl = [x for x in adj if x['role'] == 'control']
    named = [r for r in fis.values() if r['text_lobe']]
    out['lobes'] = dict(
        named_lobe_requests=len(named), named_lobe_disagree=sum(r['disagree'] for r in named),
        disagree_n=len(dis), disagree_expert_agrees_map=sum(x['q1'] == x['map_lobe'] for x in dis),
        disagree_expert_agrees_text=sum(x['q1'] == x['text_lobe'] for x in dis),
        disagree_undecidable=sum(x['q1'] == 'undecidable' for x in dis),
        controls_n=len(ctl), controls_undecidable=sum(x['q1'] == 'undecidable' for x in ctl),
        controls_agree=sum(x['q1'] == x['map_lobe'] for x in ctl),
        q2_near_threshold_mm=10.0,
        q2_applicable=sum(x['fissure_mm'] <= 10.0 for x in adj),
        q2_applicable_correct=sum(x['fissure_mm'] <= 10.0 and x['q2'] == 'correct' for x in adj),
        fissure_mm_disagree=sorted(x['fissure_mm'] for x in dis), items=sorted(adj, key=lambda x: int(x['item'][1:])))
    (B / 'paper_results.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k not in ('sets',)}, ensure_ascii=False, indent=1)[:3000])
    for s, per in out['sets'].items():
        print(s, {k: (v['correct'], v['any_wrong'], v['episode_wrong']) for k, v in per.items()})


if __name__ == '__main__':
    main()
