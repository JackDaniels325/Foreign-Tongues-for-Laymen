#!/usr/bin/env python3
import argparse, csv
from pathlib import Path
import xml.etree.ElementTree as ET


def cell_text(cell):
    # Preserve visible text while flattening any inline markup into text.
    return ''.join(cell.itertext()).strip()


def parse_file(path: Path):
    """Parse KCD2 dialog XML rows of the form:
    <Row><Cell>key</Cell><Cell>reference</Cell><Cell>display</Cell></Row>

    Returns key -> (reference, display).
    """
    out = {}
    duplicates = 0
    malformed = 0
    for _, elem in ET.iterparse(path, events=('end',)):
        if elem.tag.rsplit('}', 1)[-1] != 'Row':
            continue
        cells = [c for c in list(elem) if c.tag.rsplit('}', 1)[-1] == 'Cell']
        if len(cells) < 3:
            malformed += 1
            elem.clear()
            continue
        key = cell_text(cells[0])
        ref = cell_text(cells[1])
        display = cell_text(cells[2])
        if not key:
            malformed += 1
            elem.clear()
            continue
        if key in out:
            duplicates += 1
        else:
            out[key] = (ref, display)
        elem.clear()
    return out, duplicates, malformed


def main():
    ap = argparse.ArgumentParser(description='Align extracted KCD2 text_ui_dialog.xml files by exact localization key.')
    ap.add_argument('--repo', default='.')
    ap.add_argument('--source', default='reference/localization')
    ap.add_argument('--output', default='reference/aligned/localization_alignment.csv')
    ap.add_argument('--pairs-output', default='reference/aligned/direct_reference_pairs.csv')
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    src = repo / args.source
    outpath = repo / args.output
    pairpath = repo / args.pairs_output
    files = sorted(src.glob('*/text_ui_dialog.xml'))
    if not files:
        raise SystemExit(f'No extracted XML files found under {src}')

    lang_maps = {}
    parse_stats = {}
    for f in files:
        lang = f.parent.name
        print(f'Parsing {lang}: {f}')
        data, dup, malformed = parse_file(f)
        lang_maps[lang] = data
        parse_stats[lang] = (dup, malformed)
        print(f'  {len(data):,} keyed rows | duplicate keys: {dup:,} | malformed rows: {malformed:,}')

    all_keys = sorted(set().union(*(m.keys() for m in lang_maps.values())))
    langs = sorted(lang_maps)
    outpath.parent.mkdir(parents=True, exist_ok=True)

    with open(outpath, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        header = ['localization_key']
        for lang in langs:
            header.extend([f'{lang}_reference', f'{lang}_display'])
        w.writerow(header)
        for key in all_keys:
            row = [key]
            for lang in langs:
                ref, display = lang_maps[lang].get(key, ('', ''))
                row.extend([ref, display])
            w.writerow(row)

    # Build a compact high-value candidate set from English rows where the
    # reference/meaning cell differs from the player-facing display cell.
    # These are especially useful when the display retains a foreign phrase.
    english = lang_maps.get('English', {})
    with open(pairpath, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        w.writerow(['localization_key', 'English_reference', 'English_display'])
        count = 0
        for key in sorted(english):
            ref, display = english[key]
            if ref and display and ref != display:
                w.writerow([key, ref, display])
                count += 1

    print(f'Wrote {len(all_keys):,} aligned keys across {len(langs)} languages -> {outpath}')
    print(f'Wrote {count:,} English reference/display differences -> {pairpath}')

if __name__ == '__main__':
    main()
