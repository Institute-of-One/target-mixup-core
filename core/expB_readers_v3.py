"""Experiment B v3 gates (frozen before set 3). Readers are unchanged: the v2 rules (read_rules_v2) and
the v2b model request (read_model_v2); positions come from regions_v3.json (slice-local front/back and
inner/outer), and a position word excludes a candidate only when it is clearly on the other side
(BAND). resolve_v3 repeats the frozen resolve_v2 with that one change (expB_readers_v2 stays frozen).

Dual-reader gates, the analogue of double reading:
  target consensus: authorize only when the rule reader and the model reader each resolve the request to
                    the same single target, and that target is the one offered;
  reason consensus: additionally, both readers must state the same identifying conditions (side, lobe,
                    rank, size class, regions). A shared target reached for different reasons is deferred.
"""
from expB_readers import SIZE_CLASSES, _size_class

IDENTIFYING = ('side', 'lobe', 'ordinal', 'size', 'regions')
BAND = 0.15  # a position word excludes a candidate only when it lies clearly on the other side


def excluded_by_region(frac, region, band=BAND):
    """True only when the candidate is clearly outside the named region (set 2, B15: a nodule at
    ml 0.39-0.44 was called lateral by the expert; a borderline value must not exclude it)."""
    return {'anterior': frac['ap'] >= 0.5 + band, 'posterior': frac['ap'] < 0.5 - band,
            'medial': frac['ml'] >= 0.5 + band, 'lateral': frac['ml'] < 0.5 - band,
            'apex': frac['cc'] >= 1 / 3 + band, 'base': frac['cc'] <= 2 / 3 - band}[region]


def resolve_v3(targets, spec, regions_of, tie_pos=2.0, tie_size=1.0):
    """As resolve_v2, but region words exclude only clearly-outside candidates (excluded_by_region)."""
    if spec is None:
        return None
    answers = set()
    for assumed in ('left', 'right'):
        pool = []
        for t in targets:
            side = t['side'] if t['side'] != 'midline' else assumed
            if spec['side'] and side != spec['side']:
                continue
            if spec['lobe'] and t.get('lobe') not in (spec['lobe'], 'outside'):
                continue
            if spec['size'] and abs(SIZE_CLASSES.index(spec['size']) - SIZE_CLASSES.index(_size_class(t['size_mm']))) > 1:
                continue
            frac = regions_of.get(t['target'])
            if spec['regions'] and (frac is None or any(excluded_by_region(frac, r) for r in spec['regions'])):
                continue
            pool.append(t)
        if spec['ordinal'] and pool:
            key, tie = ((lambda t: t['size_mm']), tie_size) if spec['ordinal'] in ('largest', 'smallest') else \
                       ((lambda t: t['centroid_lps_mm'][2]), tie_pos)
            pool = sorted(pool, key=key, reverse=spec['ordinal'] in ('largest', 'most_cranial'))
            if len(pool) > 1 and abs(key(pool[0]) - key(pool[1])) <= tie:
                answers.add(None)
                continue
            pool = pool[:1]
        answers.add(pool[0]['target'] if len(pool) == 1 else None)
    return answers.pop() if len(answers) == 1 else None


def read_model_v3(response, threshold=0.8):
    """The v2b model answers read as a second reader: a specific value below the confidence threshold
    leaves that field unspecified instead of discarding the whole specification (v2). Safe only inside
    the dual gates, where the rule reader must independently reach the same target."""
    from expB_readers_v2 import QUESTIONS
    try:
        a = response['answers']
        picks = {k: (a[k]['choice'], a[k]['confidence']) for k in QUESTIONS}
    except (KeyError, TypeError):
        return None

    def value(k, none_value):
        choice, conf = picks[k]
        ok = isinstance(conf, (int, float)) and not isinstance(conf, bool) and conf >= threshold
        return None if choice == none_value or not ok else choice
    v = dict(side=value('side', 'unspecified'), lobe=value('lobe', 'unspecified'), ordinal=value('ordinal', 'none'),
             size=value('size', 'unspecified'), ap=value('ap', 'unspecified'), ml=value('ml', 'unspecified'),
             cc=value('cc', 'unspecified'))
    if v['lobe']:
        v['side'] = 'right' if v['lobe'].startswith('R') else 'left'
    spec = dict(side=v['side'], lobe=v['lobe'], ordinal=v['ordinal'],
                size=v['size'][1:] if v['size'] and v['size'].startswith('s') else v['size'],
                regions=sorted(x for x in (v['ap'], v['ml'], v['cc']) if x),
                measurement=None if picks['measurement'][0] == 'unspecified' else picks['measurement'][0],
                marker=picks['marker'][0] == 'yes', unverifiable=picks['unverifiable'][0] == 'yes')
    return spec if any((spec['side'], spec['lobe'], spec['ordinal'], spec['size'], spec['regions'])) else None


def same_reason(a, b):
    if a is None or b is None:
        return False
    return all((sorted(a[k]) if k == 'regions' else a[k]) == (sorted(b[k]) if k == 'regions' else b[k])
               for k in IDENTIFYING)


def resolve_dual(targets, spec_rule, spec_model, regions_of, reason=False):
    t_rule, t_model = resolve_v3(targets, spec_rule, regions_of), resolve_v3(targets, spec_model, regions_of)
    if t_rule is None or t_rule != t_model:
        return None
    if reason and not same_reason(spec_rule, spec_model):
        return None
    return t_rule


def gate_dual(targets, spec_rule, spec_model, regions_of, offered, reason=False):
    return 'authorize' if resolve_dual(targets, spec_rule, spec_model, regions_of, reason) == offered else 'defer'
