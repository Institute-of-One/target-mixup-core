"""The lobe adjudication, one row per item, with what the reviewer could see.

Reviewer 3: "Please provide a per-item table with slice thickness, fissure
visibility, distance to lobe boundary, and the exact question wording."

Three of those were already recorded; slice thickness was not, and is read here
from the series each item came from. Fissure visibility was never asked as a
question, so it can only be reported as the reviewer's free-text note said it,
and the table says so rather than inventing a column of judgements.

The exact wording matters more than the reviewer may have known. Question 2 was

    Q2. Is the automatic lobe boundary near this nodule correct?
    問2. 色分けされた自動の肺葉の境界は、この結節の付近で正しいですか？

which presupposes that a boundary lies near the nodule. On three items it did
not, and the reviewer answered "incorrect" with a note saying exactly that: the
boundary could not be called near the nodule. That is a presupposition failure,
not a judgement that the map was wrong, and the option list offered no way to
say so. The 10 mm rule applied afterwards separates the items the question could
be asked of from the items it could not; it does not convert one answer into
another.

The same reviewer asked for the item coordinates, because the viewer is not
distributed. Each row now carries the CT SeriesInstanceUID and the nodule
centroid in patient coordinates, which is where the viewer put its fixed
crosshair, so the same view can be reproduced in any viewer from TCIA's own
copy of the images. It also carries the moment each answer was saved, and the
moments the author asked the AI assistant about fissures while the adjudication
was open, so a reader can see which answers were recorded before the assistant
was asked and which after.

    python expB_adjudication_table.py --expb <expB dir> --expa <expA dir>
"""
import argparse
import json
import re
from pathlib import Path

import pydicom

# The questions as the reviewer saw them (src/LobeReview.jsx).
QUESTIONS = {
    'q1': {'ja': '問1. 輪郭の結節は、どの肺葉にありますか？（画像のみで判定）',
           'en': 'Q1. Which lobe contains the outlined nodule? (images only)',
           'options': ['RUL', 'RML', 'RLL', 'LUL', 'LLL', 'undecidable']},
    'q2': {'ja': '問2. 色分けされた自動の肺葉の境界は、この結節の付近で正しいですか？',
           'en': 'Q2. Is the automatic lobe boundary near this nodule correct?',
           'options': ['correct', 'incorrect', 'undecidable']},
}
NEAR_MM = 10.0

# Phrases the reviewer used in the free-text notes. These are the only record of
# what was visible, because no question asked it.
FISSURE_NOT_VISIBLE = re.compile(r'葉間裂が同定できない|葉間裂が同定出来ない')
BOUNDARY_NOT_NEAR = re.compile(r'付近とはいえ|付近であると言えない|付近とは言え')
NODULE_ON_FISSURE = re.compile(r'葉間裂上に|葉間裂に接')
THICK_SLICE = re.compile(r'スライス厚が厚')


def series_dir(expb, patient, ct_series):
    """The directory holding the CT of this case, by patient and series UID."""
    for case in (expb / 'cases').iterdir():
        if not case.is_dir() or not case.name.startswith(patient):
            continue
        for sub in case.iterdir():
            if not sub.is_dir():
                continue
            first = next(iter(sorted(sub.glob('*.dcm'))), None)
            if first is None:
                continue
            ds = pydicom.dcmread(str(first), stop_before_pixels=True)
            if getattr(ds, 'SeriesInstanceUID', None) == ct_series:
                return sub
    return None


def geometry(path):
    files = sorted(path.glob('*.dcm'))
    ds = pydicom.dcmread(str(files[0]), stop_before_pixels=True)
    thickness = getattr(ds, 'SliceThickness', None)
    spacing = getattr(ds, 'SpacingBetweenSlices', None)
    # The interval actually reconstructed, which is what a reader sees, and which
    # can differ from SliceThickness.
    zs = []
    for f in files[:400]:
        d = pydicom.dcmread(str(f), stop_before_pixels=True)
        ipp = getattr(d, 'ImagePositionPatient', None)
        if ipp is not None:
            zs.append(float(ipp[2]))
    zs = sorted(zs)
    gaps = [round(b - a, 3) for a, b in zip(zs, zs[1:])]
    interval = min(set(gaps), key=gaps.count) if gaps else None
    if gaps:
        interval = max(set(gaps), key=gaps.count)
    return dict(slice_thickness_mm=float(thickness) if thickness is not None else None,
                spacing_between_slices_mm=float(spacing) if spacing is not None else None,
                reconstruction_interval_mm=interval,
                pixel_spacing_mm=[float(x) for x in getattr(ds, 'PixelSpacing', [])] or None,
                instances=len(files))


def saved_times(expb):
    """When each answer was written, from the viewer's own log."""
    out = {}
    for line in (expb / 'lobe_review' / 'answers.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        out[(a['id'], 'q1' if a['q1'] else 'q2')] = a['saved_utc']
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)

    results = json.loads((args.expb / 'paper_results.json').read_text(encoding='utf-8'))
    items = results['lobes']['items']
    requests = {}
    for line in (args.expb / 'requests_expert.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            requests[(r.get('set') or 1, r['case'])] = r
    centroids = {(s['ct_series'], t['target']): t['centroid_lps_mm']
                 for s in json.loads((args.expa / 'targets.json').read_text(encoding='utf-8'))['series']
                 for t in s['targets']}
    guidance = json.loads((args.expb / 'adjudication_guidance.json').read_text(encoding='utf-8'))
    asked = [t['utc'] for t in guidance['turns'] if t['who'] == 'assistant']
    when = saved_times(args.expb)

    rows = []
    for it in items:
        req = requests[(it['set'], it['case'])]
        path = series_dir(args.expb, req['patient'], req['ct_series'])
        geo = geometry(path) if path else {}
        note = it.get('note') or ''
        q1_at, q2_at = when.get((it['item'], 'q1')), when.get((it['item'], 'q2'))
        rows.append(dict(
            item=it['item'], role=it['role'], set=it['set'], case=it['case'],
            patient=req['patient'],
            # Where the viewer's fixed crosshair sat, so the view can be reproduced.
            ct_series_uid=req['ct_series'], target=req['target'],
            nodule_centroid_lps_mm=centroids.get((req['ct_series'], req['target'])),
            request_click_lps_mm=(req.get('click') or {}).get('lps_mm'),
            request_click_instance_number=(req.get('click') or {}).get('instance_number'),
            q1_saved_utc=q1_at, q2_saved_utc=q2_at,
            q1_after_the_assistant_was_asked=bool(q1_at and q1_at > asked[-1]),
            q2_after_the_assistant_was_asked=bool(q2_at and q2_at > asked[-1]),
            lobe_named_in_request=it['text_lobe'], lobe_of_the_map=it['map_lobe'],
            q1_expert_lobe=it['q1'], q2=it['q2'],
            distance_to_nearest_other_lobe_mm=it['fissure_mm'],
            boundary_within_near_threshold=it['fissure_mm'] <= NEAR_MM,
            # Recorded only where the reviewer wrote it; no question asked for it.
            fissure_reported_not_visible=bool(FISSURE_NOT_VISIBLE.search(note)),
            thick_slice_reported=bool(THICK_SLICE.search(note)),
            nodule_reported_on_the_fissure=bool(NODULE_ON_FISSURE.search(note)),
            note_says_boundary_not_near=bool(BOUNDARY_NOT_NEAR.search(note)),
            note=note or None,
            **geo))

    # What the 10 mm rule does, stated as a count rather than as a reclassification.
    applicable = [r for r in rows if r['boundary_within_near_threshold']]
    answers = sorted(when.values())
    out = dict(
        questions=QUESTIONS, near_threshold_mm=NEAR_MM, items=rows,
        n_items=len(rows),
        # The assistant was asked about fissures while the adjudication was open.
        # The record of what it was asked and answered is adjudication_guidance.json.
        guidance_asked_utc=asked,
        n_answers=len(answers),
        first_answer_utc=answers[0], last_answer_utc=answers[-1],
        n_answers_after_the_assistant_was_asked=sum(a > asked[-1] for a in answers),
        n_answers_before_the_assistant_was_asked=sum(a < asked[0] for a in answers),
        q1_undecidable=[r['item'] for r in rows if r['q1_expert_lobe'] == 'undecidable'],
        q1_undecidable_after_the_assistant_was_asked=[
            r['item'] for r in rows if r['q1_expert_lobe'] == 'undecidable'
            and r['q1_after_the_assistant_was_asked']],
        n_applicable=len(applicable),
        n_applicable_correct=sum(r['q2'] == 'correct' for r in applicable),
        n_not_applicable=len(rows) - len(applicable),
        n_not_applicable_answered_incorrect=sum(
            r['q2'] == 'incorrect' for r in rows if not r['boundary_within_near_threshold']),
        n_not_applicable_note_says_not_near=sum(
            r['note_says_boundary_not_near'] for r in rows
            if not r['boundary_within_near_threshold']),
    )
    (args.expb / 'lobe_adjudication_items.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    print('%-4s %-8s %-4s %-6s %-6s %-6s %-10s %-9s %s'
          % ('item', 'role', 'set', 'named', 'map', 'Q1', 'Q2', 'dist mm', 'slice mm'))
    for r in rows:
        print('%-4s %-8s %-4d %-6s %-6s %-6s %-10s %-9.1f %s'
              % (r['item'], r['role'], r['set'], r['lobe_named_in_request'] or '-',
                 r['lobe_of_the_map'], r['q1_expert_lobe'], r['q2'],
                 r['distance_to_nearest_other_lobe_mm'],
                 r.get('slice_thickness_mm')))
    print('\nthe question could be asked of %d of %d items (boundary within %.0f mm); '
          '%d of those were answered correct'
          % (out['n_applicable'], out['n_items'], NEAR_MM, out['n_applicable_correct']))
    print('of the %d it could not be asked of, %d were answered incorrect and %d of '
          'those notes say the boundary was not near the nodule'
          % (out['n_not_applicable'], out['n_not_applicable_answered_incorrect'],
             out['n_not_applicable_note_says_not_near']))
    print('the assistant was asked at %s; %d of %d answers were saved after that, %d '
          'before the first question; "cannot decide" on question 1: %s, of which %s '
          'came after'
          % (', '.join(a[11:19] for a in asked), out['n_answers_after_the_assistant_was_asked'],
             out['n_answers'], out['n_answers_before_the_assistant_was_asked'],
             ', '.join(out['q1_undecidable']) or 'none',
             ', '.join(out['q1_undecidable_after_the_assistant_was_asked']) or 'none'))
    print('written lobe_adjudication_items.json')


if __name__ == '__main__':
    main()
