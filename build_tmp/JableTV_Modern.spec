# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = [
    'cloudscraper', 'Crypto.Cipher.AES', 'm3u8',
    'imageio_ffmpeg', 'imageio_ffmpeg.binaries',
    'customtkinter', 'curl_cffi', '_cffi_backend',
    'crashlog', 'certifi', 'faulthandler', 'updater', 'ssl_util',
    'subtitle_engine', 'subtitle_domain', 'llm_translation',
    'translation_settings', 'translation_settings_ui',
    'ctranslate2', 'ctranslate2._ext',
    'numpy._core._exceptions',
    'sentencepiece', 'sentencepiece._sentencepiece', 'opencc',
    'socks', 'urllib3.contrib.socks',
]

# Collect package data (cloudscraper browser profiles, certifi certs, customtkinter themes)
for pkg in [
        'cloudscraper', 'certifi', 'customtkinter', 'curl_cffi',
        'imageio_ffmpeg', 'ctranslate2', 'sentencepiece', 'opencc']:
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# The Windows CTranslate2 wheel ships an optional cuDNN DLL even though this
# application is CPU-only.  ctranslate2 imports every package DLL on Windows,
# so remove that unused proprietary GPU runtime from both possible TOCs.
datas = [
    entry for entry in datas
    if Path(str(entry[0])).name.lower() != 'cudnn64_9.dll'
]
binaries = [
    entry for entry in binaries
    if Path(str(entry[0])).name.lower() != 'cudnn64_9.dll'
]
datas += copy_metadata('numpy')
datas += copy_metadata('PyYAML')

datas += [
    ('..\\LICENSE', '.'),
    ('..\\THIRD_PARTY_NOTICES.md', '.'),
    (
        '..\\third_party_licenses\\FuguMT-CC-BY-SA-4.0-NOTICE.txt',
        'third_party_licenses',
    ),
    (
        '..\\third_party_licenses\\Intel-Simplified-Software-License.txt',
        'third_party_licenses',
    ),
]


a = Analysis(
    ['..\\main.py'],
    pathex=['..'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='JableTV_Modern',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Do not allow a runner-local UPX installation to change the release
    # binary or increase the antivirus heuristic surface.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='JableTV_Modern.version',
)
