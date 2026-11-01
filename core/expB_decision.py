"""What double reading costs: correct authorizations lost per wrong one removed.

Reviewer 3: "the utility cost of consensus is underdeveloped: how many correct
authorizations are lost per wrong authorization removed? A small decision-table
or net-benefit analysis would make the trade-off visible."

The comparison is paired. The same request goes to the single parser and to the
consensus built from it, so the unit is the request and the two outcomes move
together; a difference of two independent proportions would be the wrong
quantity. The consensus can only authorize where the single parser authorized,
so it never adds a wrong authorization, and the trade is one-directional: some
wrong authorizations become deferrals, and so do some correct ones.

Uncertainty is a paired cluster bootstrap over the CT series. Within one set a
series carries exactly one request, so clustering is vacuous there; pooled over
the three sets a series carries three requests, which is the nesting that
matters, and resampling series keeps those three together.

Two definitions of a wrong authorization are reported, because the paper reports
both: the pre-specified endpoint (the nearest other nodule) and the post hoc
count (any other nodule).

    python expB_decision.py --expb <expB dir>
"""
import argparse
import json
import random
from pathlib import Path

from expB_contingency import REFERENCE, classify  # one definition of an outcome

REPS, SEED = 2000, 20260926

# Each consensus against the readers it is built from, and the two consensus
# definitions against each other.
PAIRS = [('D3t', 'R3'), ('D3t', 'M3'), ('D3r', 'D3t'), ('D1', 'R1'), ('D1', 'M1')]
WRONG = {'prespecified': ('auth_nearest',),
         'posthoc': ('auth_nearest', 'auth_other')}


def outcomes(rows):
    ref = {(r['set'], r['case']): r for r in rows if r['reader'] == REFERENCE}
    return {(r['set'], r['case'], r['reader']): classify(r, ref.get((r['set'], r['case'])))
            for r in rows}


def tally(out, strict, loose, cases, sets, wrong):
    """Wrong authorizations removed and correct ones lost, over the given cases."""
    removed = lost = added = 0
    for s in sets:
        for case in cases:
            a, b = out.get((s, case, loose)), out.get((s, case, strict))
            if a is None or b is None:
                continue
            if a in wrong and b not in wrong:
                removed += 1
            if b in wrong and a not in wrong:
                added += 1
            if a == 'auth_intended' and b != 'auth_intended':
                lost += 1
    return removed, lost, added


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    args = ap.parse_args(argv)
    rows = json.loads((args.expb / 'per_request_v3.json').read_text(encoding='utf-8'))['rows']
    out = outcomes(rows)
    cases = sorted({r['case'] for r in rows})
    sets = sorted({r['set'] for r in rows})

    result = {'note': 'paired comparison of a consensus against the reader it is built '
                      'from; the consensus authorizes only where that reader did, so no '
                      'wrong authorization is added',
              'reps': REPS, 'seed': SEED, 'pairs': {}}
    for label, wrong in WRONG.items():
        for strict, loose in PAIRS:
            key = f'{strict}_vs_{loose}'
            entry = result['pairs'].setdefault(key, {})
            per_set = {}
            for s in sets:
                removed, lost, added = tally(out, strict, loose, cases, [s], wrong)
                per_set[str(s)] = dict(wrong_removed=removed, correct_lost=lost,
                                       wrong_added=added)
            removed, lost, added = tally(out, strict, loose, cases, sets, wrong)
            rng = random.Random(SEED)
            ratios, with_removal = [], 0
            for _ in range(REPS):
                draw = [rng.choice(cases) for _ in cases]
                r, l, _a = tally(out, strict, loose, draw, sets, wrong)
                if r:
                    with_removal += 1
                    ratios.append(l / r)
            ratios.sort()
            ci = ([round(ratios[int(.025 * len(ratios))], 2),
                   round(ratios[int(.975 * len(ratios)) - 1], 2)] if ratios else None)
            entry[label] = dict(per_set=per_set, wrong_removed=removed, correct_lost=lost,
                                wrong_added=added,
                                cost=round(lost / removed, 2) if removed else None,
                                cost_ci=ci, resamples_with_a_removal=with_removal)
    (args.expb / 'decision_v3.json').write_text(json.dumps(result, indent=1),
                                                encoding='utf-8')

    for label in WRONG:
        print('--- wrong =', label)
        for strict, loose in PAIRS:
            e = result['pairs'][f'{strict}_vs_{loose}'][label]
            print('  %-11s removed %2d  lost %2d  cost %-5s %s  (%d/%d resamples removed '
                  'something)'
                  % (f'{strict} vs {loose}', e['wrong_removed'], e['correct_lost'],
                     e['cost'] if e['cost'] is not None else '-',
                     e['cost_ci'] or '', e['resamples_with_a_removal'], REPS))
    print('written decision_v3.json')


if __name__ == '__main__':
    main()
