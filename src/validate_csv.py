#!/usr/bin/env python3
"""Validate relayout CSV before generating PDF."""
from __future__ import annotations
import argparse, csv, json, re, sys

QRANGE_RE = re.compile(r"^(\d{3})[-~](\d{3})$")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('csv')
    args = ap.parse_args()
    ok = True
    rows = list(csv.DictReader(open(args.csv, encoding='utf-8-sig')))
    seen = []
    for idx, r in enumerate(rows, 1):
        qr = (r.get('qrange') or '').strip()
        m = QRANGE_RE.match(qr)
        if not m:
            print(f'row {idx}: invalid qrange {qr!r}')
            ok = False; continue
        start, end = int(m.group(1)), int(m.group(2))
        expected = [f'{n:03d}' for n in range(start, end+1)]
        try:
            qs = json.loads(r.get('questions_json') or '[]')
        except Exception as e:
            print(f'row {idx} {qr}: questions_json parse error: {e}')
            ok = False; continue
        nums = [str(q.get('num','')).zfill(3) for q in qs]
        if nums != expected:
            print(f'row {idx} {qr}: question numbers mismatch; expected {expected}, got {nums}')
            ok = False
        if not (r.get('passage') or '').strip():
            print(f'row {idx} {qr}: empty passage')
            ok = False
        for q in qs:
            opts = q.get('options') or {}
            if isinstance(opts, list):
                count = len(opts)
            else:
                count = len(opts.keys())
            if count < 2:
                print(f'row {idx} {qr} q{q.get("num")}: too few options ({count})')
                ok = False
        seen.extend(nums)
    dups = sorted({x for x in seen if seen.count(x) > 1})
    if dups:
        print('duplicate question numbers:', dups)
        ok = False
    if ok:
        print(f'OK: {len(rows)} passage rows, {len(seen)} questions')
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
