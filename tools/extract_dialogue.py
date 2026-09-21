#!/usr/bin/env python3
import argparse, shutil, subprocess, sys, zipfile
from pathlib import Path
TARGET_BASENAME='text_ui_dialog.xml'
def find_7z():
    candidates=[shutil.which('7z'),shutil.which('7zz'),shutil.which('7za'),r'C:\\Program Files\\7-Zip\\7z.exe',r'C:\\Program Files (x86)\\7-Zip\\7z.exe']
    for c in candidates:
        if c and Path(c).exists(): return str(c)
    return None
def extract_with_zip(pak,out_dir):
    try:
        with zipfile.ZipFile(pak) as zf:
            matches=[n for n in zf.namelist() if Path(n).name.lower()==TARGET_BASENAME]
            if not matches: return False,'target not found in ZIP directory'
            member=sorted(matches,key=lambda x:(x.count('/'),len(x)))[0]
            out_dir.mkdir(parents=True,exist_ok=True)
            with zf.open(member) as src, open(out_dir/TARGET_BASENAME,'wb') as dst: shutil.copyfileobj(src,dst)
            return True,member
    except zipfile.BadZipFile: return False,'not readable by Python zipfile'
def extract_with_7z(sevenzip,pak,out_dir):
    out_dir.mkdir(parents=True,exist_ok=True)
    cp=subprocess.run([sevenzip,'l','-slt',str(pak)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if cp.returncode!=0: return False,cp.stderr.strip() or '7-Zip list failed'
    members=[]
    for line in cp.stdout.splitlines():
        if line.startswith('Path = '):
            val=line[7:].strip()
            if Path(val).name.lower()==TARGET_BASENAME: members.append(val)
    if not members: return False,'target not found in archive'
    member=sorted(members,key=lambda x:(x.count('\\')+x.count('/'),len(x)))[0]
    cp=subprocess.run([sevenzip,'e','-y',f'-o{out_dir}',str(pak),member],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if cp.returncode!=0 or not (out_dir/TARGET_BASENAME).exists(): return False,cp.stderr.strip() or cp.stdout.strip() or '7-Zip extract failed'
    return True,member
def lang_from_name(name):
    stem=Path(name).stem
    if stem.lower().endswith('_xml'): stem=stem[:-4]
    return stem
def main():
    ap=argparse.ArgumentParser(description='Extract text_ui_dialog.xml from all KCD2 localization PAKs.')
    ap.add_argument('--repo',default='.')
    ap.add_argument('--source',default='localization')
    ap.add_argument('--dest',default='reference/localization')
    args=ap.parse_args(); repo=Path(args.repo).resolve(); src=repo/args.source; dest=repo/args.dest
    if not src.exists(): raise SystemExit(f'Missing source folder: {src}')
    paks=sorted(src.glob('*_xml.pak'))
    if not paks: raise SystemExit(f'No *_xml.pak files found in {src}')
    sevenzip=find_7z(); print(f'Found {len(paks)} localization PAKs')
    if sevenzip: print(f'7-Zip fallback: {sevenzip}')
    ok_count=0
    for pak in paks:
        lang=lang_from_name(pak.name); out_dir=dest/lang; ok,note=extract_with_zip(pak,out_dir); method='zipfile'
        if not ok and sevenzip: ok,note=extract_with_7z(sevenzip,pak,out_dir); method='7-Zip'
        if ok: ok_count+=1; print(f'[OK] {lang:12} -> {out_dir/TARGET_BASENAME} ({method}; {note})')
        else: print(f'[FAIL] {lang:12} {note}')
    print(f'\nExtracted {ok_count}/{len(paks)} language files.')
    if ok_count!=len(paks): sys.exit(2)
if __name__=='__main__': main()
