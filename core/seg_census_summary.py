"""Summarize a seg_census.py run, and fix the manual spot-check list.

The spot-check list is chosen from sample_plan.json alone (one SEG per stratum,
smallest SHA-256 of the series UID), so it cannot depend on census outcomes.
Run `--freeze-checks` once before the census finishes; later runs refuse to change it.

    python seg_census_summary.py --out <dir> [--freeze-checks]
"""
import argparse
import collections
import hashlib
import json
import sys
import time
from pathlib import Path


def spot_checks(plan):
    by_stratum = collections.defaultdict(list)
    for s in plan['series']:
        by_stratum[s['stratum']].append(s)
    key = lambda s: hashlib.sha256(s['SeriesInstanceUID'].encode()).hexdigest()
    return [dict(stratum=k, patient=min(v, key=key)['PatientID'],
                 seg_series=min(v, key=key)['SeriesInstanceUID']) for k, v in sorted(by_stratum.items())]


def last_records(path):
    records = {}
    for line in filter(None, path.read_text().splitlines()):
        r = json.loads(line)
        records[r['seg_series']] = r
    return records


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--freeze-checks', action='store_true')
    args = ap.parse_args(argv)
    plan = json.loads((args.out / 'sample_plan.json').read_text())
    checks_path = args.out / 'spot_checks.json'
    checks = spot_checks(plan)
    if args.freeze_checks:
        if checks_path.exists():
            sys.exit('spot_checks.json already frozen; not overwriting')
        records_seen = len(last_records(args.out / 'records.jsonl')) if (args.out / 'records.jsonl').exists() else 0
        checks_path.write_text(json.dumps(dict(
            rule='one SEG per stratum, smallest sha256(SeriesInstanceUID), from sample_plan.json only',
            frozen_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            records_present_when_frozen=records_seen, checks=checks), indent=1))
    frozen = json.loads(checks_path.read_text())['checks'] if checks_path.exists() else None
    if frozen is not None and frozen != checks:
        sys.exit('sample plan and frozen spot checks disagree')

    planned = {s['SeriesInstanceUID']: s for s in plan['series']}
    records = last_records(args.out / 'records.jsonl')
    missing = set(planned) - set(records)
    table = collections.defaultdict(collections.Counter)
    patients = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in records.values():
        table[r['stratum']][r['status']] += 1
        patients[r['stratum']][r['status']].add(r['patient'])
        if 'for_candidates' in r:
            n = r['for_candidates']
            table[r['stratum']][f"unreferenced_for_candidates_{n if n < 2 else '2+'}"] += 1
        if r['status'] in ('match', 'mismatch'):
            table[r['stratum']]['sops_resolved' if r['sop_references_resolved'] else 'sops_unresolved'] += 1
    summary = dict(planned=len(planned), audited=len(records), not_yet_audited=len(missing),
                   strata={k: dict(series=dict(v), patients={s: len(p) for s, p in patients[k].items()})
                           for k, v in sorted(table.items())})
    # A completed census must account for every planned series exactly once.
    statuses = {'match', 'mismatch', 'no_referenced_series', 'ct_unavailable', 'error'}
    assert sum(c for v in table.values() for s, c in v.items() if s in statuses) == len(records)
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
