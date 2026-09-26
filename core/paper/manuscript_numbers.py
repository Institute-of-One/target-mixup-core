"""Collect every number the manuscript quotes from the frozen result files.

Nothing in the manuscript is typed by hand: the build substitutes {{key}} from numbers.json.
Each value records its source file so a reader can trace it.

    python manuscript_numbers.py --census <census dir> --expa <expA dir> --expb <expB dir> --out <build dir>
"""
import argparse
import json
from pathlib import Path


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
    put('lidc_qiicr_patients_sampled', strata['LIDC-IDRI | QIICR']['patients']['match'], 'summary.json')
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
