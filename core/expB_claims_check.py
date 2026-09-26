"""Checks of the qualitative claims the manuscript makes about Experiment B (each prints PASS/FAIL).

    python expB_claims_check.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
import sys
from pathlib import Path

from expB_readers import read_model, read_rules
from expB_readers_v2 import read_model_v2, read_rules_v2
from expB_readers_v3 import read_model_v3, resolve_v3
from expB_score import load_jsonl
from expB_score_v2 import author_to_v2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    B = args.expb
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    lobes = json.loads((B / 'lobes.json').read_text())
    reg3 = json.loads((B / 'regions_v3.json').read_text())
    for uid, per in lobes.items():
        for t in table[uid]['targets']:
            t['lobe'] = per[str(t['target'])]['lobe']
    m1 = {r['id']: r.get('response') for r in load_jsonl(B / 'model_responses.jsonl')}
    m2 = {r['id']: r.get('response') for r in load_jsonl(B / 'model_responses_v2b.jsonl')}
    author = {r['id']: r['spec'] for r in load_jsonl(B / 'author_specs.jsonl')}
    fis = {(r['set'], r['case']): r for r in json.loads((B / 'fissure.json').read_text(encoding='utf-8'))}
    reqs = load_jsonl(B / 'requests_expert.jsonl')
    results = []

    def claim(name, ok, detail=''):
        results.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + (f' — {detail}' if detail else ''))

    ranks_model = [(read_model(m1[q['saved_utc']]) or {}).get('ordinal') for q in reqs] + \
                  [(read_model_v2(m2[q['saved_utc']]) or {}).get('ordinal') for q in reqs]
    claim('the model reader never returned a rank', not any(ranks_model), str([r for r in ranks_model if r]))
    r1_ranks = {(read_rules(q['text']) or {}).get('ordinal') for q in reqs} - {None}
    claim('the v1 rules only ever read the rank "largest"', r1_ranks == {'largest'}, str(r1_ranks))
    from_ld = all('最大径' in q['text'] for q in reqs if (read_rules(q['text']) or {}).get('ordinal'))
    claim('every v1 rank came from a request containing 最大径', from_ld)
    wrong_cases, disagree = set(), {c for (s, c), r in fis.items() if s == 3 and r['disagree']}
    for q in reqs:
        if q.get('set') != 3:
            continue
        tg = table[q['ct_series']]['targets']
        g3 = {int(k): v for k, v in reg3[q['ct_series']].items()}
        r2, mm3 = read_rules_v2(q['text']), read_model_v3(m2[q['saved_utc']])
        for spec in (r2, mm3, author_to_v2(author[q['saved_utc']])):
            t = resolve_v3(tg, spec, g3)
            if t is not None and t != q['target']:
                wrong_cases.add(q['case'])
        if q['case'] in disagree:
            f = fis[(3, q['case'])]
            claim(f"set-3 {q['case']}: rule and model read the named lobe", (r2 or {}).get('lobe') == f['text_lobe']
                  and (mm3 or {}).get('lobe') == f['text_lobe'], f"text {f['text_lobe']} rule {(r2 or {}).get('lobe')} "
                  f"model {(mm3 or {}).get('lobe')}")
    claim('every set-3 wrong resolution of R3/M3/A3 is a lobe-conflict request', wrong_cases <= disagree,
          f'wrong {sorted(wrong_cases)} conflicts {sorted(disagree)}')
    for s in (1, 2):
        bad = []
        for q in reqs:
            if q.get('set', 1) != s:
                continue
            tg = table[q['ct_series']]['targets']
            g3 = {int(k): v for k, v in reg3[q['ct_series']].items()}
            for name, spec in (('R3', read_rules_v2(q['text'])), ('M3', read_model_v3(m2[q['saved_utc']]))):
                t = resolve_v3(tg, spec, g3)
                if t is not None and t != q['target']:
                    bad.append((name, q['case']))
        claim(f'set {s}: no v3 rule or model resolution to another nodule', not bad, str(bad))
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
