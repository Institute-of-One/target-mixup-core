"""The segmentation environment, recorded once from the environment that ran it.

The reproducibility table names the TotalSegmentator version and the torch build the
lobe masks were computed with. Both used to be read, at the moment the numbers were
assembled, out of the ts-venv that ran them - which is correct about provenance and
impossible from the published archive, because the archive carries no venv. Continuous
integration regenerates the reported numbers from the released inputs, so a value that
can only be read on one machine cannot be among them, and the job that claimed to
regenerate every number would have failed on the first.

So the reading stays where it was and its result is written down: this script reads the
venv and records what it found, the record ships with the results, and the paper's
number comes from the record. The value is still read from the environment that ran the
segmentation, never typed, and the archive can now reproduce the table.

Run it where the segmentation ran, before paper/manuscript_numbers.py.

    python record_environment.py --expb <expB dir> [--ts-venv <dir>]
"""
import argparse
import json
from pathlib import Path

SOURCE = 'ts-venv/…dist-info'


def read(ts_venv):
    """(TotalSegmentator version, torch version) as the installed venv reports them."""
    site = ts_venv / 'Lib' / 'site-packages'
    dist = sorted(site.glob('[Tt]otal[Ss]egmentator-*.dist-info'))
    if not dist:
        raise SystemExit('TotalSegmentator is not installed in %s; its version cannot be '
                         'read. Run this where the segmentation ran.' % ts_venv)
    ts = dist[-1].name.split('-')[1].removesuffix('.dist')
    # "CPU" is a claim about the machine, so read it from the build that ran there: a
    # +cpu wheel of torch has no CUDA at all. Neither the directory name nor METADATA
    # keeps the local version, so read the module's own version.py, where the +cpu of a
    # CPU-only wheel survives.
    torch_py = site / 'torch' / 'version.py'
    if not torch_py.exists():
        raise SystemExit('torch is not installed in %s' % ts_venv)
    torch = next(l.split('=', 1)[1].strip().strip('\'"') for l in
                 torch_py.read_text(encoding='utf-8').splitlines()
                 if l.startswith('__version__'))
    if not torch.endswith('+cpu'):
        raise SystemExit('torch in %s is %s, not a CPU build' % (ts_venv, torch))
    return ts, torch


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--ts-venv', type=Path, default=None,
                    help='default: ts-venv beside the results directories')
    args = ap.parse_args(argv)
    ts_venv = args.ts_venv or args.expb.parent / 'ts-venv'
    ts, torch = read(ts_venv)
    out = args.expb / 'environment.json'
    out.write_text(json.dumps({'ts_version': ts, 'torch': torch, 'read_from': SOURCE},
                              indent=2) + '\n', encoding='utf-8')
    print('%s: TotalSegmentator %s, torch %s' % (out.name, ts, torch))


if __name__ == '__main__':
    main()
