import json
import shutil

from uav_downloader.core import config
from uav_downloader.subtitles import engine as subtitles


def _srt(text):
    return f'1\n00:00:00,000 --> 00:00:01,000\n{text}\n'


def test_legacy_jable_provenance_is_read_as_managed_uav_state(tmp_path):
    video = tmp_path / 'movie.mp4'
    canonical = tmp_path / 'movie.uav-subtitles.json'
    legacy = tmp_path / 'movie.jable-subtitles.json'
    legacy.write_text(
        json.dumps({
            'schema': 1,
            'kind': 'jable_subtitle_provenance',
            'tracks': {
                'ja': {
                    'generator': 'jable',
                    'srt_sha256': '0' * 64,
                },
            },
        }),
        encoding='utf-8',
    )

    loaded = subtitles._load_subtitle_provenance(
        subtitles._subtitle_provenance_path(str(video)))

    assert loaded['kind'] == 'uav_subtitle_provenance'
    assert loaded['tracks']['ja']['generator'] == 'jable'
    assert legacy.is_file()
    assert not canonical.exists()


def test_managed_asr_is_reused_until_downloaded_media_changes(
        monkeypatch, tmp_path):
    video = tmp_path / 'movie.mp4'
    video.write_bytes(b'first video')
    calls = []
    monkeypatch.setattr(
        config, 'get_recognition_quality', lambda: 'quality')
    monkeypatch.setattr(
        subtitles, '_prepare_runtime',
        lambda *_args: ('whisper.exe', 'model.bin', 'vad.bin'))
    monkeypatch.setattr(
        subtitles, '_extract_audio',
        lambda _source, wav, _log, _cancel: open(wav, 'wb').close())

    def fake_whisper(
            _exe, _model, _vad, _wav, output, _log, _cancel,
            progress_callback=None):
        calls.append(len(calls) + 1)
        result = output + '.srt'
        subtitles._atomic_write_text(
            result, _srt(f'generated pass {calls[-1]}'))
        return result

    monkeypatch.setattr(subtitles, '_run_whisper', fake_whisper)

    first = subtitles.generate_subtitles(str(video), 'ja')
    second = subtitles.generate_subtitles(str(video), 'ja')
    video.write_bytes(b'replaced video with different content and size')
    third = subtitles.generate_subtitles(str(video), 'ja')

    assert calls == [1, 2]
    assert first.generated == (str(tmp_path / 'movie.ja.srt'),)
    assert second.generated == ()
    assert third.generated == (str(tmp_path / 'movie.ja.srt'),)
    assert (tmp_path / 'movie.ja.srt').read_text(
        encoding='utf-8') == _srt('generated pass 2')


def test_media_identity_survives_a_copy_but_detects_replacement(tmp_path):
    source = tmp_path / 'source.mp4'
    copied = tmp_path / 'copied.mp4'
    source.write_bytes((b'video-content-' * 20_000) + b'end')
    shutil.copyfile(source, copied)

    assert subtitles._media_identity(str(source)) == subtitles._media_identity(
        str(copied))

    copied.write_bytes((b'different-data' * 20_000) + b'end')
    assert subtitles._media_identity(str(source)) != subtitles._media_identity(
        str(copied))


def test_manual_derived_subtitle_does_not_load_translation_settings(
        monkeypatch, tmp_path):
    video = tmp_path / 'movie.mp4'
    english = tmp_path / 'movie.en.srt'
    video.write_bytes(b'video')
    english.write_text(_srt('User-authored English'), encoding='utf-8')
    monkeypatch.setattr(
        subtitles, '_selected_translation_profile',
        lambda: (_ for _ in ()).throw(
            AssertionError('manual SRT must not load provider settings')))

    result = subtitles.generate_subtitles(str(video), 'en')

    assert result.files == (str(english),)
    assert result.generated == ()


def test_utf16_user_subtitle_is_preserved_without_starting_asr(
        monkeypatch, tmp_path):
    video = tmp_path / 'movie.mp4'
    japanese = tmp_path / 'movie.ja.srt'
    video.write_bytes(b'video')
    japanese.write_text(_srt('User-authored Japanese'), encoding='utf-16')
    original = japanese.read_bytes()
    monkeypatch.setattr(
        subtitles, '_prepare_runtime',
        lambda *_args: (_ for _ in ()).throw(
            AssertionError('manual UTF-16 SRT must not start ASR')))

    result = subtitles.generate_subtitles(str(video), 'ja')

    assert result.files == (str(japanese),)
    assert result.generated == ()
    assert japanese.read_bytes() == original


def test_corrupt_provenance_never_claims_or_overwrites_existing_srt(
        monkeypatch, tmp_path):
    video = tmp_path / 'movie.mp4'
    japanese = tmp_path / 'movie.ja.srt'
    manifest = tmp_path / 'movie.uav-subtitles.json'
    video.write_bytes(b'video')
    japanese.write_text(_srt('User subtitle'), encoding='utf-8')
    manifest.write_text('{"tracks":', encoding='utf-8')
    monkeypatch.setattr(
        subtitles, '_prepare_runtime',
        lambda *_args: (_ for _ in ()).throw(
            AssertionError('corrupt metadata must fail open')))

    result = subtitles.generate_subtitles(str(video), 'ja')

    assert result.files == (str(japanese),)
    assert result.generated == ()
    assert japanese.read_text(encoding='utf-8') == _srt('User subtitle')


def test_no_speech_removes_only_an_obsolete_app_owned_sidecar(
        monkeypatch, tmp_path):
    video = tmp_path / 'movie.mp4'
    japanese = tmp_path / 'movie.ja.srt'
    video.write_bytes(b'first video')
    monkeypatch.setattr(
        config, 'get_recognition_quality', lambda: 'quality')
    monkeypatch.setattr(
        subtitles, '_prepare_runtime',
        lambda *_args: ('whisper.exe', 'model.bin', 'vad.bin'))
    monkeypatch.setattr(
        subtitles, '_extract_audio',
        lambda _source, wav, _log, _cancel: open(wav, 'wb').close())
    pass_count = {'value': 0}

    def fake_whisper(
            _exe, _model, _vad, _wav, output, _log, _cancel,
            progress_callback=None):
        pass_count['value'] += 1
        if pass_count['value'] == 2:
            return None
        result = output + '.srt'
        subtitles._atomic_write_text(result, _srt('Generated subtitle'))
        return result

    monkeypatch.setattr(subtitles, '_run_whisper', fake_whisper)
    subtitles.generate_subtitles(str(video), 'ja')
    assert japanese.exists()

    video.write_bytes(b'replacement contains no speech and is longer')
    result = subtitles.generate_subtitles(str(video), 'ja')

    assert result.no_speech is True
    assert result.files == ()
    assert not japanese.exists()
