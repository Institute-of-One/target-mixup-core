"""Write FREEZE_v3_before_set3.json. Refuses to overwrite, or to run once any set-3 request exists.

    python expB_freeze_v3.py --expb <expB dir> --paper <paper dir> --gui <jev-workbench dir>
"""
import argparse
import datetime
import json
from pathlib import Path

from expB_freeze_v2 import CORE, sha

CODE = ('expB_readers.py', 'expB_readers_v2.py', 'expB_readers_v3.py', 'expB_regions_v3.py', 'expB_score_v2.py',
        'expB_score_v3.py', 'expB_jev.py', 'expB_diag.py', 'test_expB_v3.py', 'test_expB_readers_v2.py',
        'test_expB_score_v2.py')
DATA = ('regions.json', 'regions_v3.json', 'lobes.json', 'series.json', 'requests_expert.jsonl',
        'model_responses.jsonl', 'model_responses_v2b.jsonl', 'author_specs.jsonl')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--paper', required=True, type=Path)
    ap.add_argument('--gui', required=True, type=Path)
    args = ap.parse_args(argv)
    out = args.expb / 'FREEZE_v3_before_set3.json'
    if out.exists():
        raise SystemExit('Already frozen; not overwritten.')
    reqs = [json.loads(l) for l in (args.expb / 'requests_expert.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    if any(r.get('set') == 3 for r in reqs):
        raise SystemExit('Set-3 requests already exist; refusing to freeze after the fact.')
    record = dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  stage='v3 gates frozen after sets 1-2 were scored, before any set-3 request',
                  requests_by_set={s: sum(r.get('set', 1) == s for r in reqs) for s in (1, 2)},
                  files={f: sha(CORE / f) for f in CODE},
                  gui={f: sha(args.gui / f) for f in ('authoring_service.py', 'src/Authoring.jsx', 'src/Labelling.jsx')},
                  design={'EXPERIMENT_B_AMENDMENT_v3_20260926.md': sha(args.paper / 'EXPERIMENT_B_AMENDMENT_v3_20260926.md')},
                  data={f: sha(args.expb / f) for f in DATA},
                  approved_by='Shuji Yamamoto (chat, 2026-09-26: freeze and prepare set 3)')
    out.write_text(json.dumps(record, indent=1))
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main()
