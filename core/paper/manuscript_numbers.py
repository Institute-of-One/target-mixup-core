"""Collect every number the manuscript quotes from the frozen result files.

Nothing in the manuscript is typed by hand: the build substitutes {{key}} from numbers.json.
Each value records its source file so a reader can trace it.

    python manuscript_numbers.py --census <census dir> --expa <expA dir> --expb <expB dir> --out <build dir>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import labels  # noqa: E402
# The reproducibility table quotes the endpoint, the model name and the confidence
# threshold from the modules that use them, so the table cannot drift from the code.
import expA_jev  # noqa: E402
import expB_readers_v2  # noqa: E402
import expB_readers_v3  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')   # the data here is Japanese; a cp932 console kills the first print


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def latest_jsonl(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            out[r['dataset']] = r
    return out


def pct(a, b, digits=0):
    return f'{100 * a / b:.{digits}f}'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    n, src = {}, {}

    def put(key, value, source):
        n[key], src[key] = value, source

    # Parser and condition names, so Table 1 interpolates the same strings the
    # figures draw instead of carrying its own hand-typed copy (see labels.py).
    for code, words in labels.readers_b_flat() + labels.CONDITIONS_A:
        put(f'label_{code}', labels.table_form(code, words), 'paper/labels.py')

    summary = load(args.census / 'summary.json')
    strata = summary['strata']
    total = summary['audited']
    put('census_series', total, 'summary.json')
    mism = sum(v['series'].get('mismatch', 0) for v in strata.values())
    unref = sum(v['series'].get('no_referenced_series', 0) for v in strata.values())
    match = sum(v['series'].get('match', 0) for v in strata.values())
    resolved_mism = sum(v['series'].get('mismatch', 0) for v in strata.values())  # all mismatches resolve (checked below)
    assert all(v['series'].get('sops_unresolved', 0) == 0 for v in strata.values()), 'unresolved references present'
    put('census_match', match, 'summary.json')
    put('census_for_mismatch', mism, 'summary.json')
    put('census_for_mismatch_pct', pct(mism, total), 'summary.json')
    put('census_unreferenced', unref, 'summary.json')
    put('census_unreferenced_pct', pct(unref, total), 'summary.json')
    put('census_mismatch_resolved', resolved_mism, 'summary.json')
    siemens = strata['RIDER Lung CT | Siemens Corporate Research']['series']
    put('siemens_for_one_candidate', siemens.get('unreferenced_for_candidates_1', 0), 'summary.json')
    put('siemens_for_two_candidates', siemens.get('unreferenced_for_candidates_2+', 0), 'summary.json')
    # The listing each stratum was drawn from, so a proportion has a denominator.
    # This used to be the count of patients whose series came out matching, which
    # equals the planned 100 only as long as no patient's series all mismatch.
    pop = load(args.census / 'population.json')
    sampled, seed = pop['sampled_stratum'], pop['seed']
    put('pop_listed_series', pop['totals']['listed_series'], 'population.json')
    put('pop_seed', str(pop['seed']), 'population.json')   # a seed is a name, not a quantity
    put('pop_accessed', pop['accessed'][:10], 'population.json')
    put('pop_audited_pct', pct(pop['totals']['drawn_series'], pop['totals']['listed_series']), 'population.json')
    put('lidc_qiicr_patients_sampled', pop['drawn'][sampled]['patients'], 'population.json')
    put('lidc_qiicr_patients_listed', pop['listed'][sampled]['patients'], 'population.json')
    put('lidc_qiicr_series_listed', pop['listed'][sampled]['series'], 'population.json')
    put('lidc_qiicr_patients_pct', pct(pop['drawn'][sampled]['patients'],
                                       pop['listed'][sampled]['patients']), 'population.json')
    put('strata_n', len(labels.STRATA), 'paper/labels.py')
    for key, collection, producer in labels.STRATA:
        slug = labels.stratum_slug(collection, producer)
        put(f'st_{slug}_collection', collection, 'paper/labels.py')
        put(f'st_{slug}_producer', producer, 'paper/labels.py')
        put(f'st_{slug}_listed', pop['listed'][key]['series'], 'population.json')
        put(f'st_{slug}_listed_pat', pop['listed'][key]['patients'], 'population.json')
        put(f'st_{slug}_series', pop['drawn'][key]['series'], 'population.json')
        put(f'st_{slug}_patients', pop['drawn'][key]['patients'], 'population.json')
        # The counts are in the columns beside this one; the cell says how, not how many.
        put(f'st_{slug}_rule',
            ('at random, seed %s' % seed) if key == sampled else 'all',
            'population.json')
    qin = strata['LIDC-IDRI | QIN challenge alg01']['patients']
    put('lidc_qin_pat_mismatch', qin.get('mismatch', 0), 'summary.json')
    put('lidc_qin_pat_match', qin.get('match', 0), 'summary.json')
    put('lidc_qin_pat_total', qin.get('mismatch', 0) + qin.get('match', 0), 'summary.json')
    put('pydicom_pat', strata['RIDER Lung CT | pydicom-seg']['patients']['mismatch'], 'summary.json')
    study_for = load(args.census / 'study_for.json')
    per_study = {sum(1 for x in s['series'] if x['modality'] == 'SEG' and x['shares_seg_for']
                     and 'QIN' in x['description']) for s in study_for}
    assert len(per_study) == 1, per_study
    put('qin_segs_per_study', per_study.pop(), 'study_for.json')

    # How complete the descriptive fields are, and what distinct concepts occur.
    # The pair counts come from the file that also records the comparison rule, so
    # the rule the manuscript states and the number it quotes cannot drift apart.
    cf = load(args.census / 'coded_fields.json')
    cfs = {k: sum(v.get(k, 0) for v in cf['per_stratum'].values())
           for k in ('segments', 'anatomic_region_absent', 'anatomic_region_empty',
                     'category_absent', 'category_empty', 'type_absent', 'type_empty',
                     'label_absent', 'label_empty', 'description_absent',
                     'tracking_id_absent', 'tracking_id_present')}
    put('cf_series', cf['series'], 'coded_fields.json')
    put('cf_segments', cf['segments'], 'coded_fields.json')
    assert cfs['segments'] == cf['segments'], 'per-stratum segments do not sum to the total'
    for name in ('category', 'type', 'label'):
        assert cfs[f'{name}_absent'] == cfs[f'{name}_empty'] == 0, f'{name} absent or empty'
    put('cf_required_missing', 0, 'coded_fields.json')
    put('cf_region_absent', cfs['anatomic_region_absent'], 'coded_fields.json')
    put('cf_region_present', cf['segments'] - cfs['anatomic_region_absent'], 'coded_fields.json')
    put('cf_description_absent', cfs['description_absent'], 'coded_fields.json')
    put('cf_tracking_absent', cfs['tracking_id_absent'], 'coded_fields.json')
    put('cf_tracking_present', cfs['tracking_id_present'], 'coded_fields.json')
    # Sub-elements: no present coded field lacked a scheme, a value or a meaning.
    missing_parts = sum(v.get(f'{name}_{part}_missing', 0) for v in cf['per_stratum'].values()
                        for name in ('category', 'type', 'anatomic_region')
                        for part in ('CodingSchemeDesignator', 'CodeValue', 'CodeMeaning'))
    put('cf_subelements_missing', missing_parts, 'coded_fields.json')
    FIELD_WORDS = dict(category='Category', type='Type', anatomic_region='Anatomic region')
    rows = 0
    for field, concepts in cf['distinct_concepts'].items():
        put(f'cf_{field}_n', len(concepts), 'coded_fields.json')
        put(f'cf_{field}_values', len({c['value'] for c in concepts}), 'coded_fields.json')
        put(f'cf_{field}_meanings', len({c['meaning'] for c in concepts}), 'coded_fields.json')
        for i, c in enumerate(concepts, 1):
            rows += 1
            put(f'cf_{field}_{i}_field', FIELD_WORDS[field], 'coded_fields.json')
            put(f'cf_{field}_{i}_scheme', c['scheme'], 'coded_fields.json')
            put(f'cf_{field}_{i}_value', c['value'], 'coded_fields.json')
            put(f'cf_{field}_{i}_meaning', c['meaning'], 'coded_fields.json')
            put(f'cf_{field}_{i}_segments', c['segments'], 'coded_fields.json')
            put(f'cf_{field}_{i}_producers', labels.compact_producers(c['producers']),
                'coded_fields.json')
    put('cf_concept_rows', rows, 'coded_fields.json')
    # One code value with two different recorded meanings is the reason the rule matters.
    clash = sum(len({c['meaning'] for c in concepts if c['value'] == value}) > 1
                for concepts in cf['distinct_concepts'].values()
                for value in {c['value'] for c in concepts})
    put('cf_value_meaning_clashes', clash, 'coded_fields.json')
    tr = cf['tracking']
    put('cf_track_segments', tr['segments'], 'coded_fields.json')
    put('cf_track_is_nodule_number', tr['tracking_id_is_nodule_number'], 'coded_fields.json')
    put('cf_track_nodules', tr['nodules'], 'coded_fields.json')
    put('cf_track_one_uid', tr['nodules_with_one_uid'], 'coded_fields.json')
    cp3 = cf['cross_target_pairs']
    put('cf_pairs', cp3['pairs'], 'coded_fields.json')
    put('cf_pairs_concepts_identical', cp3['concepts_identical'], 'coded_fields.json')
    put('cf_pairs_labels_identical', cp3['labels_identical'], 'coded_fields.json')
    put('cf_pair_segments', cp3['segments'], 'coded_fields.json')

    targets = load(args.census / 'targets.json')
    lidc = targets['strata']['LIDC-IDRI']
    put('lidc_cross_pairs', lidc['cross_target_pairs'], 'targets.json')
    put('lidc_cross_codes_identical', lidc['cross_codes_identical'], 'targets.json')
    put('lidc_same_pairs', lidc['same_target_pairs'], 'targets.json')
    put('lidc_same_label_differs', lidc['same_target_label_differs'], 'targets.json')
    put('lidc_same_label_differs_pct', pct(lidc['same_target_label_differs'], lidc['same_target_pairs']), 'targets.json')
    put('lidc_ct_multi_target', lidc['ct_with_2plus_targets'], 'targets.json')
    d = targets['cross_target_centroid_distance_mm']['LIDC-IDRI']
    put('lidc_cross_dist_min', d['min'], 'targets.json')
    put('lidc_cross_dist_median', d['median'], 'targets.json')

    # The two halves of the RIDER claim, kept apart: where each SEG lies relative to
    # the documented lesion is arithmetic (rider_targets.json); what the Siemens SEGs
    # lie on instead is the author's judgement (target_reviews.jsonl, further down).
    rt = load(args.census / 'rider_targets.json')
    src_rt = 'rider_targets.json'
    segs = [s for case in rt['cases'] for s in case['segments']]
    qiicr = [s for s in segs if 'QIICR' in s['stratum']]
    siemens = [s for s in segs if 'Siemens' in s['stratum']]
    put('rider_target_series', len(rt['cases']), src_rt)
    put('rider_qiicr_segments', len(qiicr), src_rt)
    put('rider_qiicr_covering', sum(s['covers_noted_voxel'] for s in qiicr), src_rt)
    put('rider_qiicr_centroid_min', min(s['distance_to_note_centroid_mm'] for s in qiicr), src_rt)
    put('rider_qiicr_centroid_max', max(s['distance_to_note_centroid_mm'] for s in qiicr), src_rt)
    put('rider_siemens_segments', len(siemens), src_rt)
    put('rider_siemens_covering', sum(s['covers_noted_voxel'] for s in siemens), src_rt)
    put('rider_siemens_nearest_min', min(s['distance_to_note_nearest_mm'] for s in siemens), src_rt)
    put('rider_siemens_nearest_max', max(s['distance_to_note_nearest_mm'] for s in siemens), src_rt)
    put('rider_siemens_x_min', min(s['separation_x_mm'] for s in siemens), src_rt)
    thickness = sorted({c['slice_thickness_mm'] for c in rt['cases']})
    assert len(thickness) == 1, thickness
    put('rider_target_thickness', thickness[0], src_rt)
    readings = {c['note']['reading'] for c in rt['cases']}
    assert len(readings) == 1, readings
    put('rider_note_reading', readings.pop().replace('_', ' '), src_rt)
    put('rider_note_other_reading_min',
        round(min(max(c['note']['anchor_distance_mm'].values()) for c in rt['cases'])), src_rt)

    # The acquisition each spot check was viewed on, and when the selection was frozen.
    sd = load(args.census / 'spot_detail.json')
    thick = sorted({t for c in sd['checks'] for t in c['slice_thickness_mm']})
    put('spot_thickness_min', thick[0], 'spot_detail.json')
    put('spot_thickness_max', thick[-1], 'spot_detail.json')
    put('spot_frozen', sd['frozen_at'][:10], 'spot_detail.json')
    put('spot_frozen_records', sd['records_present_when_frozen'], 'spot_detail.json')

    spot = args.census / 'spot_checks'
    v1 = latest_jsonl(spot / 'reviews.jsonl')
    v2 = latest_jsonl(spot / 'reviews_v2_anatomy.jsonl')
    blocked = [r for r in v1.values() if r['decision_shown']]
    put('spot_n', len(v1), 'reviews.jsonl')
    put('spot_on_structure', sum(r['answers']['placement'] == 'on_structure' for r in v1.values()), 'reviews.jsonl')
    put('spot_blocked', len(blocked), 'reviews.jsonl')
    put('spot_blocked_on_structure', sum(r['answers']['placement'] == 'on_structure' for r in blocked), 'reviews.jsonl')
    put('v2_site_present', sum(r['answers']['anatomy_present'] == 'present' for r in v2.values()), 'reviews_v2_anatomy.jsonl')
    put('v2_type_wrong', sum(r['answers']['category_correct'] == 'wrong' for r in v2.values()), 'reviews_v2_anatomy.jsonl')
    match01 = load(spot / 'match_01_findings.json')['summary']
    put('marks_total', len(match01), 'match_01_findings.json')
    put('marks_matched', sum(bool(m['inside_nodules']) for m in match01), 'match_01_findings.json')
    t3 = [json.loads(l) for l in (args.census / 'target_checks' / 'target_reviews.jsonl').read_text(encoding='utf-8')
          .splitlines() if l.strip()]
    put('rider_series_checked', len({r['dataset'] for r in t3}), 'target_reviews.jsonl')
    put('rider_other_lesion', sum(r['answers']['siemens_target'] == 'other_lesion' for r in t3), 'target_reviews.jsonl')

    ev = load(args.expa / 'results_eval.json')['conditions']
    reqs = load(args.expa / 'requests_eval.json')
    put('expa_eval_requests', ev['G0']['n'], 'results_eval.json')
    put('expa_eval_series', len({r['ct_series'] for r in reqs['requests']}), 'requests_eval.json')
    put('expa_eval_pool', reqs['eval_pool'], 'requests_eval.json')
    for c in ('G0', 'G1', 'G2', 'G3'):
        r = ev[c]
        put(f'{c}_wrong', r['wrong_release'], 'results_eval.json')
        put(f'{c}_wrong_pct', pct(r['wrong_release'], r['n']), 'results_eval.json')
        put(f'{c}_wrong_ci', '–'.join(f'{100 * x:.0f}' for x in r['wrong_release_ci95']), 'results_eval.json')
        put(f'{c}_done', r['completion'], 'results_eval.json')
        put(f'{c}_done_of', r['completion_of'], 'results_eval.json')
        put(f'{c}_done_pct', pct(r['completion'], r['completion_of']), 'results_eval.json')
        put(f'{c}_done_ci', '–'.join(f'{100 * x:.0f}' for x in r['completion_ci95']), 'results_eval.json')
        put(f'{c}_unneeded_defer', r['unnecessary_deferral'], 'results_eval.json')
        put(f'{c}_amb_defer', r['deferral_ambiguous'], 'results_eval.json')

    # Post hoc analyses after the review (reported as post hoc in the manuscript).
    ph = load(args.expa / 'posthoc_20260925.json')
    b = ph['eval']['g0_breakdown']
    put('g0_mismatched', b['mismatched_target'], 'posthoc_20260925.json')
    put('g0_ambiguous', b['ambiguous'], 'posthoc_20260925.json')
    put('eval_release_required', b['release_required'], 'posthoc_20260925.json')
    put('eval_distinct_texts', ph['eval']['distinct_texts'], 'posthoc_20260925.json')
    put('resolver_disagreements', len(ph['eval']['independent_resolver_disagreements'])
        + len(ph['dev']['independent_resolver_disagreements']), 'posthoc_20260925.json')
    m = ph['eval']['conditions']['G1_vocabulary_matched']
    put('g1m_done', m['completion'], 'posthoc_20260925.json')
    put('g1m_inappropriate', m['inappropriate'], 'posthoc_20260925.json')
    dsc = ph['descriptions']
    put('desc_distinct', dsc['distinct'], 'posthoc_20260925.json')
    put('desc_ambiguous', dsc['ambiguous'], 'posthoc_20260925.json')
    put('desc_ambiguous_pct', pct(dsc['ambiguous'], dsc['distinct']), 'posthoc_20260925.json')
    tp = load(args.census / 'targets_posthoc_20260925.json')
    cp = tp['cross_target_pairs']
    put('code_annotations', cp['annotations'], 'targets_posthoc_20260925.json')
    put('code_targets', cp['targets'], 'targets_posthoc_20260925.json')
    put('code_patients', cp['patients'], 'targets_posthoc_20260925.json')
    put('code_distinct_triples', cp['distinct_code_triples'], 'targets_posthoc_20260925.json')
    s3 = tp['sensitivity']['3.0']
    put('nodule_id_one_to_one', s3['one_to_one_with_nodule_id'], 'targets_posthoc_20260925.json')
    put('nodule_id_targets', s3['targets'], 'targets_posthoc_20260925.json')
    # The order the design was fixed in, from the freeze records themselves, and how
    # the requests changed from set to set. Both answer "pre-specified or adapted?",
    # which no sentence in the Methods can answer on its own.
    tl = load(args.expb / 'timeline.json')
    src_tl = 'expB/timeline.json'
    put('freeze_n', len(tl['freezes']), src_tl)
    for i, f in enumerate(tl['freezes'], 1):
        put(f'fz{i}_record', f['short'].replace('_', ' '), src_tl)
        put(f'fz{i}_experiment', f['experiment'], src_tl)
        put(f'fz{i}_utc', f['frozen_utc'][:16].replace('T', ' '), src_tl)
        put(f'fz{i}_stage', f['stage_short'], src_tl)
        put(f'fz{i}_files', f['files'] + f['data'] + f['gui'] + len(f['design']), src_tl)
        for s in ('1', '2', '3'):
            put(f'fz{i}_set{s}', f['requests_written'].get(s, 0), src_tl)
    # The set a freeze governs must have had no request written when it was taken.
    governed = {'FREEZE_before_requests': '1', 'FREEZE_v2_before_set2': '2',
                'FREEZE_v3_before_set3': '3'}
    for f in tl['freezes']:
        if f['short'] in governed:
            assert f['requests_written'][governed[f['short']]] == 0, f['short']
    for row in tl['sets']:
        p = row['profile']
        for key in ('marking', 'segment_name', 'lobe', 'position_word'):
            put(f"drift{row['set']}_{key}", p[key], src_tl)
        put(f"drift{row['set']}_n", p['n'], src_tl)

    # Experiment B (paper_results.json aggregates the frozen outputs; any-wrong counts are post hoc).
    pb = load(args.expb / 'paper_results.json')
    src_b = 'expB/paper_results.json'
    for s, per in pb['sets'].items():
        for reader, v in per.items():
            put(f'b{s}_{reader}_c', v['correct'], src_b)
            put(f'b{s}_{reader}_w', v['any_wrong'], src_b)
            put(f'b{s}_{reader}_e', v['episode_wrong'], src_b)
            put(f'b{s}_{reader}_cci', '–'.join(f'{100 * x:.0f}' for x in v['correct_ci']), src_b)
            put(f'b{s}_{reader}_wci', '–'.join(f'{100 * x:.0f}' for x in v['any_wrong_ci']), src_b)
    # The five-cell partition behind Table 1 (expB_contingency.py). The counts the
    # manuscript used before are derivable from these, and check_contingency.py
    # requires that they still agree with paper_results.json.
    cg = load(args.expb / 'contingency_v3.json')
    src_cg = 'expB/contingency_v3.json'
    for s, per in cg['sets'].items():
        for reader, cells in per.items():
            for cell in cg['cells']:
                put(f'b{s}_{reader}_{cell}', cells[cell], src_cg)
    put('b_defer_reference', cg['reference'], src_cg)
    # The ceiling: how often the author's own recorded conditions singled out the
    # intended nodule under the final gate, over all three sets.
    put('b_a3_intended_all',
        sum(per[cg['reference']]['auth_intended'] for per in cg['sets'].values()), src_cg)
    put('b_requests_all', sum(per[cg['reference']]['n'] for per in cg['sets'].values()), src_cg)
    # What double reading costs (expB_decision.py): a paired comparison of each
    # consensus against the reader it is built from.
    dec = load(args.expb / 'decision_v3.json')
    src_dec = 'expB/decision_v3.json'
    for pair, per in dec['pairs'].items():
        short = pair.replace('_vs_', '')
        for label, e in per.items():
            tag = 'pre' if label == 'prespecified' else 'post'
            put(f'dec_{short}_{tag}_removed', e['wrong_removed'], src_dec)
            put(f'dec_{short}_{tag}_lost', e['correct_lost'], src_dec)
            put(f'dec_{short}_{tag}_added', e['wrong_added'], src_dec)
            put(f'dec_{short}_{tag}_cost',
                '-' if e['cost'] is None else f"{e['cost']:.1f}", src_dec)
            put(f'dec_{short}_{tag}_ci',
                '-' if not e['cost_ci'] else '–'.join(f'{x:.1f}' for x in e['cost_ci']),
                src_dec)
            for s, v in e['per_set'].items():
                put(f'dec{s}_{short}_{tag}_removed', v['wrong_removed'], src_dec)
                put(f'dec{s}_{short}_{tag}_lost', v['correct_lost'], src_dec)
    put('dec_reps', dec['reps'], src_dec)

    # The lobe adjudication, one row per item (expB_adjudication_table.py). The
    # reviewer asked for slice thickness and the distance to the lobe boundary
    # beside each answer, so the table interpolates them rather than quoting them.
    adj = load(args.expb / 'lobe_adjudication_items.json')
    src_adj = 'expB/lobe_adjudication_items.json'
    for row in adj['items']:
        i = row['item']
        put(f'adj_{i}_role', row['role'], src_adj)
        put(f'adj_{i}_set', row['set'], src_adj)
        put(f'adj_{i}_named', row['lobe_named_in_request'] or '—', src_adj)
        put(f'adj_{i}_map', row['lobe_of_the_map'], src_adj)
        put(f'adj_{i}_q1', row['q1_expert_lobe'], src_adj)
        put(f'adj_{i}_q2', row['q2'], src_adj)
        put(f'adj_{i}_dist', f"{row['distance_to_nearest_other_lobe_mm']:.1f}", src_adj)
        put(f'adj_{i}_slice', f"{row['slice_thickness_mm']:.2f}", src_adj)
    put('adj_near_mm', f"{adj['near_threshold_mm']:.0f}", src_adj)
    put('adj_n', adj['n_items'], src_adj)
    put('adj_applicable', adj['n_applicable'], src_adj)
    put('adj_applicable_correct', adj['n_applicable_correct'], src_adj)
    put('adj_not_applicable', adj['n_not_applicable'], src_adj)
    put('adj_not_applicable_incorrect', adj['n_not_applicable_answered_incorrect'], src_adj)
    put('adj_not_applicable_note_not_near', adj['n_not_applicable_note_says_not_near'], src_adj)
    put('adj_q2_en', adj['questions']['q2']['en'], src_adj)
    put('adj_q1_en', adj['questions']['q1']['en'], src_adj)
    # When the author asked the AI assistant about fissures, against when each answer
    # was saved. A reviewer asked for the exact prompts; the order is what says how
    # much of the adjudication they could have reached.
    put('adj_answers', adj['n_answers'], src_adj)
    put('adj_guidance_n', len(adj['guidance_asked_utc']), src_adj)
    put('adj_guidance_first', adj['guidance_asked_utc'][0][11:16], src_adj)
    put('adj_guidance_last', adj['guidance_asked_utc'][-1][11:16], src_adj)
    put('adj_after_guidance', adj['n_answers_after_the_assistant_was_asked'], src_adj)
    put('adj_before_guidance', adj['n_answers_before_the_assistant_was_asked'], src_adj)
    put('adj_undecidable_n', len(adj['q1_undecidable']), src_adj)
    put('adj_undecidable_after', len(adj['q1_undecidable_after_the_assistant_was_asked']), src_adj)

    # Everything a reader needs to repeat a model call (Table 9). The counts are
    # recomputed from the stored responses, not quoted from the text.
    src_rep = 'expA/g2_*.jsonl, expB/model_responses*.jsonl'
    calls = {}
    for name, path in (('a_dev', args.expa / 'g2_dev.jsonl'),
                       ('a_dev_failed', args.expa / 'g2_dev_attempt1_http400.jsonl'),
                       ('a_eval', args.expa / 'g2_eval.jsonl'),
                       ('b_v1', args.expb / 'model_responses.jsonl'),
                       ('b_v2_dev', args.expb / 'model_responses_v2.jsonl'),
                       ('b_v2', args.expb / 'model_responses_v2b.jsonl')):
        calls[name] = [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()
                       if l.strip()]
    answered = [r for rs in calls.values() for r in rs if r.get('status') == 200]
    names = {(r.get('response') or {}).get('model') for r in answered}
    assert names == {expB_readers_v2.MODEL}, f'model strings in the responses: {names}'
    days = sorted({r['utc'][:10] for rs in calls.values() for r in rs if r.get('utc')})
    put('rep_model', expB_readers_v2.MODEL, 'core/expB_readers_v2.py')
    put('rep_endpoint', expA_jev.ENDPOINT, 'core/expA_jev.py')
    put('rep_threshold', f'{expB_readers_v2.THRESHOLD:g}', 'core/expB_readers_v2.py')
    # Section 3.5 explains why slice-local positions alone did not save the intended
    # nodule: the band, not the measurement, is what kept it. Both the band and the
    # cut it implies come from the gate's own constant, so neither can drift.
    put('v3_band', f'{expB_readers_v3.BAND:g}', 'core/expB_readers_v3.py')
    put('v3_lateral_cut', f'{0.5 - expB_readers_v3.BAND:g}', 'core/expB_readers_v3.py')
    put('rep_calls_a_eval', len(calls['a_eval']), src_rep)
    put('rep_calls_a_dev', len(calls['a_dev']), src_rep)
    put('rep_calls_a_resent', len(calls['a_dev_failed']), src_rep)
    put('rep_calls_b', len(calls['b_v1']) + len(calls['b_v2_dev']) + len(calls['b_v2']), src_rep)
    put('rep_calls_answered', len(answered), src_rep)
    put('rep_first_day', days[0], src_rep)
    put('rep_last_day', days[-1], src_rep)
    # The segmentation version is read from the environment that ran it, not typed:
    # record_environment.py does that reading where the segmentation ran, and ships
    # the result, so the archive can reproduce this table too.
    env = load(args.expb / 'environment.json')
    src_env = 'expB/environment.json'
    put('rep_ts_version', env['ts_version'], src_env)
    put('rep_ts_torch', env['torch'], src_env)

    cases = sorted({r['case'] for r in load(args.expb / 'per_request_v3.json')['rows']})
    put('b_case_first', cases[0], 'expB/per_request_v3.json')
    put('b_case_last', cases[-1], 'expB/per_request_v3.json')

    rk = pb['r1_rank_misreading']
    put('b_r1_correct', sum(v['correct'] for v in rk.values()), src_b)
    put('b_r1_correct_rank', sum(v['correct_by_rank'] for v in rk.values()), src_b)
    put('b_r1_wrong', sum(v['wrong'] for v in rk.values()), src_b)
    put('b_r1_wrong_rank', sum(v['wrong_by_rank'] for v in rk.values()), src_b)
    lang = pb['language']
    put('b_requests', sum(v['n'] for v in lang.values()), src_b)
    put('b_per_set', lang['1']['n'], src_b)
    put('b_set1_marking', lang['1']['marking'], src_b)
    put('b_set3_segment', lang['3']['segment'], src_b)
    put('b_set12_segment', lang['1']['segment'] + lang['2']['segment'], src_b)
    put('b_longest_diameter', sum(v['longest_diameter'] for v in lang.values()), src_b)
    al = pb['author_labels']
    put('b_ordinal_none', sum(v['ordinal_none'] for v in al.values()), src_b)
    put('b_set2_unverifiable', al['2']['unverifiable'], src_b)
    put('b_set3_unverifiable', al['3']['unverifiable'], src_b)
    put('b_label_corrections', pb['author_label_corrections'], src_b)
    mc = pb['model_calls']
    put('b_model_calls', mc['n'], src_b)
    put('b_model_ok', mc['ok'], src_b)
    put('b_latency_median', mc['median_latency_s'], src_b)
    put('b_latency_max', mc['max_latency_s'], src_b)
    put('b15_ml_whole', pb['b15']['ml_whole_lung'], src_b)
    put('b15_ml_slice', pb['b15']['ml_slice_local'], src_b)
    lb = pb['lobes']
    for k in ('named_lobe_requests', 'named_lobe_disagree', 'disagree_n', 'disagree_expert_agrees_map',
              'disagree_expert_agrees_text', 'disagree_undecidable', 'controls_n', 'controls_undecidable',
              'controls_agree', 'q2_applicable', 'q2_applicable_correct'):
        put(f'lobe_{k}', lb[k], src_b)
    put('lobe_q2_threshold', f"{lb['q2_near_threshold_mm']:.0f}", src_b)
    put('lobe_fissure_min', lb['fissure_mm_disagree'][0], src_b)
    put('lobe_fissure_max', lb['fissure_mm_disagree'][-1], src_b)
    put('lobe_items', lb['disagree_n'] + lb['controls_n'], src_b)
    # Post hoc (Codex review 2026-09-26): the v1 rules with only the rank removed, and first label versions.
    ab = load(args.expb / 'rank_ablation.json')
    src_ab = 'expB/rank_ablation.json'
    put('b_r1_correct_kept_norank', sum(v['correct_kept'] for v in ab.values()), src_ab)
    put('b_r1_wrong_kept_norank', sum(v['wrong_kept'] for v in ab.values()), src_ab)
    put('b_r1_wrong_rank_dependent', sum(v['wrong_rank_dependent'] for v in ab.values()), src_ab)
    put('b_d1_wrong_rank_dependent', sum(v['d1_wrong_rank_dependent'] for v in ab.values()), src_ab)
    # Per set as well as pooled: Reviewer 3 asked for the ablation set by set, and the
    # three sets do not behave alike.
    for s, v in ab.items():
        for field in ('r1_correct', 'r1_wrong', 'correct_kept', 'wrong_kept',
                      'wrong_rank_dependent'):
            put(f'b{s}_abl_{field}', v[field], src_ab)
    for s in ('1', '2', '3'):
        for name in ('a2', 'a3'):
            for ver in ('first', 'last'):
                c, w = ab[s][f'{name}_{ver}']
                put(f'b{s}_{name}_{ver}_c', c, src_ab)
                put(f'b{s}_{name}_{ver}_w', w, src_ab)
        put(f'b{s}_labels_changed', ab[s]['labels_changed'], src_ab)
    for k in ('d3t_wrong_discordant', 'd3t_wrong_unassignable', 'd3t_wrong_other'):
        put(f'lobe_{k}', lb[k], src_b)
    items = lb['items']
    put('lobe_q2_correct_raw', sum(x['q2'] == 'correct' for x in items), src_b)
    put('lobe_q2_incorrect_raw', sum(x['q2'] == 'incorrect' for x in items), src_b)
    ctl = sorted(x['fissure_mm'] for x in items if x['role'] == 'control')
    put('lobe_control_mm', ', '.join(f'{d:.1f}' for d in ctl[:-1]) + f' and {ctl[-1]:.1f}', src_b)
    series_b = load(args.expb / 'series.json')
    put('b_series', len(series_b['chosen']), 'expB/series.json')
    put('b_eligible', series_b['eligible'], 'expB/series.json')
    regions3 = load(args.expb / 'regions_v3.json')
    put('b_targets', sum(len(v) for v in regions3.values()), 'expB/regions_v3.json')

    # English style: thousands separators for counts of 1,000 or more.
    n = {k: (f'{v:,}' if isinstance(v, int) and v >= 1000 else v) for k, v in n.items()}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'numbers.json').write_text(json.dumps(dict(values=n, sources=src), ensure_ascii=False, indent=1),
                                           encoding='utf-8')
    print(len(n), 'numbers')


if __name__ == '__main__':
    main()
