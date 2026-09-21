#!/usr/bin/env python3
import argparse, csv
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description='Sanity-check the generated Rosetta alignment CSV.')
    ap.add_argument('--repo',default='.')
    ap.add_argument('--file',default='reference/aligned/localization_alignment.csv')
    args=ap.parse_args(); p=Path(args.repo).resolve()/args.file
    if not p.exists(): raise SystemExit(f'Missing alignment file: {p}')
    with open(p,encoding='utf-8-sig',newline='') as fh:
        r=csv.reader(fh); header=next(r)
        keys=set(); dup=0; rows=0; populated=[0]*(len(header)-1)
        for row in r:
            rows+=1
            if not row: continue
            if row[0] in keys: dup+=1
            keys.add(row[0])
            for i,v in enumerate(row[1:]):
                if v.strip(): populated[i]+=1
    print(f'Rows: {rows:,}')
    print(f'Unique keys: {len(keys):,}')
    print(f'Duplicate keys: {dup:,}')
    for lang,count in zip(header[1:],populated): print(f'{lang:14} {count:,} populated')
    if dup: raise SystemExit(2)

if __name__=='__main__': main()
