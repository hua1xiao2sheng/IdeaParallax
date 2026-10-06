#!/usr/bin/env python3
"""Build a checksum manifest from explicitly Git-tracked release files, then a ZIP."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from publish_github import ROOT, allowed_path, release_files

def build(root: Path, out: Path | None = None) -> dict:
    raw = subprocess.check_output(["git", "-C", str(root), "ls-files", "-z"])
    names = sorted(x for x in raw.decode("utf-8").split("\0") if x and x != "release-files.json")
    entries=[]
    for name in names:
        path=root/name
        if not allowed_path(name) or path.is_symlink():
            raise ValueError("Unapproved tracked file; release stopped")
        entries.append({"path":name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest={"project":"IdeaParallax","version":"0.1.0","files":entries,
              "note":"Checksums detect changes; this is not a cryptographic author signature. Runtime inputs and credentials are excluded."}
    (root/'release-files.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    contents=release_files(root)
    if out is not None:
        if out.exists():raise FileExistsError("Refusing to overwrite an existing release archive")
        out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in contents:
                archive.writestr('IdeaParallax/'+name,data)
            archive.write(root/'release-files.json','IdeaParallax/release-files.json')
    return {'files':len(entries)+1,'archive':str(out) if out else None}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);args=p.parse_args()
    print(json.dumps(build(ROOT,args.out),indent=2))
