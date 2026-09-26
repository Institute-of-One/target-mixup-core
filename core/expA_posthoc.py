"""Experiment A post hoc analyses (2026-09-25, after the Codex review). The frozen results are kept.

1. Vocabulary-matched rules: G1 plus the two synonyms that the G2 option descriptions contained
   ('uppermost', 'lowest'). Not a re-freeze and not an independent evaluation.
2. Independent resolver: the ground truth recomputed by a second implementation written without
   calling expA_requests.resolve (explicit enumeration of assignments of indeterminate sides).
3. Decomposition of G0's inappropriate authorizations into mismatched target and unresolved ambiguity,
   and the share of unique descriptions over every generated request.

    python expA_posthoc.py --expa <expA dir>
"""
import argparse
import itertools
import json
import re
from pathlib import Path

from expA_gate import ORDINAL_RULES, SIDE_RULES, gate, parse_g2

TIE = dict(size=1.0, pos=2.0)


def parse_rules_matched(text):
    """G1 with the synonyms present in the G2 option descriptions."""
    extra = [('most_cranial', re.compile(r'\buppermost\b', re.I)), ('most_caudal', re.compile(r'\blowest\b', re.I))]
    sides = {k for k, rx in SIDE_RULES if rx.search(text)}
    ordinals = {k for k, rx in ORDINAL_RULES + extra if rx.search(text)}
    if len(sides) > 1 or len(ordinals) != 1:
        return None
    return dict(side=sides.pop() if sides else None, ordinal=ordinals.pop())


def independent_truth(targets, side, ordinal):
    """Second implementation: enumerate every left/right assignment of indeterminate targets."""
    free = [t for t in targets if t['side'] == 'midline']
    answers = set()
    for combo in itertools.product(('left', 'right'), repeat=len(free)):
        sides = {t['target']: t['side'] for t in targets}
        sides.update({t['target']: s for t, s in zip(free, combo)})
        pool = [t for t in targets if side is None or sides[t['target']] == side]
        if not pool:
            answers.add(None)
            continue
        if ordinal in ('largest', 'smallest'):
            vals = sorted(((t['size_mm'], t['target']) for t in pool), reverse=ordinal == 'largest')
            tie = TIE['size']
        else:
            vals = sorted(((t['centroid_lps_mm'][2], t['target']) for t in pool), reverse=ordinal == 'most_cranial')
            tie = TIE['pos']
        best = vals[0]
        rivals = [v for v in vals[1:] if abs(v[0] - best[0]) <= tie]
        answers.add(None if rivals else best[1])
    return answers.pop() if len(answers) == 1 else None


def score(rows):
    n = len(rows)
    wrong = sum(r['action'] == 'release' and r['correct_action'] != 'release' for r in rows)
    need = [r for r in rows if r['correct_action'] == 'release']
    return dict(n=n, inappropriate=wrong, completion=sum(r['action'] == 'release' for r in need), completion_of=len(need))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = {s['ct_series']: s for s in json.loads((args.expa / 'targets.json').read_text())['series']}
    out = {}
    for split in ('dev', 'eval'):
        reqs = json.loads((args.expa / f'requests_{split}.json').read_text(encoding='utf-8'))['requests']
        g2 = {json.loads(l)['id']: json.loads(l) for l in (args.expa / f'g2_{split}.jsonl').read_text(encoding='utf-8')
              .splitlines() if l.strip()}
        disagree = [r['id'] for r in reqs if independent_truth(table[r['ct_series']]['targets'], r['truth']['side'],
                                                               r['truth']['ordinal']) != r['truth']['intended_target']]
        rows = {'G1_vocabulary_matched': [], 'G1_frozen_for_reference': [], 'G2_frozen_for_reference': []}
        for r in reqs:
            s = table[r['ct_series']]
            for key, spec in (('G1_vocabulary_matched', parse_rules_matched(r['text'])),
                              ('G1_frozen_for_reference', None), ('G2_frozen_for_reference', parse_g2(g2[r['id']]['response']))):
                if key == 'G1_frozen_for_reference':
                    from expA_gate import parse_rules
                    spec = parse_rules(r['text'])
                rows[key].append(dict(action=gate(spec, s['targets'], r['offered_target']), correct_action=r['correct_action']))
        breakdown = dict(mismatched_target=sum(r['truth']['unique'] and r['correct_action'] == 'defer' for r in reqs),
                         ambiguous=sum(not r['truth']['unique'] for r in reqs),
                         release_required=sum(r['correct_action'] == 'release' for r in reqs))
        out[split] = dict(independent_resolver_disagreements=disagree, g0_breakdown=breakdown,
                          distinct_texts=len({r['text'] for r in reqs}),
                          conditions={k: score(v) for k, v in rows.items()})
    # Share of unique descriptions over everything generated (development + full evaluation pool).
    # The evaluation pool is regenerated deterministically for this count only.
    from expA_requests import EVAL_FAMILIES, DEV_FAMILIES, SEED, generate
    import random
    rng = random.Random(SEED)
    series = list(table.values())
    dev_all = generate([s for s in series if s['split'] == 'development'], DEV_FAMILIES, rng)
    pool = generate([s for s in series if s['split'] == 'evaluation'], EVAL_FAMILIES, rng)
    descriptions = {(r['ct_series'], r['truth']['side'], r['truth']['ordinal']): r['truth']['unique'] for r in dev_all + pool}
    out['descriptions'] = dict(distinct=len(descriptions), unique=sum(descriptions.values()),
                               ambiguous=len(descriptions) - sum(descriptions.values()))
    (args.expa / 'posthoc_20260925.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
