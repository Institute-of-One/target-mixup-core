"""The one place a parser, condition or outcome is given a name.

Table 1 and Figure 4 named the same parsers differently because each held its
own copy of the labels: the manuscript's table was typed by hand and the figure
carried READERS_B. A reviewer found the two disagreeing. Everything that prints
a name now reads it from here, and check_labels_agree.py fails if a name is
written anywhere else.

A name has two parts, kept apart so each consumer can compose its own form:

    code   the identifier the body and the abstract use ('D3t'), and the key in
           paper_results.json / figure2_counts.json
    words  what it means, lower case, no code in it

The table prints "D3t consensus, v3 (same target)"; the figure prints
"D3t * consensus, v3 (same target)". Neither spells a name out.
"""

# Experiment B parsers, in the order they are drawn. The three groups are the
# three design versions and are separated by a gap on the figure.
READERS_B = [
    [('R1', 'rules, v1 (frozen)'),
     ('M1', 'model, v1 (frozen)'),
     ('D1', 'consensus, v1')],
    [('R2', 'rules, v2'),
     ('M2', 'model, v2'),
     ('A2', 'author intent, v2 gate')],
    [('R3', 'rules, v3 gate'),
     ('M3', 'model, v3 gate'),
     ('A3', 'author intent, v3 gate'),
     ('D3t', 'consensus, v3 (same target)'),
     ('D3r', 'consensus, v3 (same fields)')],
]

# Experiment A conditions, in the order they are drawn.
CONDITIONS_A = [
    ('G0', 'header checks only'),
    ('G1', 'rule parser (frozen)'),
    ('G1m', 'rule parser + 2 synonyms (post hoc)'),
    ('G2', 'choice-constrained model'),
    ('G3', 'reference specification'),
]

# The five outcomes of one authorization episode, with the colour and hatch each
# is drawn in. The same five are the columns of the per-condition table, so the
# table cannot invent a sixth category or rename one.
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
VIOLET, GREY = '#4a3aa7', '#c9c7c0'  # violet: yellow failed next to orange
OUTCOMES = [
    ('appropriate', 'Authorized, intended target', BLUE, None),
    ('mismatched', 'Authorized, mismatched target', ORANGE, '////'),
    ('ambiguous', 'Authorized despite ambiguity', VIOLET, 'xxxx'),
    ('deferred_ok', 'Deferred appropriately', GREY, None),
    ('deferred_unneeded', 'Deferred, target was resolvable', AQUA, '....'),
]


# The ten audit strata, in the order Figure 2 draws them: the key in the census
# summary, the collection and the producer. Figure 2 joined these two parts itself
# and the strata table in the manuscript would have been a second hand-typed copy,
# which is the defect labels.py exists for.
STRATA = [
    ('LIDC-IDRI | QIICR', 'LIDC', 'QIICR 2019'),
    ('LIDC-IDRI | QIN challenge alg01', 'LIDC', 'QIN alg01'),
    ('LIDC-IDRI | QIN challenge alg02', 'LIDC', 'QIN alg02'),
    ('LIDC-IDRI | QIN challenge alg03', 'LIDC', 'QIN alg03'),
    ('RIDER Lung CT | QIICR', 'RIDER', 'QIICR'),
    ('RIDER Lung CT | QIN challenge alg01', 'RIDER', 'QIN alg01'),
    ('RIDER Lung CT | QIN challenge alg02', 'RIDER', 'QIN alg02'),
    ('RIDER Lung CT | QIN challenge alg03', 'RIDER', 'QIN alg03'),
    ('RIDER Lung CT | Siemens Corporate Research', 'RIDER', 'Siemens 2012'),
    ('RIDER Lung CT | pydicom-seg', 'RIDER', 'pydicom-seg'),
]


def stratum_slug(collection, producer):
    """The key of a stratum's numbers, short enough to read inside a table cell."""
    return ''.join(c for c in f'{collection}_{producer}'.lower() if c.isalnum() or c == '_')


def readers_b_flat():
    """(code, words) for every Experiment B parser, groups flattened."""
    return [pair for group in READERS_B for pair in group]


def table_form(code, words):
    """How Table 1 and the manuscript body print a name."""
    return f'{code} {words}'


def figure_form(code, words):
    """How a figure axis prints a name. The separator is the figure's own."""
    return f'{code} · {words}'


def stratum_figure_form(collection, producer):
    """How Figure 2 prints a stratum; the table prints the two parts in two columns."""
    return f'{collection} · {producer}'


def compact_producers(keys):
    """Name a set of strata in one table cell.

    One coded concept is written by as many as eight of the ten strata, and
    spelling each in full needs a column no table can hold. Producers are grouped
    under their collection and a run that differs only in a trailing number is
    closed up, so that the eight become
    "LIDC: QIN alg01-03; RIDER: QIICR, QIN alg01-03, Siemens 2012".
    """
    import re
    by_collection = {}
    for key, collection, producer in STRATA:          # STRATA fixes the order
        if key in keys:
            by_collection.setdefault(collection, []).append(producer)
    parts = []
    for collection, producers in by_collection.items():
        runs = []
        for p in producers:
            m = re.match(r'(.*?)(\d+)$', p)
            if m and runs and runs[-1][0] == m.group(1):
                runs[-1][2] = m.group(2)
            else:
                runs.append([m.group(1), m.group(2), None] if m else [p, None, None])
        words = [stem if first is None else
                 f'{stem}{first}' if last is None else f'{stem}{first}-{last}'
                 for stem, first, last in runs]
        parts.append('%s: %s' % (collection, ', '.join(words)))
    return '; '.join(parts)
