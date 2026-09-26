"""Header census of public lung-CT DICOM SEG objects against their source CT.

For each sampled SEG series in TCIA (NBIA v1 public API) this records whether the
SEG FrameOfReferenceUID equals that of the CT series it references, and whether
the referenced SOP instances exist in that CT series. Pixel data are not used.

Only public, openly licensed collections are queried. Downloaded files stay in the
caller-supplied output directory and must not be redistributed or committed.

    python seg_census.py --out <dir> [--lidc-qiicr-patients 100] [--seed 20260924]
"""
import argparse
import hashlib
import io
import json
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import pydicom

API = 'https://services.cancerimagingarchive.net/nbia-api/services/v1'
COLLECTIONS = ('LIDC-IDRI', 'RIDER Lung CT')
PAUSE = 0.2


def get(endpoint, retries=4, **params):
    url = f'{API}/{endpoint}?{urllib.parse.urlencode(params)}'
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as r:
                data = r.read()
            time.sleep(PAUSE)
            return data
        except Exception as exc:  # network errors are retried, then raised
            if attempt == retries - 1:
                raise RuntimeError(f'{endpoint} failed: {exc}') from exc
            time.sleep(5 * (attempt + 1))


def producer(series):
    desc = series.get('SeriesDescription', '')
    m = re.search(r'QIN CT challenge:?\s*(alg\d+)', desc)
    return f'QIN challenge {m.group(1)}' if m else series.get('Manufacturer') or 'unknown'


def sample(rng, lidc_qiicr_patients):
    """All SEG series, except a patient-level random sample of LIDC-IDRI QIICR."""
    chosen = []
    for collection in COLLECTIONS:
        series = json.loads(get('getSeries', Collection=collection, Modality='SEG'))
        for s in series:
            s['stratum'] = f"{collection} | {producer(s)}"
        big = 'LIDC-IDRI | QIICR'
        patients = sorted({s['PatientID'] for s in series if s['stratum'] == big})
        keep = set(rng.sample(patients, min(lidc_qiicr_patients, len(patients))))
        chosen += [s for s in series if s['stratum'] != big or s['PatientID'] in keep]
    return sorted(chosen, key=lambda s: (s['stratum'], s['PatientID'], s['SeriesInstanceUID']))


def cached(path, fetch):
    if not path.exists():
        data = fetch()
        tmp = path.with_suffix('.part')
        tmp.write_bytes(data)
        tmp.replace(path)
    return path.read_bytes()


def seg_file(cache, uid):
    blob = cached(cache / 'seg' / f'{uid}.zip', lambda: get('getImage', SeriesInstanceUID=uid))
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith('.dcm')]
        if len(names) != 1:
            raise RuntimeError(f'expected one SEG instance, found {len(names)}')
        raw = z.read(names[0])
    return raw, hashlib.sha256(raw).hexdigest()


def referenced(ds):
    """Referenced (series UID -> SOP UIDs) from the header and per-frame sources."""
    refs = {}
    for item in ds.get('ReferencedSeriesSequence', []):
        sops = {i.ReferencedSOPInstanceUID for i in item.get('ReferencedInstanceSequence', [])}
        refs.setdefault(item.SeriesInstanceUID, set()).update(sops)
    frame_sops = set()
    for frame in ds.get('PerFrameFunctionalGroupsSequence', []):
        for der in frame.get('DerivationImageSequence', []):
            for src in der.get('SourceImageSequence', []):
                frame_sops.add(src.ReferencedSOPInstanceUID)
    return refs, frame_sops


def ct_info(cache, uid):
    path = cache / 'ct' / f'{uid}.json'
    if path.exists():
        return json.loads(path.read_text())
    listing = json.loads(get('getSOPInstanceUIDs', SeriesInstanceUID=uid) or b'[]')
    sops = sorted(x['SOPInstanceUID'] for x in listing)
    info = dict(series_uid=uid, instances=len(sops), sops=sops, frame_of_reference=None)
    if sops:
        raw = get('getSingleImage', SeriesInstanceUID=uid, SOPInstanceUID=sops[0])
        ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True)
        info.update(frame_of_reference=ds.get('FrameOfReferenceUID'), modality=ds.get('Modality'),
                    probe_sop=sops[0], probe_sha256=hashlib.sha256(raw).hexdigest())
    path.write_text(json.dumps(info))
    return info


def audit(cache, s):
    raw, digest = seg_file(cache, s['SeriesInstanceUID'])
    ds = pydicom.dcmread(io.BytesIO(raw), stop_before_pixels=True)
    refs, frame_sops = referenced(ds)
    all_sops = set().union(*refs.values(), frame_sops) if refs else set(frame_sops)
    record = dict(stratum=s['stratum'], patient=s['PatientID'], seg_series=s['SeriesInstanceUID'],
                  seg_sha256=digest, seg_frame_of_reference=ds.get('FrameOfReferenceUID'),
                  software=str(ds.get('SoftwareVersions', '')), segments=len(ds.get('SegmentSequence', [])),
                  frames=int(ds.get('NumberOfFrames', 0)), referenced_series=sorted(refs),
                  referenced_sops=len(all_sops))
    cts = []
    for uid in sorted(refs):
        ct = ct_info(cache, uid)
        present = set(ct['sops'])
        cts.append(dict(series_uid=uid, instances=ct['instances'], frame_of_reference=ct['frame_of_reference'],
                        modality=ct.get('modality'),
                        sops_found=len(all_sops & present), sops_missing=len(all_sops - present)))
    record['ct'] = cts
    if not cts:
        # No source references at all: the only link to an image series is the study and
        # the Frame of Reference UID. Count the CT series in the study that could be the source.
        study = str(ds.StudyInstanceUID)
        listing = json.loads(get('getSeries', StudyInstanceUID=study) or b'[]')
        candidates = [ct_info(cache, x['SeriesInstanceUID']) for x in sorted(listing, key=lambda x: x['SeriesInstanceUID'])
                      if x.get('Modality') == 'CT']
        record['study_ct_series'] = [dict(series_uid=c['series_uid'], instances=c['instances'],
                                          frame_of_reference=c['frame_of_reference']) for c in candidates]
        record['for_candidates'] = sum(c['frame_of_reference'] == record['seg_frame_of_reference'] for c in candidates)
    fors = {c['frame_of_reference'] for c in cts}
    record['status'] = ('no_referenced_series' if not cts else
                        'ct_unavailable' if None in fors else
                        'match' if fors == {record['seg_frame_of_reference']} else 'mismatch')
    record['sop_references_resolved'] = bool(cts) and all(c['sops_missing'] == 0 for c in cts)
    return record


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--lidc-qiicr-patients', type=int, default=100)
    ap.add_argument('--seed', type=int, default=20260924)
    ap.add_argument('--limit', type=int, default=None, help='debug: audit only the first N')
    args = ap.parse_args(argv)
    cache = args.out / 'cache'
    for sub in ('seg', 'ct'):
        (cache / sub).mkdir(parents=True, exist_ok=True)
    plan_path = args.out / 'sample_plan.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        plan = dict(api=API, collections=COLLECTIONS, seed=args.seed,
                    lidc_qiicr_patients=args.lidc_qiicr_patients,
                    created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    series=sample(random.Random(args.seed), args.lidc_qiicr_patients))
        plan_path.write_text(json.dumps(plan, indent=1))
    series = plan['series'][:args.limit] if args.limit else plan['series']
    records_path = args.out / 'records.jsonl'
    done = set()
    if records_path.exists():
        # Errors are retried on the next run; the summary keeps the last record per series.
        done = {r['seg_series'] for r in map(json.loads, filter(None, records_path.read_text().splitlines()))
                if r['status'] != 'error'
                and not (r['status'] == 'no_referenced_series' and 'for_candidates' not in r)}
    failures = 0
    with records_path.open('a') as out:
        for i, s in enumerate(series, 1):
            if s['SeriesInstanceUID'] in done:
                continue
            try:
                rec = audit(cache, s)
            except Exception as exc:
                failures += 1
                rec = dict(stratum=s['stratum'], patient=s['PatientID'], seg_series=s['SeriesInstanceUID'],
                           status='error', error=str(exc)[:300])
            out.write(json.dumps(rec) + '\n')
            out.flush()
            print(f"{i}/{len(series)} {rec['status']:>20} {s['stratum']} {s['PatientID']}", flush=True)
    print(f'errors this run: {failures}')


if __name__ == '__main__':
    sys.exit(main())
