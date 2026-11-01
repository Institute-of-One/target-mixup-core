"""The listing each stratum was sampled from, so the sampling fraction can be stated.

sample_plan.json records what was drawn, never what it was drawn from. Nine of the
ten strata took every listed series, so there the sample is the listing; only
LIDC-IDRI | QIICR was sampled, and its denominator was nowhere on disk.

`--refresh` queries the public NBIA listing (series-level metadata only, no pixel
data) and freezes it with an access date. Without `--refresh` nothing is fetched:
the frozen file is re-verified against sample_plan.json, which must still agree
exactly on every stratum that was taken whole, and is rewritten with the time of
that verification. So the build needs no network and still fails if the frozen
listing and the drawn sample drift apart.

    python seg_census_population.py --census <dir> [--refresh]
"""
import argparse
import collections
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

API = 'https://services.cancerimagingarchive.net/nbia-api/services/v1'
COLLECTIONS = ('LIDC-IDRI', 'RIDER Lung CT')
SAMPLED = 'LIDC-IDRI | QIICR'       # the one stratum not taken whole


def producer(series):
    """The stratum rule of seg_census.py, repeated so the two listings are comparable."""
    desc = series.get('SeriesDescription', '')
    m = re.search(r'QIN CT challenge:?\s*(alg\d+)', desc)
    return 'QIN challenge %s' % m.group(1) if m else series.get('Manufacturer') or 'unknown'


def tally(series):
    by = collections.defaultdict(lambda: (set(), set()))
    for s in series:
        uids, patients = by[s['stratum']]
        uids.add(s['SeriesInstanceUID'])
        patients.add(s['PatientID'])
    return {k: dict(series=len(v[0]), patients=len(v[1])) for k, v in by.items()}


def fetch():
    out = []
    for collection in COLLECTIONS:
        url = '%s/getSeries?%s' % (API, urllib.parse.urlencode(
            dict(Collection=collection, Modality='SEG')))
        with urllib.request.urlopen(url, timeout=300) as r:
            series = json.loads(r.read())
        for s in series:
            s['stratum'] = '%s | %s' % (collection, producer(s))
        out += series
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--refresh', action='store_true', help='query NBIA and re-freeze')
    args = ap.parse_args(argv)
    path = args.census / 'population.json'
    plan = json.loads((args.census / 'sample_plan.json').read_text())
    drawn = tally(plan['series'])

    if args.refresh or not path.exists():
        listed = tally(fetch())
        data = dict(api=API, collections=list(COLLECTIONS),
                    accessed=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    sampled_stratum=SAMPLED, listed=listed)
    else:
        data = json.loads(path.read_text())
        listed = data['listed']

    bad = []
    for stratum, got in sorted(drawn.items()):
        want = listed.get(stratum)
        if want is None:
            bad.append('%s: drawn but not in the listing' % stratum)
        elif stratum == SAMPLED:
            if got['series'] > want['series'] or got['patients'] > want['patients']:
                bad.append('%s: drew more than was listed' % stratum)
        elif got != want:
            bad.append('%s: listed %s but drew %s' % (stratum, want, got))
    if bad:
        for b in bad:
            print('FAIL %s' % b)
        return 1

    data['drawn'] = drawn
    # Carried over from the plan so one file answers "what was drawn, from what, how".
    data['seed'] = plan['seed']
    data['planned_patients'] = plan['lidc_qiicr_patients']
    data['plan_created'] = plan['created']
    if drawn[SAMPLED]['patients'] != plan['lidc_qiicr_patients']:
        print('FAIL %s: plan asked for %d patients, drew %d'
              % (SAMPLED, plan['lidc_qiicr_patients'], drawn[SAMPLED]['patients']))
        return 1
    data['totals'] = dict(
        listed_series=sum(v['series'] for v in listed.values()),
        drawn_series=sum(v['series'] for v in drawn.values()),
        taken_whole=sorted(k for k in drawn if k != SAMPLED))

    # When the audit says the same thing, say it was verified at the same moment. A new
    # clock reading on every run made this file - a released result - differ from the
    # copy in the archive by a timestamp and nothing else, which keeps check_release red
    # and trains everyone to ignore it.
    # data is carried over from the file, so it still holds the previous timestamp:
    # drop it from both sides or the payloads never compare equal.
    was = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    before = {k: v for k, v in was.items() if k != 'verified'}
    now = {k: v for k, v in data.items() if k != 'verified'}
    data['verified'] = (was['verified'] if before == now and was.get('verified')
                        else time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    path.write_text(json.dumps(data, indent=1), encoding='utf-8')
    print('%d strata; listing of %s accessed %s'
          % (len(drawn), ', '.join(COLLECTIONS), data['accessed']))
    print('%d of %d listed SEG series audited; %s sampled at %d of %d patients'
          % (data['totals']['drawn_series'], data['totals']['listed_series'], SAMPLED,
             drawn[SAMPLED]['patients'], listed[SAMPLED]['patients']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
