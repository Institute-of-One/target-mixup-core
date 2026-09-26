"""Experiment B, model reader calls: each expert request text sent once to Jev (frozen request in
expB_readers). Same safeguards as expA_jev: key from clipboard or environment, preflight on a
non-evaluation text, stop after three consecutive failures, no retry, resume skips recorded ids.

    python expB_jev.py --expb <expB dir> --max-calls N --key-from-clipboard [--reader v2]
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import expA_jev
from expA_jev import call, read_key
from expB_readers import model_request
from expB_readers_v2 import model_request_v2

PREFLIGHT = 'Measure the largest nodule in the right lower lobe.'  # not an expert request


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expb', required=True, type=Path)
    ap.add_argument('--max-calls', required=True, type=int)
    ap.add_argument('--key-from-clipboard', action='store_true')
    ap.add_argument('--probe', action='store_true', help='two diagnostic calls on a non-evaluation text')
    ap.add_argument('--reader', choices=('v1', 'v2'), default='v1',
                    help='v1: frozen request (model_responses.jsonl); v2: model_responses_v2.jsonl')
    ap.add_argument('--out', help='output file name in --expb (overrides the default for --reader)')
    args = ap.parse_args(argv)
    expA_jev.CLIPBOARD = args.key_from_clipboard
    if args.probe:
        import copy
        key = read_key()
        frozen = model_request(PREFLIGHT)
        renamed = copy.deepcopy(frozen)
        renamed['questions']['size']['criteria'] = {('s' + k if k[0].isdigit() else k): v
                                                    for k, v in frozen['questions']['size']['criteria'].items()}
        for name, body in (('as_frozen', frozen), ('size_keys_renamed', renamed)):
            res = call(body, key)
            print(name, res['status'], json.dumps(res.get('response') or res.get('error_body'), ensure_ascii=False)[:500])
            time.sleep(expA_jev.PAUSE_S)
        return
    reqs = [json.loads(l) for l in (args.expb / 'requests_expert.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    ids = {r['saved_utc']: r for r in reqs}
    build = model_request if args.reader == 'v1' else model_request_v2
    out_path = args.expb / (args.out or ('model_responses.jsonl' if args.reader == 'v1' else 'model_responses_v2.jsonl'))
    done = set()
    if out_path.exists():
        done = {json.loads(l)['id'] for l in out_path.read_text(encoding='utf-8').splitlines() if l.strip()}
    todo = [(k, r) for k, r in ids.items() if k not in done]
    print(f'{len(ids)} requests, {len(done)} recorded, {len(todo)} to send; cap {args.max_calls}.')
    if len(todo) > args.max_calls:
        raise SystemExit('More requests than --max-calls; nothing sent.')
    if not todo:
        return
    key = read_key()
    check = call(build(PREFLIGHT), key)
    if check['status'] != 200:
        raise SystemExit(f"Preflight failed ({check.get('error')}: {check.get('error_body', '')[:300]}); nothing sent.")
    print('Preflight OK.')
    failures = 0
    with out_path.open('a', encoding='utf-8') as out:
        for i, (rid, r) in enumerate(todo, 1):
            body = build(r['text'])
            res = call(body, key)
            out.write(json.dumps(dict(id=rid, request_sha256=hashlib.sha256(json.dumps(body, sort_keys=True,
                      ensure_ascii=False).encode()).hexdigest(), utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      **res), ensure_ascii=False) + '\n')
            out.flush()
            print(f"{i}/{len(todo)} {res['status']} {res['latency_s']}s", flush=True)
            failures = failures + 1 if res['status'] != 200 else 0
            if failures >= 3:
                raise SystemExit('3 consecutive failures; stopped. Remaining requests were not sent.')
            time.sleep(expA_jev.PAUSE_S)


if __name__ == '__main__':
    main()
