"""Manuscript figures from frozen result files (no hand-entered values).

Figure 1: census by producer — share of SEG series whose FoR matches the referenced CT, differs
          although every reference resolves, or that carry no source reference.
Figure 2: Experiment A — outcome of every challenge episode by condition.
Figure 3: Experiment B — per request set and reader, resolution to the intended or another nodule.

    python figures.py --census <census dir> --expa <expA dir> --expb <expB dir> --out <build dir>
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

# Reference palette, light mode, fixed order (validated: CVD ΔE 9.2, normal-vision 27.6; slot 3
# below 3:1 contrast, so every segment carries a direct label and a hatch for grayscale print).
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
INK, INK2, GRID, SURFACE = '#0b0b0b', '#52514e', '#e4e3df', '#ffffff'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8, 'axes.edgecolor': INK2, 'axes.labelcolor': INK,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False})

STRATA = [  # (key in summary.json, label)
    ('LIDC-IDRI | QIICR', 'LIDC · QIICR 2019'),
    ('LIDC-IDRI | QIN challenge alg01', 'LIDC · QIN alg01'),
    ('LIDC-IDRI | QIN challenge alg02', 'LIDC · QIN alg02'),
    ('LIDC-IDRI | QIN challenge alg03', 'LIDC · QIN alg03'),
    ('RIDER Lung CT | QIICR', 'RIDER · QIICR'),
    ('RIDER Lung CT | QIN challenge alg01', 'RIDER · QIN alg01'),
    ('RIDER Lung CT | QIN challenge alg02', 'RIDER · QIN alg02'),
    ('RIDER Lung CT | QIN challenge alg03', 'RIDER · QIN alg03'),
    ('RIDER Lung CT | Siemens Corporate Research', 'RIDER · Siemens 2012'),
    ('RIDER Lung CT | pydicom-seg', 'RIDER · pydicom-seg'),
]
CATS = [('match', 'FoR matches CT', BLUE, None),
        ('mismatch', 'FoR differs; all references resolve', ORANGE, '////'),
        ('no_referenced_series', 'No source reference', AQUA, '....')]


def figure1(summary, out):
    fig, ax = plt.subplots(figsize=(6.3, 3.4), dpi=300)
    rows = list(reversed(STRATA))
    for y, (key, label) in enumerate(rows):
        series = summary['strata'][key]['series']
        total = sum(series.get(c, 0) for c, *_ in CATS)
        left = 0.0
        for cat, _, color, hatch in CATS:
            share = series.get(cat, 0) / total
            if share:
                ax.barh(y, share, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=1.2,
                        hatch=hatch)
                if share >= 0.12:
                    # Solid backing so the count stays legible over the hatch.
                    ax.text(left + share / 2, y, f'{series[cat]}', ha='center', va='center', fontsize=7,
                            color='white', fontweight='bold',
                            bbox=dict(boxstyle='round,pad=0.25', facecolor=color, edgecolor='none'))
                left += share
        ax.text(1.01, y, f'n = {total}', va='center', fontsize=7, color=INK2)
    ax.set_yticks(range(len(rows)), [lab for _, lab in rows])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ['0%', '25%', '50%', '75%', '100%'])
    ax.set_xlabel('Share of SEG series in stratum')
    ax.tick_params(axis='y', length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, hatch=h, edgecolor=SURFACE) for _, _, c, h in CATS]
    ax.legend(handles, [lab for _, lab, *_ in CATS], loc='upper center', bbox_to_anchor=(0.45, 1.13), ncol=3,
              frameon=False, fontsize=7, handlelength=1.4)
    fig.tight_layout()
    for ext in ('png', 'tif'):
        fig.savefig(out / f'Figure1.{ext}', dpi=300, facecolor=SURFACE)
    plt.close(fig)


OUTCOMES = [('appropriate', 'Authorized, intended target', BLUE, None),
            ('mismatched', 'Authorized, mismatched target', ORANGE, '////'),
            ('ambiguous', 'Authorized despite ambiguity', '#4a3aa7', 'xxxx'),  # violet: yellow failed next to orange
            ('deferred_ok', 'Deferred appropriately', '#c9c7c0', None),
            ('deferred_unneeded', 'Deferred, target was resolvable', AQUA, '....')]


def episode_outcomes(expa):
    """Per condition, the outcome of every evaluation episode (frozen G0-G3 plus the post hoc G1 variant)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from expA_gate import gate, parse_g2, parse_rules, structural_pass  # noqa: F401
    from expA_posthoc import parse_rules_matched
    table = {s['ct_series']: s for s in json.loads((expa / 'targets.json').read_text())['series']}
    reqs = json.loads((expa / 'requests_eval.json').read_text(encoding='utf-8'))['requests']
    g2 = {json.loads(l)['id']: json.loads(l) for l in (expa / 'g2_eval.jsonl').read_text(encoding='utf-8').splitlines()
          if l.strip()}
    specs = {'G0': lambda r: 'release-all', 'G1': lambda r: parse_rules(r['text']),
             'G1m': lambda r: parse_rules_matched(r['text']), 'G2': lambda r: parse_g2(g2[r['id']]['response']),
             'G3': lambda r: dict(side=r['truth']['side'], ordinal=r['truth']['ordinal'])}
    out = {}
    for cond, spec_of in specs.items():
        counts = {k: 0 for k, *_ in OUTCOMES}
        for r in reqs:
            spec = spec_of(r)
            # G0 authorizes every offered SEG: all offered QIICR SEGs passed the census checks.
            action = 'release' if spec == 'release-all' else gate(spec, table[r['ct_series']]['targets'], r['offered_target'])
            if action == 'release':
                key = ('appropriate' if r['correct_action'] == 'release' else
                       'mismatched' if r['truth']['unique'] else 'ambiguous')
            else:
                key = 'deferred_unneeded' if r['correct_action'] == 'release' else 'deferred_ok'
            counts[key] += 1
        out[cond] = counts
    return out


def figure2(expa, out):
    rows = [('G0', 'G0 Header checks only'), ('G1', 'G1 Rule parser (frozen)'),
            ('G1m', 'G1 + 2 synonyms (post hoc)'), ('G2', 'G2 Choice-constrained model'),
            ('G3', 'G3 Reference specification')]
    data = episode_outcomes(expa)
    (out / 'figure2_counts.json').write_text(json.dumps(data, indent=1))
    fig, ax = plt.subplots(figsize=(6.3, 2.9), dpi=300)
    for y, (cond, _) in enumerate(reversed(rows)):
        total, left = sum(data[cond].values()), 0
        for key, _, color, hatch in OUTCOMES:
            v = data[cond][key]
            if v:
                ax.barh(y, v / total, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=1.2, hatch=hatch)
                if v / total >= 0.06:
                    ax.text(left + v / total / 2, y, str(v), ha='center', va='center', fontsize=7, color=INK,
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.85))
                left += v / total
    ax.set_yticks(range(len(rows)), [lab for _, lab in reversed(rows)])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ['0%', '25%', '50%', '75%', '100%'])
    ax.set_xlabel(f'Share of {sum(data["G0"].values())} evaluation requests')
    ax.tick_params(axis='y', length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=c, hatch=h, edgecolor=SURFACE) for _, _, c, h in OUTCOMES]
    ax.legend(handles, [lab for _, lab, *_ in OUTCOMES], loc='upper center', bbox_to_anchor=(0.4, 1.3), ncol=3,
              frameon=False, fontsize=6.5, handlelength=1.4)
    fig.tight_layout()
    for ext in ('png', 'tif'):
        fig.savefig(out / f'Figure2.{ext}', dpi=300, facecolor=SURFACE)
    plt.close(fig)


READERS_B = [  # (key in paper_results.json, label); groups separated by a gap
    [('R1', 'Rules, v1 (frozen)'), ('M1', 'Model, v1 (frozen)'), ('D1', 'Double reading, v1')],
    [('R2', 'Rules, v2'), ('M2', 'Model, v2'), ('A2', 'Author intent, v2 gate')],
    [('R3', 'Rules, v3 gate'), ('M3', 'Model, v3 gate'), ('A3', 'Author intent, v3 gate'),
     ('D3t', 'Double reading, v3 (target)'), ('D3r', 'Double reading, v3 (reason)')],
]
SETS_B = [(1, 'Set 1 · development'), (2, 'Set 2 · evaluation of v2'), (3, 'Set 3 · confirmatory, v3')]


def figure3(expb, out):
    """Experiment B: per set and reader, requests resolved to the intended nodule (right, blue) and to any
    other nodule (left, orange); the rest were deferred."""
    res = json.loads((expb / 'paper_results.json').read_text(encoding='utf-8'))['sets']
    rows, ys, y = [], [], 0
    for g, group in enumerate(READERS_B):
        for key, label in group:
            rows.append((key, label))
            ys.append(y)
            y -= 1
        y -= 0.6
    fig, axes = plt.subplots(1, 3, figsize=(6.3, 3.6), dpi=300, sharey=True)
    for ax, (s, title) in zip(axes, SETS_B):
        per = res[str(s)]
        n = per['R1']['n']
        for (key, _), yy in zip(rows, ys):
            c, w = per[key]['correct'], per[key]['any_wrong']
            ax.barh(yy, c, height=0.66, color=BLUE, edgecolor=SURFACE, linewidth=0.8)
            ax.barh(yy, -w, height=0.66, color=ORANGE, edgecolor=SURFACE, linewidth=0.8, hatch='////')
            ax.text(c + 0.5, yy, str(c), va='center', ha='left', fontsize=6.3, color=INK)
            if w:
                ax.text(-w - 0.5, yy, str(w), va='center', ha='right', fontsize=6.3, color=INK)
        ax.axvline(0, color=INK2, linewidth=0.8)
        ax.set_xlim(-n - 1, n + 3)
        ax.set_xticks([-n, -n // 2, 0, n // 2, n], [str(n), str(n // 2), '0', str(n // 2), str(n)])
        ax.grid(axis='x', color=GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        ax.set_title(title, fontsize=7.5, loc='left', color=INK)
        ax.tick_params(axis='y', length=0)
    axes[0].set_yticks(ys, [lab for _, lab in rows], fontsize=7)
    axes[1].set_xlabel('Requests (of 20): wrong nodule ←  → intended nodule', fontsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=BLUE, edgecolor=SURFACE),
               plt.Rectangle((0, 0), 1, 1, facecolor=ORANGE, hatch='////', edgecolor=SURFACE)]
    fig.legend(handles, ['Resolved to the intended nodule', 'Resolved to another nodule'], loc='upper center',
               bbox_to_anchor=(0.6, 1.0), ncol=2, frameon=False, fontsize=7, handlelength=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.94), w_pad=1.2)
    for ext in ('png', 'tif'):
        fig.savefig(out / f'Figure3.{ext}', dpi=300, facecolor=SURFACE)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--census', required=True, type=Path)
    ap.add_argument('--expa', required=True, type=Path)
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    figure1(json.loads((args.census / 'summary.json').read_text()), args.out)
    figure2(args.expa, args.out)
    figure3(args.expb, args.out)
    print('written', sorted(p.name for p in args.out.glob('Figure*')))


if __name__ == '__main__':
    main()
