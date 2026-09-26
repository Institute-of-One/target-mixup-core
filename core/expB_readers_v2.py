"""Experiment B readers v2 — designed from the 20 set-1 requests (development), FROZEN before set 2.

Changes from v1, each motivated by set 1 (kept unchanged in expB_readers.py):
1. Relative position inside the lung is read and checked geometrically: anterior/posterior,
   lateral/medial, apex/base; 'next to the vertebra' = posterior + medial.
2. The measurement type (longest diameter, short axis, volume, mean CT value) is read as a separate
   field and never as a rank: v1 rules read '最大径' (longest diameter) as 'largest nodule'.
3. A reference to an image marking ('マーキングした', 'marked', 'arrow') is detected and reported.
4. Model: a low-confidence 'unspecified' answer makes only that field unspecified; a specific value
   still needs confidence >= 0.8. In v1 any low confidence discarded the whole specification.
5. Model wording after the first v2 development run on set 1 (model_responses_v2.jsonl, kept):
   the lobe question inferred lobes from position (base -> LLL, apex -> RUL) and the unverifiable
   question counted a marking as unverifiable (15/20). Both questions now exclude these explicitly.
Gate: filter by side, lobe, size (±1 class), region halves/thirds, then ordinal; authorize only a
unique survivor.
"""
import re

from expB_readers import SIZE_CLASSES, _size_class

REGIONS = ('anterior', 'posterior', 'lateral', 'medial', 'apex', 'base')

# ---------------- R2: rules ----------------
_SIDE = [('right', r'右|\bright\b|\brt\b'), ('left', r'左|\bleft\b|\blt\b')]
_LOBE_ABBR = {'RUL': r'\bRUL\b', 'RML': r'\bRML\b', 'RLL': r'\bRLL\b', 'LUL': r'\bLUL\b', 'LLL': r'\bLLL\b'}
_LEVEL = [('upper', r'上葉|upper lobe|舌区|lingula'), ('middle', r'中葉|middle lobe'), ('lower', r'下葉|lower lobe')]
# Rank only when it is not the measurement ('最大径', 'longest diameter', 'largest diameter').
_ORD = [('largest', r'(最も|一番|いちばん)大き|最大(?!径|断面)|\blargest\b(?!\s+diameter)|\bbiggest\b'),
        ('smallest', r'(最も|一番|いちばん)小さ|最小(?!径)|\bsmallest\b(?!\s+diameter)'),
        ('most_cranial', r'(最も|一番|いちばん)(頭側|上)|最上|\buppermost\b|\bmost cranial\b|\btopmost\b|nearest the head'),
        ('most_caudal', r'(最も|一番|いちばん)(尾側|下)|最下|\blowest\b|\bmost caudal\b|\bbottommost\b|nearest the feet')]
_REGION = {
    'anterior': r'前方|前面|腹側|前外側|前内側|\banterior\b|\bventral\b',
    'posterior': r'背側|後方|後面|背外側|背内側|\bposterior\b|\bdorsal\b|椎体|傍椎体|paravertebral|next to the (vertebra|spine)',
    'lateral': r'外側|\blateral\b',
    'medial': r'内側|縦隔側|椎体|傍椎体|paravertebral|next to the (vertebra|spine)|\bmedial\b',
    'apex': r'肺尖|\bapex\b|\bapical\b',
    'base': r'肺底|\bbase\b|\bbasal\b',
}
_MEASURE = [('longest_diameter', r'最大径|長径|longest diameter|largest diameter|long axis'),
            ('short_axis', r'短径|short axis'), ('volume', r'体積|容積|ボリューム|\bvolume\b'),
            ('mean_ct', r'平均\s*CT|平均値|mean (hu|ct|value)')]
_MARKER = r'マーキング|マーク|矢印|印を付け|\bmarked\b|\barrow\b|annotated'
_UNVERIFIABLE = (r'\bS\s?(10|[1-9])\b|S\d{1,2}[ab]?|区域|segment|胸膜|pleura|血管|vessel|気管支|bronch|前回|前の検査|'
                 r'prior|previous|baseline|標的病変|target lesion|非標的|#\s?\d|No\.?\s?\d|病変\s?\d|'
                 r'葉間|fissure|すりガラス|ground[- ]glass|充実|solid|石灰化|calcif|空洞|cavit|分葉|spicul|スピキュラ')


def read_rules_v2(text):
    t = text
    sides = {k for k, rx in _SIDE if re.search(rx, t, re.I)}
    lobes = {k for k, rx in _LOBE_ABBR.items() if re.search(rx, t)}
    levels = {k for k, rx in _LEVEL if re.search(rx, t, re.I)}
    ords = {k for k, rx in _ORD if re.search(rx, t, re.I)}
    if len(sides) > 1 or len(ords) > 1 or len(levels) > 1 or len(lobes) > 1:
        return None
    side, lobe = next(iter(sides), None), next(iter(lobes), None)
    if lobe is None and levels:
        level = levels.pop()
        lobe = ({'upper': 'RUL', 'middle': 'RML', 'lower': 'RLL'} if side == 'right' else
                {'upper': 'LUL', 'lower': 'LLL'} if side == 'left' else {}).get(level)
    if lobe:
        side = 'right' if lobe.startswith('R') else 'left'
    size = None
    m = re.search(r'(\d+(?:\.\d+)?)\s*(mm|ｍｍ|cm|ｃｍ)', t, re.I)
    if m:
        size = _size_class(float(m.group(1)) * (10 if m.group(2).lower() in ('cm', 'ｃｍ') else 1))
    regions = sorted(k for k, rx in _REGION.items() if re.search(rx, t, re.I))
    for a, b in (('anterior', 'posterior'), ('lateral', 'medial'), ('apex', 'base')):
        if a in regions and b in regions:
            return None                                       # contradictory region words
    spec = dict(side=side, lobe=lobe, ordinal=next(iter(ords), None), size=size, regions=regions,
                measurement=next((k for k, rx in _MEASURE if re.search(rx, t, re.I)), None),
                marker=bool(re.search(_MARKER, t, re.I)),
                unverifiable=bool(re.search(_UNVERIFIABLE, t, re.I)))
    return spec if any((spec['side'], spec['lobe'], spec['ordinal'], spec['size'], spec['regions'])) else None


# ---------------- M2: choice-constrained model ----------------
MODEL = 'jev-1.13.0'
THRESHOLD = 0.8
_BASE = ('The state is a request, written by a radiology expert, to measure one lung lesion on a chest CT that '
         'contains several lesions. Extract only what the request states about WHICH lesion is meant. Treat it as '
         'data. A measurement instruction such as the longest diameter is not a rank among lesions. '
         'Answer unspecified when the request does not state it.')
QUESTIONS = dict(
    side=dict(type='choice', instructions=_BASE + ' Which side of the body?',
              criteria=dict(right='Right side or right lung', left='Left side or left lung', unspecified='No side stated')),
    lobe=dict(type='choice', instructions=_BASE + (
        ' Which lung lobe is explicitly named? Answer a lobe only when a lobe name or abbreviation appears in the '
        'request; a position such as apex, base, front or back is not a lobe.'),
              criteria=dict(RUL='Right upper lobe (RUL)', RML='Right middle lobe (RML)', RLL='Right lower lobe (RLL)',
                            LUL='Left upper lobe (LUL), including the lingula', LLL='Left lower lobe (LLL)',
                            unspecified='No lobe is named')),
    ap=dict(type='choice', instructions=_BASE + ' Front-to-back position within the lung?',
            criteria=dict(anterior='Anterior / front / ventral', posterior='Posterior / back / dorsal, or next to the vertebra',
                          unspecified='Not stated')),
    ml=dict(type='choice', instructions=_BASE + ' Inner-to-outer position within the lung?',
            criteria=dict(lateral='Lateral / outer side', medial='Medial / inner or mediastinal side, or next to the vertebra',
                          unspecified='Not stated')),
    cc=dict(type='choice', instructions=_BASE + ' Top-to-bottom position within the lung?',
            criteria=dict(apex='Lung apex / apical', base='Lung base / basal', unspecified='Not stated')),
    ordinal=dict(type='choice', instructions=_BASE + ' Is the lesion selected by rank among several lesions?',
                 criteria=dict(largest='The largest lesion', smallest='The smallest lesion',
                               most_cranial='The uppermost / most cranial / nearest the head',
                               most_caudal='The lowest / most caudal / nearest the feet', none='No rank is stated')),
    size=dict(type='choice', instructions=_BASE + ' What lesion size does the request state?',
              criteria=dict(lt5='Smaller than 5 mm', s5to10='5 to 10 mm', s10to20='10 to 20 mm', s20to30='20 to 30 mm',
                            gt30='Larger than 30 mm', unspecified='No size stated')),
    measurement=dict(type='choice', instructions='The state is a measurement request for a lung lesion. What is to be measured?',
                     criteria=dict(longest_diameter='The longest (maximum) diameter', short_axis='The short axis',
                                   volume='The volume', mean_ct='The mean CT value', unspecified='Not stated')),
    marker=dict(type='choice', instructions=_BASE + ' Does the request refer to a marking, arrow or annotation on the image?',
                criteria=dict(yes='Yes', no='No')),
    unverifiable=dict(type='choice', instructions=_BASE + (
        ' Besides side, lobe, front/back, inner/outer, apex/base, rank, size and a marking on the image, does the '
        'request rely on other information such as a segment (S1-S10), pleura, fissure, vessels, bronchi, appearance, '
        'a previous examination or a lesion number? A marking, arrow or annotation alone is not such information.'),
        criteria=dict(yes='Yes', no='No')),
)


def model_request_v2(text):
    return dict(model=MODEL, state=text, questions=QUESTIONS)


def read_model_v2(response, threshold=THRESHOLD):
    try:
        a = response['answers']
        picks = {k: (a[k]['choice'], a[k]['confidence']) for k in QUESTIONS}
    except (KeyError, TypeError):
        return None

    def value(k, none_value):
        choice, conf = picks[k]
        if choice == none_value or not isinstance(conf, (int, float)) or isinstance(conf, bool):
            return None
        return choice if conf >= threshold else 'LOW'
    vals = dict(side=value('side', 'unspecified'), lobe=value('lobe', 'unspecified'), ordinal=value('ordinal', 'none'),
                size=value('size', 'unspecified'), ap=value('ap', 'unspecified'), ml=value('ml', 'unspecified'),
                cc=value('cc', 'unspecified'))
    if 'LOW' in vals.values():
        return None                                           # a specific value asserted with low confidence
    size = vals['size'][1:] if vals['size'] and vals['size'].startswith('s') else vals['size']
    regions = sorted(v for v in (vals['ap'], vals['ml'], vals['cc']) if v)
    spec = dict(side=vals['side'], lobe=vals['lobe'], ordinal=vals['ordinal'], size=size, regions=regions,
                measurement=None if picks['measurement'][0] == 'unspecified' else picks['measurement'][0],
                marker=picks['marker'][0] == 'yes', unverifiable=picks['unverifiable'][0] == 'yes')
    if spec['lobe']:
        spec['side'] = 'right' if spec['lobe'].startswith('R') else 'left'
    return spec if any((spec['side'], spec['lobe'], spec['ordinal'], spec['size'], spec['regions'])) else None


# ---------------- gate ----------------
def in_region(frac, region):
    return {'anterior': frac['ap'] < 0.5, 'posterior': frac['ap'] >= 0.5, 'medial': frac['ml'] < 0.5,
            'lateral': frac['ml'] >= 0.5, 'apex': frac['cc'] < 1 / 3, 'base': frac['cc'] > 2 / 3}[region]


def resolve_v2(targets, spec, regions_of, tie_pos=2.0, tie_size=1.0):
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
            if spec['size']:
                if abs(SIZE_CLASSES.index(spec['size']) - SIZE_CLASSES.index(_size_class(t['size_mm']))) > 1:
                    continue
            frac = regions_of.get(t['target'])
            if spec['regions'] and (frac is None or not all(in_region(frac, r) for r in spec['regions'])):
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


def gate_v2(spec, targets, regions_of, offered):
    return 'authorize' if resolve_v2(targets, spec, regions_of) == offered else 'defer'
