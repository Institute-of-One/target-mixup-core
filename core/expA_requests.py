"""Experiment A, step 2: frozen request templates, request generation and ground truth.

A description is (side, ordinal): side in {right, left, None}; ordinal in {largest, smallest,
most_cranial, most_caudal}. Truth is resolved on the target table; a description is ambiguous when
no single target satisfies it, when ties fall within TIE_POS_MM / TIE_SIZE_MM, or when a target of
indeterminate side could change the answer (amendment v1.1). Correct action: release only for a
unique description offered the intended target's SEG; otherwise defer.

    python expA_requests.py --expa <expA dir>
"""
import argparse
import hashlib
import json
import random
from pathlib import Path

SEED = 20260925
EVAL_REQUESTS = 200
TIE_POS_MM, TIE_SIZE_MM = 2.0, 1.0
ORDINALS = ('largest', 'smallest', 'most_cranial', 'most_caudal')

# FROZEN 2026-09-25 (author approved the draft). Families D* are used to write the rule parser;
# families E* are used only for evaluation.
TEMPLATES = {
    'D1': dict(lang='ja', text='{side}肺で{ordinal}結節の体積と平均CT値を測ってください。',
               side={'right': '右', 'left': '左'},
               ordinal=dict(largest='最も大きい', smallest='最も小さい', most_cranial='最も頭側の', most_caudal='最も尾側の')),
    'D2': dict(lang='ja', text='{side}の{ordinal}ノジュールを計測して。', side={'right': '右', 'left': '左'},
               ordinal=dict(largest='一番大きい', smallest='一番小さい', most_cranial='一番上の', most_caudal='一番下の')),
    'D3': dict(lang='en', text='Measure the volume and mean HU of the {ordinal} nodule in the {side} lung.',
               side={'right': 'right', 'left': 'left'},
               ordinal=dict(largest='largest', smallest='smallest', most_cranial='most cranial', most_caudal='most caudal')),
    'E1': dict(lang='ja', text='{ordinal}{side}側病変のボリュームをお願いします。', side={'right': '右', 'left': '左'},
               ordinal=dict(largest='最も大きい', smallest='最も小さい', most_cranial='最も頭側の', most_caudal='最も尾側の')),
    'E2': dict(lang='ja', text='{side}の{ordinal}結節、測っといてください。', side={'right': '右', 'left': '左'},
               ordinal=dict(largest='一番大きい', smallest='一番小さい', most_cranial='一番上の', most_caudal='一番下の')),
    'E3': dict(lang='en', text='Please quantify the {ordinal} {side}-sided nodule.', side={'right': 'right', 'left': 'left'},
               ordinal=dict(largest='largest', smallest='smallest', most_cranial='most cranial', most_caudal='most caudal')),
    'E4': dict(lang='en', text='{side} lung, {ordinal} lesion — volume please.', side={'right': 'Right', 'left': 'Left'},
               ordinal=dict(largest='largest', smallest='smallest', most_cranial='uppermost', most_caudal='lowest')),
    'E5': dict(lang='ja', text='{ordinal}結節を測定してください。', side=None,
               ordinal=dict(largest='最も大きい', smallest='最も小さい', most_cranial='最も頭側の', most_caudal='最も尾側の')),
}
DEV_FAMILIES = ('D1', 'D2', 'D3')
EVAL_FAMILIES = ('E1', 'E2', 'E3', 'E4', 'E5')


def templates_sha256():
    return hashlib.sha256(json.dumps(TEMPLATES, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def resolve(targets, side, ordinal):
    """Target number satisfying (side, ordinal), or None when not unique (ambiguous)."""
    answers = set()
    # An indeterminate-side target may count on either side; if that changes the answer, it is ambiguous.
    for assumed in ('left', 'right'):
        pool = [t for t in targets if side is None or (t['side'] if t['side'] != 'midline' else assumed) == side]
        answers.add(_pick(pool, ordinal))
    return answers.pop() if len(answers) == 1 else None


def _pick(pool, ordinal):
    if not pool:
        return None
    if ordinal in ('largest', 'smallest'):
        key, tie = (lambda t: t['size_mm']), TIE_SIZE_MM
    else:
        key, tie = (lambda t: t['centroid_lps_mm'][2]), TIE_POS_MM
    ranked = sorted(pool, key=key, reverse=ordinal in ('largest', 'most_cranial'))
    if len(ranked) > 1 and abs(key(ranked[0]) - key(ranked[1])) <= tie:
        return None
    return ranked[0]['target']


def render(family, side, ordinal):
    t = TEMPLATES[family]
    if t['side'] is None:
        return t['text'].format(ordinal=t['ordinal'][ordinal])
    return t['text'].format(side=t['side'][side], ordinal=t['ordinal'][ordinal])


def generate(series, families, rng):
    out = []
    for s in series:
        for fam in families:
            sides = [None] if TEMPLATES[fam]['side'] is None else ['right', 'left']
            for side in sides:
                for ordinal in ORDINALS:
                    intended = resolve(s['targets'], side, ordinal)
                    offer_intended = intended is not None and rng.random() < 0.5
                    others = [t['target'] for t in s['targets'] if t['target'] != intended]
                    offered = intended if offer_intended else rng.choice(others)
                    out.append(dict(ct_series=s['ct_series'], patient=s['patient'], family=fam,
                                    lang=TEMPLATES[fam]['lang'], text=render(fam, side, ordinal),
                                    truth=dict(side=side, ordinal=ordinal, intended_target=intended,
                                               unique=intended is not None),
                                    offered_target=offered,
                                    correct_action='release' if intended is not None and offered == intended else 'defer'))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expa', required=True, type=Path)
    args = ap.parse_args(argv)
    table = json.loads((args.expa / 'targets.json').read_text())
    rng = random.Random(SEED)
    dev = generate([s for s in table['series'] if s['split'] == 'development'], DEV_FAMILIES, rng)
    pool = generate([s for s in table['series'] if s['split'] == 'evaluation'], EVAL_FAMILIES, rng)
    ev = sorted(random.Random(SEED + 1).sample(pool, min(EVAL_REQUESTS, len(pool))),
                key=lambda r: (r['patient'], r['family'], r['text']))
    for i, r in enumerate(dev):
        r['id'] = f'dev{i:04d}'
    for i, r in enumerate(ev):
        r['id'] = f'eval{i:04d}'
    meta = dict(seed=SEED, templates_sha256=templates_sha256(), eval_pool=len(pool), eval_sampled=len(ev))
    (args.expa / 'requests_dev.json').write_text(json.dumps(dict(meta, requests=dev), ensure_ascii=False, indent=1),
                                                 encoding='utf-8')
    # Evaluation requests are written with their truth; they must not be read while writing parsers.
    (args.expa / 'requests_eval.json').write_text(json.dumps(dict(meta, requests=ev), ensure_ascii=False, indent=1),
                                                  encoding='utf-8')
    def summary(rs):
        return dict(n=len(rs), unique=sum(r['truth']['unique'] for r in rs),
                    correct_release=sum(r['correct_action'] == 'release' for r in rs))
    print('dev', summary(dev), 'eval', summary(ev), 'pool', len(pool), 'templates', meta['templates_sha256'][:12])


if __name__ == '__main__':
    main()
