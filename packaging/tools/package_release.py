from __future__ import annotations
import argparse, hashlib, json, shutil, zipfile
from datetime import datetime, timezone
from pathlib import Path

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def zip_tree(source: Path, target: Path):
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(source.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(source.parent))

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--version',required=True); p.add_argument('--dist',required=True); p.add_argument('--release',required=True); a=p.parse_args()
    root=Path(a.root).resolve(); dist=Path(a.dist).resolve(); release_root=Path(a.release).resolve()/f'v{a.version}'
    if not (dist/'MigrationReportTool.exe').exists(): raise SystemExit(f'EXE not found: {dist / "MigrationReportTool.exe"}')
    product=f'MigrationReportTool-v{a.version}-Windows-x64'; package=release_root/product; archive=release_root/f'{product}.zip'
    if release_root.exists(): shutil.rmtree(release_root)
    release_root.mkdir(parents=True)
    shutil.copytree(dist,package)
    (package/'workspace').mkdir(exist_ok=True)
    (package/'workspace/README.txt').write_text('All site projects are created under this workspace directory.\n',encoding='utf-8')
    shutil.copy2(root/'README.md',package/'README.md')
    shutil.copy2(root/'docs/USER_GUIDE.md',package/'USER_GUIDE.md')
    shutil.copy2(root/'build/BUILD_INFO.json',package/'BUILD_INFO.json')
    (package/'VERSION.txt').write_text(a.version+'\n',encoding='ascii')
    files=[]
    for fp in sorted(package.rglob('*')):
        if fp.is_file(): files.append({'path':str(fp.relative_to(package)).replace('\\','/'),'sha256':sha256(fp),'size':fp.stat().st_size})
    zip_tree(package,archive)
    manifest={'product':'NARI Saudi ADMS Migration Report','version':a.version,'platform':'Windows x64','created_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),'package':archive.name,'package_sha256':sha256(archive),'files':files}
    mf=release_root/f'{product}.manifest.json'; mf.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    checks=release_root/'SHA256SUMS.txt'; checks.write_text(f"{sha256(archive)}  {archive.name}\n{sha256(dist/'MigrationReportTool.exe')}  MigrationReportTool.exe\n",encoding='ascii')
    print(f'Release directory: {release_root}'); print(f'Package: {archive}'); print(f'SHA256: {sha256(archive)}')
if __name__=='__main__': main()
