"""Where else does a SEG's FrameOfReferenceUID occur in its study?

For each audited SEG in a stratum, reads one instance header of every series in the
same study and records which series share the SEG FoR and which share the CT FoR.
Headers only (one instance per series).

    python seg_census_study_for.py --out <census dir> [--stratum-prefix "LIDC-IDRI | QIN"]
"""
import argparse
import collections
import io
import json
from pathlib import Path

import pydicom

from seg_census import get


def first_header(series_uid):
    listing = json.loads(get('getSOPInstanceUIDs', SeriesInstanceUID=series_uid) or b'[]')
    if not listing:
        return None
    sop = sorted(x['SOPInstanceUID'] for x in listing)[0]
    return pydicom.dcmread(io.BytesIO(get('getSingleImage', SeriesInstanceUID=series_uid, SOPInstanceUID=sop)),
                           stop_before_pixels=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--stratum-prefix', default='LIDC-IDRI | QIN')
    args = ap.parse_args(argv)
    last = {}
    for line in filter(None, (args.out / 'records.jsonl').read_text().splitlines()):
        r = json.loads(line)
        last[r['seg_series']] = r
    plan = {s['SeriesInstanceUID']: s for s in json.loads((args.out / 'sample_plan.json').read_text())['series']}
    by_patient = collections.defaultdict(list)
    for r in last.values():
        if r['stratum'].startswith(args.stratum_prefix) and r['status'] in ('match', 'mismatch'):
            by_patient[r['patient']].append(r)
    result = []
    for patient, recs in sorted(by_patient.items()):
        study = plan[recs[0]['seg_series']]['StudyInstanceUID']
        seg_for, ct_for = recs[0]['seg_frame_of_reference'], recs[0]['ct'][0]['frame_of_reference']
        series = json.loads(get('getSeries', StudyInstanceUID=study) or b'[]')
        rows = []
        for s in sorted(series, key=lambda x: (x['Modality'], x.get('SeriesDescription', ''))):
            ds = first_header(s['SeriesInstanceUID'])
            f = str(ds.get('FrameOfReferenceUID', '')) if ds is not None else None
            rows.append(dict(modality=s['Modality'], description=s.get('SeriesDescription', ''),
                             manufacturer=s.get('Manufacturer', ''), series_date=s.get('SeriesDate', ''),
                             frame_of_reference=f, shares_seg_for=f == seg_for, shares_ct_for=f == ct_for))
        result.append(dict(patient=patient, status=recs[0]['status'], study=study, seg_for=seg_for, ct_for=ct_for,
                           same_seg_for_across_algorithms=len({x['seg_frame_of_reference'] for x in recs}) == 1,
                           series=rows))
        kinds = collections.Counter((x['modality'], 'SEG-FoR' if x['shares_seg_for'] else 'CT-FoR' if x['shares_ct_for']
                                     else 'other') for x in rows)
        print(patient, recs[0]['status'], dict(kinds), flush=True)
    (args.out / 'study_for.json').write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
