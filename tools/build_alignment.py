#!/usr/bin/env python3
import argparse, csv, re
from pathlib import Path
import xml.etree.ElementTree as ET

ID_NAMES = {'id','key','name','uid','uuid','localization_key','string_id'}
TEXT_NAMES = {'text','value','translation','localized','content','display_text','english'}

def clean(s):
    if s is None: return ''
    return re.sub(r'\s+', ' ', str(s)).strip()

def infer_pair(elem):
    # Prefer attributes commonly used by localization XML.
    attrs = {k.lower(): v for k,v in elem.attrib.items()}
    key = ''
    for n in ID_NAMES:
        if n in attrs and clean(attrs[n]):
            key = clean(attrs[n]); break
    vals = []
    for n in TEXT_NAMES:
        if n in attrs and clean(attrs[n]): vals.append(clean(attrs[n]))
    # Include child text/attributes as a fallback.
    for child in list(elem):
        ca = {k.lower(): v for k,v in child.attrib.items()}
        if not key:
            for n in ID_NAMES:
                if n in ca and clean(ca[n]): key = clean(ca[n]); break
        for n in TEXT_NAMES:
            if n in ca and clean(ca[n]): vals.append(clean(ca[n]))
        if clean(child.text): vals.append(clean(child.text))
    if clean(elem.text): vals.append(clean(elem.text))
    # Deduplicate while retaining order.
    seen=[]
    for v in vals:
        if v and v not in seen: seen.append(v)
    if key and seen:
        return key, seen[-1]
    return None

def parse_file(path: Path):
    out = {}
    # iterparse avoids loading very large XML fully into RAM.
    for _, elem in ET.iterparse(path, events=('end',)):
        pair = infer_pair(elem)
        if pair:
            k,v = pair
            # Keep first non-empty value for stability.
            if k not in out or not out[k]: out[k] = v
        elem.clear()
    return out

def main():
    ap = argparse.ArgumentParser(description='Align extracted KCD2 text_ui_dialog.xml files by exact localization key.')
    ap.add_argument('--repo', default='.')
    ap.add_argument('--source', default='reference/localization')
    ap.add_argument('--output', default='reference/aligned/localization_alignment.csv')
    args=ap.parse_args()
    repo=Path(args.repo).resolve(); src=repo/args.source; outpath=repo/args.output
    files=sorted(src.glob('*/text_ui_dialog.xml'))
    if not files: raise SystemExit(f'No extracted XML files found under {src}')

    lang_maps={}
    for f in files:
        lang=f.parent.name
        print(f'Parsing {lang}: {f}')
        lang_maps[lang]=parse_file(f)
        print(f'  {len(lang_maps[lang]):,} keyed rows')

    all_keys=sorted(set().union(*(m.keys() for m in lang_maps.values())))
    langs=sorted(lang_maps)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with open(outpath,'w',newline='',encoding='utf-8-sig') as fh:
        w=csv.writer(fh)
        w.writerow(['localization_key']+langs)
        for key in all_keys:
            w.writerow([key]+[lang_maps[l].get(key,'') for l in langs])
    print(f'Wrote {len(all_keys):,} aligned keys across {len(langs)} languages -> {outpath}')

if __name__=='__main__': main()
