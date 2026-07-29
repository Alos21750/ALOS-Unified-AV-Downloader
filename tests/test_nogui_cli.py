import argparse
import runpy
import sys
import types
from pathlib import Path

import args as cli_args
import pytest


ROOT = Path(__file__).resolve().parent.parent


def test_parser_accepts_short_and_long_output_options(tmp_path):
    parser = cli_args.get_parser()
    expected = str(tmp_path / 'downloads')

    short = parser.parse_args([
        '--nogui', '--url', 'https://jable.tv/videos/example/', '-o', expected,
    ])
    long = parser.parse_args([
        '--nogui', '--url', 'https://jable.tv/videos/example/',
        '--output', expected,
    ])

    assert short.output == expected
    assert long.output == expected


def test_parser_preserves_download_as_default_output():
    parsed = cli_args.get_parser().parse_args([
        '--nogui', '--url', 'https://jable.tv/videos/example/',
    ])

    assert parsed.output == 'download'


def test_nogui_entrypoint_imports_downloader_and_forwards_output(
        monkeypatch, tmp_path):
    destination = str(tmp_path / 'downloads')
    calls = []

    fake_args = types.ModuleType('args')
    fake_args.get_parser = lambda: types.SimpleNamespace(
        parse_args=lambda: argparse.Namespace(
            random=False,
            url='https://jable.tv/videos/example/',
            nogui=True,
            output=destination,
        ))
    fake_args.av_recommand = lambda: None

    fake_downloader = types.ModuleType('M3U8Sites')
    fake_downloader.consoles_main = (
        lambda url, output: calls.append((url, output)))

    fake_gui = types.ModuleType('gui_modern')
    fake_gui.gui_modern_main = lambda *_args: None

    fake_crashlog = types.ModuleType('crashlog')
    fake_crashlog.install = lambda: None

    monkeypatch.setitem(sys.modules, 'args', fake_args)
    monkeypatch.setitem(sys.modules, 'M3U8Sites', fake_downloader)
    monkeypatch.setitem(sys.modules, 'gui_modern', fake_gui)
    monkeypatch.setitem(sys.modules, 'crashlog', fake_crashlog)
    monkeypatch.delenv('JABLE_WHISPER_DIAGNOSTIC_INPUT', raising=False)
    monkeypatch.delenv('JABLE_WHISPER_DIAGNOSTIC_OUTPUT', raising=False)
    monkeypatch.delenv(
        'JABLE_LOCAL_TRANSLATION_DIAGNOSTIC_OUTPUT', raising=False)
    monkeypatch.delenv(
        'JABLE_LOCAL_TRANSLATION_SOAK_DIAGNOSTIC_OUTPUT',
        raising=False)
    monkeypatch.delenv(
        'JABLE_LLM_TRANSLATION_DIAGNOSTIC_OUTPUT', raising=False)

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')

    assert caught.value.code == 0

    assert calls == [
        ('https://jable.tv/videos/example/', destination),
    ]
