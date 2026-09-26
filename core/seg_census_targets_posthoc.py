"""Post hoc checks of the target analysis (2026-09-25, after the Codex review).

1. Codes compared as concepts (CodingSchemeDesignator + CodeValue) instead of CodeMeaning strings.
2. Geometric target grouping compared with the QIICR nodule identifiers ("Nodule k" in the series
   description, i.e. the clustered nodule of Fedorov et al. 2020), with a threshold sensitivity.
3. What the cross-target pairs consist of: patients, series, targets and annotations.

    python seg_census_targets_posthoc.py --census <census dir>
"""
import argparse
import collections
import itertools
import json
import re
from pathlib import Path

import numpy as np

import seg_census_targets as sct
from seg_point_match import read_seg, segment_voxels


def concept(item, name):
    codes = item.get(name, [])
    return (str(codes[0].get('CodingSchemeDesignator', '')), str(codes[0].get('CodeValue', ''))) if codes else ('', '')


def items(census):
    last = {}
    for line in filter(None, (census / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    plan = {s['SeriesInstanceUID']: s for s in json.loads((census / 'sample_plan.json').read_text())['series']}
    by_ct = collections.defaultdict(list)
    for r in last.values():
        if r['stratum'] != 'LIDC-IDRI | QIICR' or r['status'] not in ('match', 'mismatch') or not r['ct']:
            continue
        seg = read_seg(census / 'cache' / 'seg' / f"{r['seg_series']}.zip")
        voxels, _ = segment_voxels(seg)
        nodule = re.search(r'Nodule (\d+)', plan[r['seg_series']].get('SeriesDescription', ''))
        for s in seg.SegmentSequence:
            n = int(s.SegmentNumber)
            if n in voxels:
                pts = voxels[n]
                by_ct[r['ct'][0]['series_uid']].append(dict(
                    patient=r['patient'], seg_series=r['seg_series'], nodule=nodule.group(1) if nodule else None,
                    label=str(s.get('SegmentLabel', '')),
                    codes=(concept(s, 'SegmentedPropertyCategoryCodeSequence'),
                           concept(s, 'SegmentedPropertyTypeCodeSequence'), concept(s, 'AnatomicRegionSequence')),
                    centroid=pts.mean(axis=0), keys=set(map(tuple, np.round(pts, 2)))))
    return by_ct


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    args = ap.parse_args(argv)
    by_ct = items(args.census)
    out = dict(sensitivity={})
    for mm in (0.0, 1.5, 3.0, 5.0, 10.0):
        sct.SAME_TARGET_MM = mm
        agree = split = merged = targets_total = 0
        for its in by_ct.values():
            roots = sct.group_targets(its)
            targets_total += len(set(roots))
            geo = collections.defaultdict(set)
            ids = collections.defaultdict(set)
            for it, root in zip(its, roots):
                geo[root].add(it['nodule'])
                ids[it['nodule']].add(root)
            merged += sum(len(v) > 1 for v in geo.values())      # one geometric target, several nodule IDs
            split += sum(len(v) > 1 for v in ids.values())       # one nodule ID, several geometric targets
            agree += sum(len(v) == 1 and len(ids[next(iter(v))]) == 1 for v in geo.values())
        out['sensitivity'][str(mm)] = dict(targets=targets_total, one_to_one_with_nodule_id=agree,
                                           targets_merging_ids=merged, ids_split_over_targets=split)
    # Primary threshold (3 mm): cross-target pairs by concept codes and composition.
    sct.SAME_TARGET_MM = 3.0
    pairs = same_codes = 0
    patients, series, targets, annotations = set(), set(), 0, 0
    code_sets = collections.Counter()
    for ct, its in by_ct.items():
        roots = sct.group_targets(its)
        if len(set(roots)) < 2:
            continue
        patients.add(its[0]['patient'])
        series.add(ct)
        targets += len(set(roots))
        annotations += len(its)
        for (i, a), (j, b) in itertools.combinations(enumerate(its), 2):
            if roots[i] != roots[j]:
                pairs += 1
                same_codes += a['codes'] == b['codes']
        for it in its:
            code_sets[json.dumps(it['codes'])] += 1
    out['cross_target_pairs'] = dict(pairs=pairs, identical_concept_codes=same_codes, patients=len(patients),
                                     series=len(series), targets=targets, annotations=annotations,
                                     distinct_code_triples=len(code_sets), code_triples=dict(code_sets))
    (args.census / 'targets_posthoc_20260925.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
