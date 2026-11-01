"""What was fixed before what, from the dated freeze records themselves.

The paper says each set was written after its design had been hash-frozen. A
reviewer asked what was truly pre-specified and what was adapted as the study
went, and that cannot be answered by repeating the sentence: it needs the order
of the records. Every freeze record carries a UTC time, the files it hashed and a
stage description, and every request carries the time it was saved, so the order
is on disk.

This builds one row per freeze, saying how many requests of each set existed when
it was taken, and one row per set, saying which freeze governed it and whether the
results of the earlier sets were already known. It also measures how the requests
themselves changed from set to set, using the frozen parsers' own vocabularies
rather than a reading of the text, because a set written after seeing two others
is not exchangeable with them and the paper should say so with a number.

    python expB_timeline.py --expa <expA dir> --expb <expB dir>
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

import expB_readers
import expB_readers_v2

sys.stdout.reconfigure(encoding='utf-8')

# The two features the frozen readers lump into one "information the gate cannot
# check" flag, split out because they changed between sets in opposite directions.
SEGMENT_NAME = r'\bS\s?(10|[1-9])\b|S\d{1,2}[ab]?|区域'
MARKING = expB_readers_v2._MARKER


def freezes(expa, expb):
    out = []
    for path in sorted(expa.glob('*FREEZE*.json')) + sorted(expb.glob('FREEZE*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        when = record.get('frozen_utc')
        stage = record.get('stage') or record.get('note', '')
        # The first Experiment A record names its design as a string beside a single
        # sha256; every other record carries a {name: sha256} map.
        design = record.get('design') or {}
        if isinstance(design, str):
            design = {design: record['sha256']}
        out.append(dict(
            record=path.name, short=path.stem, experiment='A' if path.parent == expa else 'B',
            frozen_utc=when, stage=stage,
            # The first clause of the record's own stage, for a table cell. The whole
            # of it, and every hash, stay in the released record.
            stage_short=re.split(r';|\.\s', stage)[0].strip()[:72],
            design=sorted(design),
            files=len(record.get('files', {})), data=len(record.get('data', {})),
            gui=len(record.get('gui', {}))))
    return sorted(out, key=lambda r: r['frozen_utc'])


def set_of(request):
    """Set 1 was written before the field existed, so its records carry no 'set'."""
    return request.get('set') or 1


def profile(texts):
    """What the frozen parsers find in a set of requests, as counts."""
    count = collections.Counter(n=len(texts))
    for text in texts:
        v1 = expB_readers.read_rules(text) or {}
        v2 = expB_readers_v2.read_rules_v2(text) or {}
        count['side'] += bool(v1.get('side'))
        count['lobe'] += bool(v1.get('lobe'))
        count['rank_read_by_v1'] += bool(v1.get('ordinal'))
        count['size'] += bool(v1.get('size'))
        count['position_word'] += bool(v2.get('regions'))
        count['measurement_word'] += bool(v2.get('measurement'))
        count['marking'] += bool(re.search(MARKING, text, re.I))
        count['segment_name'] += bool(re.search(SEGMENT_NAME, text, re.I))
    return dict(count)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--expb', required=True, type=Path)
    args = ap.parse_args(argv)

    requests = [json.loads(line) for line in
                (args.expb / 'requests_expert.jsonl').read_text(encoding='utf-8').splitlines()
                if line.strip()]
    by_set = collections.defaultdict(list)
    for request in requests:
        by_set[set_of(request)].append(request)

    rows = freezes(args.expa, args.expb)
    for row in rows:
        # How much of the study existed when this freeze was taken.
        row['requests_written'] = {str(s): sum(r['saved_utc'] < row['frozen_utc'] for r in rs)
                                   for s, rs in sorted(by_set.items())}
        row['requests_written_total'] = sum(row['requests_written'].values())

    sets = []
    for s, rs in sorted(by_set.items()):
        first, last = min(r['saved_utc'] for r in rs), max(r['saved_utc'] for r in rs)
        governing = [row for row in rows if row['experiment'] == 'B' and row['frozen_utc'] < first]
        sets.append(dict(set=s, requests=len(rs), first_saved=first, last_saved=last,
                         freezes_before_first_request=[row['record'] for row in governing],
                         sets_already_written=sum(1 for other, o in by_set.items()
                                                  if other != s and max(x['saved_utc'] for x in o) < first),
                         profile=profile([r['text'] for r in rs])))

    out = dict(freezes=rows, sets=sets,
               requests_total=len(requests),
               segment_name_pattern=SEGMENT_NAME, marking_pattern=MARKING)
    (args.expb / 'timeline.json').write_text(json.dumps(out, indent=1, ensure_ascii=False),
                                             encoding='utf-8')

    print('%-34s %-3s %-20s %s' % ('record', 'exp', 'frozen (UTC)', 'requests written by then'))
    for row in rows:
        print('%-34s %-3s %-20s %d %s' % (row['record'], row['experiment'],
                                          row['frozen_utc'][:19], row['requests_written_total'],
                                          row['requests_written']))
    print()
    keys = ['n', 'side', 'lobe', 'rank_read_by_v1', 'size', 'position_word',
            'measurement_word', 'marking', 'segment_name']
    print('set  ' + '  '.join('%-16s' % k for k in keys))
    for row in sets:
        print('%-4d ' % row['set'] + '  '.join('%-16s' % row['profile'].get(k, 0) for k in keys))
    print('\nwrote timeline.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
