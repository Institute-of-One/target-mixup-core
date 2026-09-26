"""Experiment A, G2 calls: send each frozen request text to the choice model once.

Only the request text is sent (no image, identifier, truth or target data). The API key is read
without echo and kept in this process only. Each request is attempted once: failures are recorded,
never retried. Already answered ids are skipped, so an interrupted run can be resumed. A hard cap on
the number of calls is required.

    python expA_jev.py --expa <expA dir> --split dev|eval --max-calls N
"""
import argparse
import getpass
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from expA_gate import g2_request

ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
PAUSE_S = 0.5
MAX_CONSECUTIVE_FAILURES = 3
CLIPBOARD = False  # set by --key-from-clipboard
PREFLIGHT_TEXT = 'Measure the largest nodule in the right lung.'  # not an evaluation request


def read_key():
    """Key from the clipboard (--key-from-clipboard), else TYPESAFE_API_KEY, else hidden entry.

    Ctrl+V in a Windows console can insert a control character instead of the clipboard; such
    input is refused before anything is sent. Only counts are reported, never the key itself.
    """
    if CLIPBOARD:
        # The command itself is usually pasted from the clipboard, so ask for the key only now.
        # getpass: anything typed or pasted here is not echoed; the key is read from the clipboard.
        getpass.getpass('Copy the TypeSafe API key now, then press Enter here (no need to paste): ')
        # Windows clipboard via PowerShell; cleared right after reading.
        key = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard -Raw'],
                             capture_output=True, text=True).stdout.strip()
        subprocess.run(['powershell', '-NoProfile', '-Command', 'Set-Clipboard -Value $null'], capture_output=True)
        source = 'clipboard (now cleared)'
    elif os.environ.get('TYPESAFE_API_KEY', '').strip():
        key, source = os.environ['TYPESAFE_API_KEY'].strip(), 'TYPESAFE_API_KEY in this shell'
    else:
        key = getpass.getpass('TypeSafe API key (not echoed; paste with right-click): ').strip()
        source = 'hidden entry'
    control = sum(ord(c) < 32 or ord(c) == 127 for c in key)
    spaces = sum(c.isspace() for c in key)
    non_ascii = sum(ord(c) > 126 for c in key)
    print(f'Key source: {source}; {len(key)} characters.')
    if not key or control or spaces or non_ascii:
        raise SystemExit(f'Key refused: {control} control, {spaces} whitespace, {non_ascii} non-ASCII characters. '
                         'Copy the key again (for example from the TypeSafe dashboard) and retry. Nothing was sent.')
    return key


def call(body, key):
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(ENDPOINT, data=data, headers={'Authorization': 'Bearer ' + key,
                                                               'Content-Type': 'application/json'})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return dict(status=r.status, response=json.load(r), latency_s=round(time.perf_counter() - started, 3))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode('utf-8', 'replace')[:2000]
        except Exception:
            detail = ''
        return dict(status=exc.code, response=None, error=f'HTTP {exc.code}', error_body=detail,
                    latency_s=round(time.perf_counter() - started, 3))
    except Exception as exc:  # recorded as a failed call; not retried
        return dict(status=None, response=None, error=type(exc).__name__, latency_s=round(time.perf_counter() - started, 3))


def probe(key):
    """Four diagnostic calls on a development text; prints status and error bodies. Not evaluation data."""
    from copy import deepcopy
    text_ja, text_en = '右肺で最も大きい結節の体積と平均CT値を測ってください。', 'Measure the largest nodule in the right lung.'
    base = g2_request(text_ja)
    single = deepcopy(base)
    single['questions'] = {'side': base['questions']['side']}
    english = g2_request(text_en)
    plain = deepcopy(base)
    for q in plain['questions'].values():
        q['criteria'] = {k: v.replace("'", '') for k, v in q['criteria'].items()}
    for name, body in (('as_frozen', base), ('single_question', single), ('english_text', english),
                       ('no_apostrophe', plain)):
        result = call(body, key)
        print(name, result['status'], json.dumps(result.get('response') or result.get('error_body'), ensure_ascii=False)[:600])
        time.sleep(PAUSE_S)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--expa', type=Path)
    ap.add_argument('--split', choices=('dev', 'eval'))
    ap.add_argument('--max-calls', type=int)
    ap.add_argument('--probe', action='store_true', help='four diagnostic calls only')
    ap.add_argument('--key-from-clipboard', action='store_true', help='read the key from the clipboard, then clear it')
    args = ap.parse_args(argv)
    global CLIPBOARD
    CLIPBOARD = args.key_from_clipboard
    if args.probe:
        probe(read_key())
        return
    if not (args.expa and args.split and args.max_calls):
        raise SystemExit('--expa, --split and --max-calls are required')
    requests = json.loads((args.expa / f'requests_{args.split}.json').read_text(encoding='utf-8'))['requests']
    out_path = args.expa / f'g2_{args.split}.jsonl'
    done = set()
    if out_path.exists():
        done = {json.loads(line)['id'] for line in out_path.read_text(encoding='utf-8').splitlines() if line.strip()}
    todo = [q for q in requests if q['id'] not in done]
    print(f'{len(requests)} requests, {len(done)} already recorded, {len(todo)} to send; cap {args.max_calls}.')
    if len(todo) > args.max_calls:
        raise SystemExit('More requests than --max-calls; nothing sent.')
    if not todo:
        return
    key = read_key()
    # Preflight on a fixed development text: a key or transport problem must not consume requests.
    check = call(g2_request(PREFLIGHT_TEXT), key)
    if check['status'] != 200:
        raise SystemExit(f"Preflight failed ({check.get('error')}: {check.get('error_body', '')[:200]}); nothing sent.")
    print('Preflight OK.')
    failures = 0
    with out_path.open('a', encoding='utf-8') as out:
        for i, q in enumerate(todo, 1):
            body = g2_request(q['text'])
            result = call(body, key)
            record = dict(id=q['id'], request_sha256=hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False)
                                                                   .encode()).hexdigest(),
                          utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **result)
            out.write(json.dumps(record, ensure_ascii=False) + '\n')
            out.flush()
            print(f"{i}/{len(todo)} {q['id']} {result['status']} {result['latency_s']}s", flush=True)
            failures = failures + 1 if result['status'] != 200 else 0
            if failures >= MAX_CONSECUTIVE_FAILURES:
                raise SystemExit(f'{failures} consecutive failures; stopped. Remaining requests were not sent.')
            time.sleep(PAUSE_S)
    del key


if __name__ == '__main__':
    main()
