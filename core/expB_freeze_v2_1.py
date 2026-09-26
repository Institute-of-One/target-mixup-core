"""Amendment v2.1 freeze: labelling fields and scorer after set 2 was written, before any set-2 reader
output or score was produced. Refuses to overwrite, or to run once any author label exists.

    python expB_freeze_v2_1.py --expb <expB dir> --paper <paper dir> --gui <jev-workbench dir>
"""
import argparse
import datetime
import json
from pathlib import Path

from expB_freeze_v2 import CORE, sha


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--paper', required=True, type=Path)
    ap.add_argument('--gui', required=True, type=Path)
    args = ap.parse_args(argv)
    out = args.expb / 'FREEZE_v2_1_labels.json'
    if out.exists():
        raise SystemExit('Already frozen; not overwritten.')
    if (args.expb / 'author_specs.jsonl').exists():
        raise SystemExit('Author labels already exist; refusing to freeze after the fact.')
    model_ids = {json.loads(l)['id'] for f in ('model_responses.jsonl', 'model_responses_v2b.jsonl')
                 for l in (args.expb / f).read_text(encoding='utf-8').splitlines() if l.strip()}
    reqs = [json.loads(l) for l in (args.expb / 'requests_expert.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    set2 = [r for r in reqs if r.get('set') == 2]
    record = dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  stage='amendment v2.1: marker label removed; set 2 written; set-2 model outputs may exist '
                        '(counted below) but were neither read nor scored; no author label exists',
                  set2_requests=len(set2), set2_model_outputs=sum(r['saved_utc'] in model_ids for r in set2),
                  files={f: sha(CORE / f) for f in ('expB_score_v2.py', 'test_expB_score_v2.py', 'expB_readers_v2.py')},
                  gui={f: sha(args.gui / f) for f in ('authoring_service.py', 'src/Labelling.jsx')},
                  design={'EXPERIMENT_B_AMENDMENT_v2_20260925.md': sha(args.paper / 'EXPERIMENT_B_AMENDMENT_v2_20260925.md')},
                  data={'requests_expert.jsonl': sha(args.expb / 'requests_expert.jsonl')},
                  requested_by='Shuji Yamamoto (chat, 2026-09-25: the marking question cannot discriminate)')
    out.write_text(json.dumps(record, indent=1))
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main()
