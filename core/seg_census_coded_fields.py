"""What the audited SEGs actually record about what they segmented, field by field.

Section 3.1 says the coded semantics were identical for every pair of segments on
different targets of one CT. A count alone does not say what was compared or how
complete the fields were, so this writes both:

1. A completeness census over every audited SEG, from headers only. For each
   descriptive field it counts the segments where the field is absent, present but
   empty, and present with a value, and for the coded fields it counts the
   sub-elements (coding scheme, code value, code meaning) that are missing or
   empty. It also counts the two fields DICOM provides for identity, TrackingID and
   TrackingUID, because an absent identity field is the finding.

2. The per-pair table: one row for every pair of segments on different targets of
   the same LIDC-IDRI CT series, carrying each side's three coded concepts as
   (scheme, value, meaning) and its free-text label. The comparison rule is on one
   line in `same_concepts`, and the row records what it returned, so the claim can
   be recomputed from the table without this script.

Targets are grouped exactly as in seg_census_targets.py (shared voxel centre or
centroids within SAME_TARGET_MM), which needs pixel data; the cached SEG files are
read and nothing is downloaded.

    python seg_census_coded_fields.py --census <census dir>
"""
import argparse
import collections
import csv
import io
import itertools
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pydicom

import seg_census_targets as sct
from seg_point_match import read_seg, segment_voxels

sys.stdout.reconfigure(encoding='utf-8')

# The three coded fields a SEG uses to say what a segment is, and the free text beside
# them. Category and type are required by the standard; the anatomic region is not.
CODED = [('category', 'SegmentedPropertyCategoryCodeSequence', 1),
         ('type', 'SegmentedPropertyTypeCodeSequence', 1),
         ('anatomic_region', 'AnatomicRegionSequence', 3)]
TEXT = [('label', 'SegmentLabel', 1), ('description', 'SegmentDescription', 3)]
# What DICOM offers for identity rather than for kind. Type 1C: required only when the
# segment is tracked, so absence is conformant and is exactly the point.
IDENTITY = [('tracking_id', 'TrackingID', '1C'), ('tracking_uid', 'TrackingUID', '1C')]
TRIPLE = ('CodingSchemeDesignator', 'CodeValue', 'CodeMeaning')


def concept(segment, keyword):
    """(scheme, value, meaning) of the first item, with '' for anything absent."""
    seq = segment.get(keyword)
    if not seq or len(seq) == 0:
        return ('', '', '')
    item = seq[0]
    return tuple(str(item.get(k, '') or '') for k in TRIPLE)


def same_concepts(a, b):
    """The comparison rule of Section 3.1: the three concepts, each as scheme, value
    and meaning, must be equal element for element."""
    return all(a[name] == b[name] for name, _, _ in CODED)


def header(path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith('.dcm'))
        return pydicom.dcmread(io.BytesIO(z.read(name)), stop_before_pixels=True)


def last_records(census):
    last = {}
    for line in filter(None, (census / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    return last


def completeness(census, records):
    """Field-by-field counts over every audited SEG, from headers only."""
    per_stratum = collections.defaultdict(collections.Counter)
    triples = {name: collections.Counter() for name, _, _ in CODED}
    # Which producers wrote each concept: the same code value carries different
    # meanings in different strata, which is only visible side by side.
    producers = {name: collections.defaultdict(collections.Counter) for name, _, _ in CODED}
    series = segments = 0
    for r in sorted(records.values(), key=lambda r: r['seg_series']):
        if r['status'] == 'error':
            continue
        ds = header(census / 'cache' / 'seg' / ('%s.zip' % r['seg_series']))
        c = per_stratum[r['stratum']]
        c['series'] += 1
        series += 1
        for s in ds.get('SegmentSequence', []):
            c['segments'] += 1
            segments += 1
            for name, keyword, _ in CODED:
                seq = s.get(keyword)
                if seq is None:
                    c['%s_absent' % name] += 1
                    continue
                if len(seq) == 0:
                    c['%s_empty' % name] += 1
                    continue
                c['%s_present' % name] += 1
                item = seq[0]
                for k in TRIPLE:
                    if not str(item.get(k, '') or '').strip():
                        c['%s_%s_missing' % (name, k)] += 1
                key = json.dumps(concept(s, keyword))
                triples[name][key] += 1
                producers[name][key][r['stratum']] += 1
            for name, keyword, _ in TEXT + IDENTITY:
                value = s.get(keyword)
                if value is None:
                    c['%s_absent' % name] += 1
                elif not str(value).strip():
                    c['%s_empty' % name] += 1
                else:
                    c['%s_present' % name] += 1
    concepts = {}
    for name, _, _ in CODED:
        concepts[name] = [dict(scheme=json.loads(k)[0], value=json.loads(k)[1],
                               meaning=json.loads(k)[2], segments=n,
                               producers=sorted(producers[name][k]))
                          for k, n in triples[name].most_common()]
    return dict(series=series, segments=segments,
                per_stratum={k: dict(v) for k, v in sorted(per_stratum.items())},
                distinct_concepts=concepts)


def tracking(census, records, stratum='LIDC-IDRI | QIICR'):
    """What the one stratum that fills TrackingID and TrackingUID puts in them.

    DICOM does offer a field for identity rather than kind. Where it is filled here
    it carries the collection's own nodule number, so the question is whether it
    agrees with the number in the series description and whether the UID groups the
    annotations of one nodule and separates different nodules of the same CT.
    """
    plan = {s['SeriesInstanceUID']: s for s in
            json.loads((census / 'sample_plan.json').read_text())['series']}
    out = collections.Counter()
    uid_of = collections.defaultdict(set)      # (patient, nodule) -> TrackingUIDs
    nodule_of = collections.defaultdict(set)   # (patient, TrackingUID) -> nodule numbers
    for r in records.values():
        if r['stratum'] != stratum or r['status'] == 'error':
            continue
        ds = header(census / 'cache' / 'seg' / ('%s.zip' % r['seg_series']))
        desc = plan[r['seg_series']].get('SeriesDescription', '')
        m = re.search(r'Nodule (\d+)', desc)
        for s in ds.get('SegmentSequence', []):
            out['segments'] += 1
            tid, tuid = str(s.get('TrackingID', '') or ''), str(s.get('TrackingUID', '') or '')
            if not m:
                out['no_nodule_number_in_description'] += 1
                continue
            out['tracking_id_is_nodule_number'] += tid == 'Nodule %s' % m.group(1)
            uid_of[(r['patient'], m.group(1))].add(tuid)
            nodule_of[(r['patient'], tuid)].add(m.group(1))
    out['nodules'] = len(uid_of)
    out['nodules_with_one_uid'] = sum(len(v) == 1 for v in uid_of.values())
    out['uids_with_one_nodule'] = sum(len(v) == 1 for v in nodule_of.values())
    out['uids'] = len(nodule_of)
    return dict(out, stratum=stratum)


def items_for(record, cache):
    """Segments of one SEG with their concepts, labels and voxel geometry."""
    seg = read_seg(cache / 'seg' / ('%s.zip' % record['seg_series']))
    voxels, _ = segment_voxels(seg)
    out = []
    for s in seg.SegmentSequence:
        n = int(s.SegmentNumber)
        if n not in voxels:
            continue
        pts = voxels[n]
        row = dict(seg_series=record['seg_series'], segment=n, stratum=record['stratum'],
                   patient=record['patient'], label=str(s.get('SegmentLabel', '') or ''),
                   centroid=pts.mean(axis=0), keys=set(map(tuple, np.round(pts, 2))))
        for name, keyword, _ in CODED:
            row[name] = concept(s, keyword)
        out.append(row)
    return out


def pair_table(census, records, collection):
    """One row per pair of segments on different targets of the same CT series."""
    cache = census / 'cache'
    by_ct = collections.defaultdict(list)
    for r in records.values():
        if not r['stratum'].startswith(collection + ' |'):
            continue
        if r['status'] not in ('match', 'mismatch', 'no_referenced_series'):
            continue
        uid = sct.ct_series_of(r)
        if uid is not None:
            by_ct[uid].extend(items_for(r, cache))
    rows, counts = [], collections.Counter()
    for uid, its in sorted(by_ct.items()):
        roots = sct.group_targets(its)
        if len(set(roots)) < 2:
            continue
        counts['ct_series'] += 1
        counts['targets'] += len(set(roots))
        counts['segments'] += len(its)
        order = {root: k + 1 for k, root in enumerate(sorted(set(roots), key=roots.index))}
        for (i, a), (j, b) in itertools.combinations(enumerate(its), 2):
            if roots[i] == roots[j]:
                continue
            counts['pairs'] += 1
            codes_same, label_same = same_concepts(a, b), a['label'] == b['label']
            counts['concepts_identical'] += codes_same
            counts['labels_identical'] += label_same
            row = dict(ct_series=uid, patient=a['patient'],
                       target_a=order[roots[i]], target_b=order[roots[j]],
                       concepts_identical=int(codes_same), labels_identical=int(label_same),
                       centroid_distance_mm=round(float(np.linalg.norm(a['centroid'] - b['centroid'])), 1))
            for side, it in (('a', a), ('b', b)):
                for name, _, _ in CODED:
                    scheme, value, meaning = it[name]
                    row['%s_%s_scheme' % (side, name)] = scheme
                    row['%s_%s_value' % (side, name)] = value
                    row['%s_%s_meaning' % (side, name)] = meaning
                row['%s_label' % side] = it['label']
            rows.append(row)
    return rows, dict(counts)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--collection', default='LIDC-IDRI')
    args = ap.parse_args(argv)
    records = last_records(args.census)

    fields = completeness(args.census, records)
    print('completeness: %d series, %d segments' % (fields['series'], fields['segments']))

    fields['tracking'] = tracking(args.census, records)
    tr = fields['tracking']
    print('tracking: %d of %d segments carry the nodule number of their series description; '
          '%d of %d nodules have one TrackingUID' % (tr['tracking_id_is_nodule_number'],
          tr['segments'], tr['nodules_with_one_uid'], tr['nodules']))

    rows, counts = pair_table(args.census, records, args.collection)
    print('%s: %d pairs on %d CT series, concepts identical in %d, labels in %d'
          % (args.collection, counts['pairs'], counts['ct_series'],
             counts['concepts_identical'], counts['labels_identical']))

    out = args.census / 'cross_target_pairs.csv'
    with out.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print('wrote %s (%d rows)' % (out.name, len(rows)))

    fields['cross_target_pairs'] = dict(counts, collection=args.collection,
                                        same_target_mm=sct.SAME_TARGET_MM,
                                        rule=' '.join(same_concepts.__doc__.split()))
    (args.census / 'coded_fields.json').write_text(json.dumps(fields, indent=1), encoding='utf-8')
    print('wrote coded_fields.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
