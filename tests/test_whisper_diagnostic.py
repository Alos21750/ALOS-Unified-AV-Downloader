import wave

from alos_downloader.core import config
from alos_downloader.subtitles import engine as subtitles


def _write_pcm16_wav(path, seconds):
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b'\0\0' * int(16_000 * seconds))


def test_whisper_diagnostic_records_timing_without_transcript_or_paths(
        monkeypatch, tmp_path):
    media = tmp_path / 'private-title-secret.mp4'
    report = tmp_path / 'diagnostic.json'
    media.write_bytes(b'video')
    monkeypatch.setattr(
        config, 'get_recognition_quality', lambda: 'quality')
    profile = subtitles.recognition_profile()
    monkeypatch.setattr(
        subtitles, '_prepare_runtime',
        lambda *_args: (
            'whisper.exe', profile.model_name, 'vad.bin'))

    def fake_extract(_source, wav, _log, _cancel):
        _write_pcm16_wav(wav, 8.0)

    def fake_whisper(
            _exe, _model, _vad, _wav, output, _log, _cancel,
            progress_callback=None):
        del progress_callback
        path = output + '.srt'
        subtitles._atomic_write_text(
            path,
            '1\n00:00:01,250 --> 00:00:02,500\n'
            'PRIVATE TRANSCRIPT SECRET\n\n'
            '2\n00:00:06,000 --> 00:00:07,125\n'
            'SECOND SECRET\n',
        )
        return path

    monkeypatch.setattr(subtitles, '_extract_audio', fake_extract)
    monkeypatch.setattr(subtitles, '_run_whisper', fake_whisper)

    payload = subtitles.run_whisper_diagnostic(
        str(media), str(report))

    serialized = report.read_text(encoding='utf-8')
    assert payload['cue_count'] == 2
    assert payload['first_cue_start_ms'] == 1250
    assert payload['last_cue_end_ms'] == 7125
    assert payload['timing_monotonic'] is True
    assert payload['no_speech'] is False
    assert payload['audio_duration_ms'] == 8000
    assert payload['actual_engine'] == 'whisper'
    assert payload['actual_runtime_version'] == subtitles.WHISPER_VERSION
    assert payload['actual_model_sha256'] == profile.model_sha256
    assert payload['fallback_used'] is False
    assert 'PRIVATE TRANSCRIPT' not in serialized
    assert 'SECOND SECRET' not in serialized
    assert 'private-title-secret' not in serialized
    assert str(media) not in serialized


def test_whisper_diagnostic_reports_vad_zero_as_no_speech(
        monkeypatch, tmp_path):
    media = tmp_path / 'silence.wav'
    report = tmp_path / 'diagnostic.json'
    _write_pcm16_wav(media, 2.0)
    monkeypatch.setattr(
        config, 'get_recognition_quality', lambda: 'quality')
    profile = subtitles.recognition_profile()
    monkeypatch.setattr(
        subtitles, '_prepare_runtime',
        lambda *_args: (
            'whisper.exe', profile.model_name, 'vad.bin'))
    monkeypatch.setattr(
        subtitles, '_extract_audio',
        lambda _source, wav, _log, _cancel: _write_pcm16_wav(
            wav, 2.0))
    monkeypatch.setattr(
        subtitles, '_run_whisper',
        lambda *_args, **_kwargs: None)

    payload = subtitles.run_whisper_diagnostic(
        str(media), str(report))

    assert payload['no_speech'] is True
    assert payload['cue_count'] == 0
    assert payload['first_cue_start_ms'] is None
    assert payload['last_cue_end_ms'] is None
    assert payload['transcript_characters'] == 0
    assert payload['actual_engine'] == 'vad'
    assert payload['actual_model_sha256'] is None
    assert payload['fallback_used'] is False
