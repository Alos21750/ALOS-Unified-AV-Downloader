#!/usr/bin/env python
"""Generate standalone PyInstaller version-resource files."""

from pathlib import Path


VERSION = (2, 5, 38, 0)
HERE = Path(__file__).resolve().parent


def make_version(internal_name, description, original_filename):
    dotted = '.'.join(str(part) for part in VERSION)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSION!r},
    prodvers={VERSION!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'ALOS (Alos21750)'),
        StringStruct('FileDescription', '{description}'),
        StringStruct('FileVersion', '{dotted}'),
        StringStruct('InternalName', '{internal_name}'),
        StringStruct('OriginalFilename', '{original_filename}'),
        StringStruct('ProductName', 'JableTV, MissAV & SupJav Downloader'),
        StringStruct('ProductVersion', '{dotted}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


FILES = (
    ('JableTV_Modern.version', 'JableTV_Modern',
     'JableTV, MissAV & SupJav Video Downloader GUI',
     'JableTV_Modern.exe'),
    ('Jable_smalltool.version', 'Jable_smalltool',
     'JableTV, MissAV & SupJav Batch Download Tool',
     'Jable_smalltool.exe'),
)

for path_name, internal_name, description, original_filename in FILES:
    text = make_version(internal_name, description, original_filename)
    (HERE / path_name).write_text(text, encoding='utf-8')

print('Generated version files.')
