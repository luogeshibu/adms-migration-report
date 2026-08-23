from pathlib import Path
import argparse

def parts(v: str):
    raw = [int(x) for x in v.split('.')[:4]]
    return tuple((raw + [0,0,0,0])[:4])

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--version', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    ver = parts(a.version)
    text = '# UTF-8\n' + ("VSVersionInfo(\n  ffi=FixedFileInfo(\n    filevers=%r, prodvers=%r, mask=0x3f, flags=0x0,\n    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)\n  ),\n  kids=[\n    StringFileInfo([StringTable(\n      '040904B0',\n      [StringStruct('CompanyName', 'NARI'),\n       StringStruct('FileDescription', 'NARI Saudi ADMS Migration Report'),\n       StringStruct('FileVersion', '%s'),\n       StringStruct('InternalName', 'MigrationReportTool'),\n       StringStruct('LegalCopyright', 'Copyright (c) NARI'),\n       StringStruct('OriginalFilename', 'MigrationReportTool.exe'),\n       StringStruct('ProductName', 'NARI Saudi ADMS Migration Report'),\n       StringStruct('ProductVersion', '%s')])\n    ]),\n    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n  ]\n)\n" % (ver, ver, a.version, a.version))
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print(out)

if __name__ == '__main__':
    main()
