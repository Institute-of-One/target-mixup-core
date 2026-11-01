"""Experiment B outcomes as one contingency table, and one row per request.

Reviewer 3 asked for a full contingency table per parser and set, a per-request
supplementary table, and one definition of "wrong-target authorization" that
does not change between sections. The paper reported C / W (N), which is three
overlapping counts rather than a partition, and used "ambiguous", "deferred" and
"unresolvable" differently in different places.

The partition used here, per reader and set, over the requests of that set:

    auth_intended   the reader resolved the request to the nodule the author meant
    auth_nearest    it resolved to the nearest other nodule  (the pre-specified
                    safety endpoint: this is what "wrong-target authorization"
                    means, here and everywhere in the paper)
    auth_other      it resolved to some further nodule       (post hoc)
    defer_resolvable    it resolved nothing, although the author's own labelled
                        conditions under the same gate (A3) did resolve the
                        intended nodule
    defer_unresolved    it resolved nothing, and A3 did not resolve the intended
                        nodule either

The five sum to the number of requests in the set. The paper's earlier counts
are recoverable: C = auth_intended, N = auth_nearest, W = auth_nearest +
auth_other.

A3 is the reference for the deferral split because it is the best a reader of
the author's recorded intent could do under the final gate; it is one fixed
reference for every row, so rows stay comparable. It is not a statement that the
request text was resolvable: the labels were recorded separately from the text
(Section 2.4). A3's own row has every deferral in defer_unresolved by
construction, and in a few requests A3 resolved to another nodule, which counts
as defer_unresolved for the readers that deferred on them; both are reported.

    python expB_contingency.py --expb <expB dir>
"""
import argparse
import csv
import json
from pathlib import Path

CELLS = ('auth_intended', 'auth_nearest', 'auth_other',
         'defer_resolvable', 'defer_unresolved')
REFERENCE = 'A3'


def classify(row, reference):
    """The one place a reader-request outcome is given a name."""
    if row['chosen'] is not None:
        if row['chosen'] == row['target']:
            return 'auth_intended'
        if row['chosen'] == row['nearest_other']:
            return 'auth_nearest'
        return 'auth_other'
    if reference is not None and reference['chosen'] == reference['target']:
        return 'defer_resolvable'
    return 'defer_unresolved'


def build(rows, order):
    ref = {(r['set'], r['case']): r for r in rows if r['reader'] == REFERENCE}
    for r in rows:
        r['outcome'] = classify(r, ref.get((r['set'], r['case'])))
    out = {}
    for s in sorted({r['set'] for r in rows}):
        per = {}
        for name in order:
            rs = [r for r in rows if r['reader'] == name and r['set'] == s]
            if not rs:
                continue
            counts = {c: sum(r['outcome'] == c for r in rs) for c in CELLS}
            counts['n'] = len(rs)
            assert sum(counts[c] for c in CELLS) == counts['n'], (name, s, counts)
            # The counts the manuscript already reports, derived from the same rows.
            counts['correct'] = counts['auth_intended']
            counts['episode_wrong'] = counts['auth_nearest']
            counts['any_wrong'] = counts['auth_nearest'] + counts['auth_other']
            per[name] = counts
        out[str(s)] = per
    return out, rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    args = ap.parse_args(argv)
    data = json.loads((args.expb / 'per_request_v3.json').read_text(encoding='utf-8'))
    rows = data['rows']
    # The row order is the paper's; paper/labels.py holds the names that go with it.
    order = ['R1', 'M1', 'D1', 'R2', 'M2', 'A2', 'R3', 'M3', 'A3', 'D3t', 'D3r']
    table, rows = build(rows, order)
    (args.expb / 'contingency_v3.json').write_text(
        json.dumps(dict(cells=list(CELLS), reference=REFERENCE, sets=table), indent=1),
        encoding='utf-8')

    # One row per request, every reader's outcome side by side.
    by_req = {}
    for r in rows:
        k = (r['set'], r['case'])
        rec = by_req.setdefault(k, dict(set=r['set'], case=r['case'], patient=r['patient'],
                                        ct_series=r['series'], intended_target=r['target'],
                                        nearest_other_target=r['nearest_other']))
        rec[r['reader']] = r['outcome']
        rec[r['reader'] + '_target'] = r['chosen']
    fields = ['set', 'case', 'patient', 'ct_series', 'intended_target', 'nearest_other_target']
    fields += [c for name in order for c in (name, name + '_target')]
    path = args.expb / 'per_request_supplementary.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, restval='')
        w.writeheader()
        for k in sorted(by_req):
            w.writerow(by_req[k])

    for s, per in table.items():
        print('set', s)
        for name, c in per.items():
            print('  %-4s %2d %2d %2d %2d %2d  = %d' % (name, *(c[x] for x in CELLS), c['n']))
    print('written contingency_v3.json and', path.name, '(%d requests)' % len(by_req))


if __name__ == '__main__':
    main()
