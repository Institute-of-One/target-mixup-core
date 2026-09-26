"""How far do recorded semantics and coarse location distinguish targets on one CT series?

Items are segments of the audited SEGs (one item per segment). Items on the same CT series
are grouped into targets by geometry alone: they share a voxel centre (0.01 mm grid) or their
centroids lie within SAME_TARGET_MM. For every pair of items on different targets we record
whether the coded property (category, type, anatomic region) or the free-text SegmentLabel
differ, and the centroid distance, i.e. how precise a location given with a request would have
to be to tell the targets apart. Pixel data of the cached SEG files are read; no new downloads.

    python seg_census_targets.py --out <census dir>
"""
import argparse
import collections
import itertools
import json
from pathlib import Path

import numpy as np

from seg_point_match import read_seg, segment_voxels

SAME_TARGET_MM = 3.0


def meaning(item, name):
    codes = item.get(name, [])
    return str(codes[0].get('CodeMeaning', '')) if codes else ''


def items_for(record, cache):
    seg = read_seg(cache / 'seg' / f"{record['seg_series']}.zip")
    voxels, _ = segment_voxels(seg)
    out = []
    for s in seg.SegmentSequence:
        n = int(s.SegmentNumber)
        if n not in voxels:
            continue
        pts = voxels[n]
        out.append(dict(seg_series=record['seg_series'], segment=n, stratum=record['stratum'], patient=record['patient'],
                        label=str(s.get('SegmentLabel', '')),
                        codes=(meaning(s, 'SegmentedPropertyCategoryCodeSequence'),
                               meaning(s, 'SegmentedPropertyTypeCodeSequence'), meaning(s, 'AnatomicRegionSequence')),
                        centroid=pts.mean(axis=0), keys=set(map(tuple, np.round(pts, 2)))))
    return out


def ct_series_of(record):
    if record.get('ct'):
        return record['ct'][0]['series_uid']
    cands = [c for c in record.get('study_ct_series', []) if c['frame_of_reference'] == record['seg_frame_of_reference']]
    return cands[0]['series_uid'] if len(cands) == 1 else None


def group_targets(items):
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, j in itertools.combinations(range(len(items)), 2):
        a, b = items[i], items[j]
        if np.linalg.norm(a['centroid'] - b['centroid']) <= SAME_TARGET_MM or a['keys'] & b['keys']:
            parent[find(i)] = find(j)
    return [find(i) for i in range(len(items))]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    cache = args.out / 'cache'
    last = {}
    for line in filter(None, (args.out / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    by_ct = collections.defaultdict(list)
    skipped = collections.Counter()
    for r in last.values():
        uid = ct_series_of(r) if r['status'] in ('match', 'mismatch', 'no_referenced_series') else None
        if uid is None:
            skipped[r['status']] += 1
            continue
        by_ct[uid].extend(items_for(r, cache))
    stats = collections.defaultdict(collections.Counter)
    distances = collections.defaultdict(list)
    per_ct = []
    for uid, items in by_ct.items():
        roots = group_targets(items)
        targets = len(set(roots))
        # A CT series may carry SEGs of several producers; aggregate by collection.
        stratum = items[0]['stratum'].split(' | ')[0]
        st = stats[stratum]
        st['ct_series'] += 1
        st['items'] += len(items)
        st['ct_with_2plus_targets'] += targets >= 2
        for (i, a), (j, b) in itertools.combinations(enumerate(items), 2):
            if roots[i] == roots[j]:
                st['same_target_pairs'] += 1
                st['same_target_cross_producer'] += a['stratum'] != b['stratum']
                st['same_target_label_differs'] += a['label'] != b['label']
                st['same_target_codes_differ'] += a['codes'] != b['codes']
                continue
            st['cross_target_pairs'] += 1
            st['cross_same_producer'] += a['stratum'] == b['stratum']
            codes_same, label_same = a['codes'] == b['codes'], a['label'] == b['label']
            st['cross_codes_identical'] += codes_same
            st['cross_label_identical'] += label_same
            st['cross_codes_and_label_identical'] += codes_same and label_same
            distances[stratum].append(float(np.linalg.norm(a['centroid'] - b['centroid'])))
        per_ct.append(dict(ct_series=uid, collection=stratum, producers=sorted({it['stratum'] for it in items}),
                           patient=items[0]['patient'], items=len(items), targets=targets,
                           labels=sorted({it['label'] for it in items}), codes=sorted({' / '.join(it['codes']) for it in items})))
    spread = {k: dict(n=len(v), min=round(min(v), 1), p10=round(float(np.percentile(v, 10)), 1),
                      median=round(float(np.median(v)), 1)) for k, v in distances.items() if v}
    result = dict(same_target_mm=SAME_TARGET_MM, skipped_records=dict(skipped),
                  strata={k: dict(v) for k, v in sorted(stats.items())},
                  cross_target_centroid_distance_mm=spread, per_ct=per_ct)
    (args.out / 'targets.json').write_text(json.dumps(result, indent=1))
    for k, v in sorted(stats.items()):
        print(k, dict(v), spread.get(k))
    print('skipped', dict(skipped))


if __name__ == '__main__':
    main()
