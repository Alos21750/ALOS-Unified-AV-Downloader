import builtins
import json
import runpy
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINTS = ('main.py', 'jable_smalltool.py')
GUI_IMPORT_ROOTS = {
    'args',
    'customtkinter',
    'gui',
    'gui_modern',
    'M3U8Sites',
    'tkinter',
    'translation_settings_ui',
}


def _install_safe_modules(monkeypatch, diagnostic):
    fake_engine = types.ModuleType('subtitle_engine')
    fake_engine.run_whisper_diagnostic = diagnostic
    fake_engine.run_local_translation_diagnostic = lambda _output: None
    fake_engine.run_local_translation_worker_soak_diagnostic = (
        lambda _output: None)
    fake_engine.run_llm_translation_diagnostic = lambda _output: None
    fake_crashlog = types.ModuleType('crashlog')
    fake_crashlog.install = lambda: None
    monkeypatch.setitem(sys.modules, 'subtitle_engine', fake_engine)
    monkeypatch.setitem(sys.modules, 'crashlog', fake_crashlog)


def _reject_gui_imports(monkeypatch):
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if str(name).split('.', 1)[0] in GUI_IMPORT_ROOTS:
            raise AssertionError(
                f'GUI/heavy module imported during diagnostic: {name}')
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', guarded_import)


def _clear_other_diagnostics(monkeypatch):
    monkeypatch.delenv(
        'JABLE_LOCAL_TRANSLATION_DIAGNOSTIC_OUTPUT', raising=False)
    monkeypatch.delenv(
        'JABLE_LOCAL_TRANSLATION_SOAK_DIAGNOSTIC_OUTPUT',
        raising=False)
    monkeypatch.delenv(
        'JABLE_LLM_TRANSLATION_DIAGNOSTIC_OUTPUT', raising=False)


@pytest.mark.parametrize('filename', ENTRY_POINTS)
def test_whisper_diagnostic_runs_before_gui_import(
        filename, monkeypatch, tmp_path, capsys):
    media = tmp_path / 'private transcript secret.wav'
    media.write_bytes(b'RIFF-test')
    report = tmp_path / f'{filename}.json'
    calls = []

    def diagnostic(input_path, output_path):
        calls.append((input_path, output_path))
        Path(output_path).write_text(
            json.dumps({
                'kind': 'jable_whisper_diagnostic',
                'schema': 1,
                'cue_count': 2,
                'transcript_sha256': '0' * 64,
            }),
            encoding='utf-8')

    _install_safe_modules(monkeypatch, diagnostic)
    _reject_gui_imports(monkeypatch)
    _clear_other_diagnostics(monkeypatch)
    monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_INPUT', str(media))
    monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_OUTPUT', str(report))

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / filename), run_name='__main__')

    assert caught.value.code == 0
    assert calls == [(str(media.resolve()), str(report.resolve()))]
    payload = json.loads(report.read_text(encoding='utf-8'))
    serialized = json.dumps(payload)
    assert 'private transcript secret' not in serialized
    assert str(media) not in serialized
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('filename', ENTRY_POINTS)
@pytest.mark.parametrize(
    ('input_value', 'output_value'),
    (
        ('private-input.wav', None),
        (None, 'private-output.json'),
        ('   ', 'private-output.json'),
        ('private-input.wav', ''),
        ('same-path', 'same-path'),
        ('missing-input.wav', 'private-output.json'),
    ),
)
def test_malformed_whisper_diagnostic_fails_closed_without_gui_or_details(
        filename, input_value, output_value, monkeypatch, capsys):
    def should_not_run(*_args):
        raise AssertionError('malformed request reached diagnostic engine')

    _install_safe_modules(monkeypatch, should_not_run)
    _reject_gui_imports(monkeypatch)
    _clear_other_diagnostics(monkeypatch)
    if input_value is None:
        monkeypatch.delenv('JABLE_WHISPER_DIAGNOSTIC_INPUT', raising=False)
    else:
        monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_INPUT', input_value)
    if output_value is None:
        monkeypatch.delenv('JABLE_WHISPER_DIAGNOSTIC_OUTPUT', raising=False)
    else:
        monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_OUTPUT', output_value)

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / filename), run_name='__main__')

    assert caught.value.code == 2
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('filename', ENTRY_POINTS)
def test_whisper_diagnostic_failure_does_not_expose_exception_or_paths(
        filename, monkeypatch, tmp_path, capsys):
    media = tmp_path / 'private-media.wav'
    media.write_bytes(b'RIFF-test')
    report = tmp_path / 'private-report.json'

    def diagnostic(_input_path, _output_path):
        raise RuntimeError('secret transcript and provider-key')

    _install_safe_modules(monkeypatch, diagnostic)
    _reject_gui_imports(monkeypatch)
    _clear_other_diagnostics(monkeypatch)
    monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_INPUT', str(media))
    monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_OUTPUT', str(report))

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / filename), run_name='__main__')

    assert caught.value.code == 2
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('filename', ENTRY_POINTS)
def test_whisper_diagnostic_cannot_reuse_a_stale_report(
        filename, monkeypatch, tmp_path, capsys):
    media = tmp_path / 'private-media.wav'
    report = tmp_path / 'stale-report.json'
    media.write_bytes(b'RIFF-test')
    report.write_text('{"kind":"stale"}', encoding='utf-8')

    _install_safe_modules(monkeypatch, lambda *_args: None)
    _reject_gui_imports(monkeypatch)
    _clear_other_diagnostics(monkeypatch)
    monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_INPUT', str(media))
    monkeypatch.setenv('JABLE_WHISPER_DIAGNOSTIC_OUTPUT', str(report))

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / filename), run_name='__main__')

    assert caught.value.code == 2
    assert not report.exists()
    assert capsys.readouterr() == ('', '')


@pytest.mark.parametrize('filename', ENTRY_POINTS)
@pytest.mark.parametrize(
    ('environment_name', 'function_name'),
    (
        (
            'JABLE_LOCAL_TRANSLATION_DIAGNOSTIC_OUTPUT',
            'run_local_translation_diagnostic',
        ),
        (
            'JABLE_LOCAL_TRANSLATION_SOAK_DIAGNOSTIC_OUTPUT',
            'run_local_translation_worker_soak_diagnostic',
        ),
        (
            'JABLE_LLM_TRANSLATION_DIAGNOSTIC_OUTPUT',
            'run_llm_translation_diagnostic',
        ),
    ),
)
def test_translation_diagnostic_failure_is_silent_and_cannot_reuse_stale_report(
        filename, environment_name, function_name,
        monkeypatch, tmp_path, capsys):
    report = tmp_path / f'{function_name}.json'
    report.write_text('{"kind":"stale"}', encoding='utf-8')

    _install_safe_modules(monkeypatch, lambda *_args: None)
    fake_engine = sys.modules['subtitle_engine']

    def fail_without_writing(_output_path):
        raise RuntimeError('secret provider key and private response')

    setattr(fake_engine, function_name, fail_without_writing)
    _reject_gui_imports(monkeypatch)
    monkeypatch.delenv(
        'JABLE_WHISPER_DIAGNOSTIC_INPUT', raising=False)
    monkeypatch.delenv(
        'JABLE_WHISPER_DIAGNOSTIC_OUTPUT', raising=False)
    _clear_other_diagnostics(monkeypatch)
    monkeypatch.setenv(environment_name, str(report))

    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(ROOT / filename), run_name='__main__')

    assert caught.value.code == 2
    assert not report.exists()
    assert capsys.readouterr() == ('', '')
