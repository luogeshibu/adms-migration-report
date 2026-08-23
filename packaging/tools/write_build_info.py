from __future__ import annotations
import argparse, json, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

def git_value(root: Path, *args):
    try:
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ''

def main():
    p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--output',required=True); p.add_argument('--version',required=True); a=p.parse_args()
    root=Path(a.root).resolve(); out=Path(a.output)
    import PySide6, PyInstaller
    data={
      'product':'NARI Saudi ADMS Migration Report','version':a.version,'platform':'Windows x64',
      'built_at_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'python':platform.python_version(),'pyside6':PySide6.__version__,'pyinstaller':PyInstaller.__version__,
      'git_commit':git_value(root,'rev-parse','HEAD'),
      'git_branch':git_value(root,'rev-parse','--abbrev-ref','HEAD'),
    }
    status=git_value(root,'status','--porcelain'); data['git_dirty']=bool(status)
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(data,indent=2),encoding='utf-8'); print(out)
if __name__=='__main__': main()
