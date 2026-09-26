"""Write FREEZE_v2_before_set2.json (hashes of the v2 readers, scorer, tests, region data, amendment).

Refuses to overwrite an existing freeze and refuses if any set-2 request already exists.

    python expB_freeze_v2.py --expb <expB dir> --paper <paper dir>
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

CORE = Path(__file__).resolve().parent
CODE = ('expB_readers.py', 'expB_readers_v2.py', 'expB_regions.py', 'expB_jev.py', 'expB_score_v2.py',
        'expB_dev_v2.py', 'test_expB_readers_v2.py', 'test_expB_score_v2.py')
DATA = ('regions.json', 'lobes.json', 'series.json', 'requests_expert.jsonl', 'model_responses.jsonl',
        'model_responses_v2.jsonl', 'model_responses_v2b.jsonl')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--paper', required=True, type=Path)
    args = ap.parse_args(argv)
    out = args.expb / 'FREEZE_v2_before_set2.json'
    if out.exists():
        raise SystemExit('Already frozen; not overwritten.')
    reqs = [json.loads(l) for l in (args.expb / 'requests_expert.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    if any(r.get('set') == 2 for r in reqs):
        raise SystemExit('Set-2 requests already exist; refusing to freeze after the fact.')
    record = dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  stage='v2 readers frozen after set 1 (development), before any set-2 request',
                  set1_requests=len(reqs),
                  files={f: sha(CORE / f) for f in CODE},
                  design={'EXPERIMENT_B_AMENDMENT_v2_20260925.md': sha(args.paper / 'EXPERIMENT_B_AMENDMENT_v2_20260925.md')},
                  data={f: sha(args.expb / f) for f in DATA},
                  approved_by='Shuji Yamamoto (chat, 2026-09-25: proceed as proposed)')
    out.write_text(json.dumps(record, indent=1))
    print(json.dumps(record, indent=1))


if __name__ == '__main__':
    main()
