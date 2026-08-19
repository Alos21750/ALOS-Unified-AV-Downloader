from types import SimpleNamespace

import pytest

from alos_downloader.subtitles import engine as subtitles


def test_model_download_fails_before_network_when_disk_is_too_small(
        monkeypatch, tmp_path):
    destination = tmp_path / 'models' / 'large-model.bin'
    monkeypatch.setattr(
        subtitles, '_is_verified', lambda *_args: False)
    monkeypatch.setattr(
        subtitles.shutil, 'disk_usage',
        lambda _path: SimpleNamespace(
            total=1_000_000, used=900_000, free=100_000))
    monkeypatch.setattr(
        subtitles, '_session',
        lambda: pytest.fail('network must not start without enough space'))

    with pytest.raises(
            subtitles.SubtitleError, match='free disk space'):
        subtitles._download_verified(
            'https://example.invalid/model.bin',
            str(destination),
            574_041_195,
            '0' * 64,
            'model',
            None,
            None,
        )


def test_recognition_profile_scope_pins_a_queued_job(monkeypatch):
    selected = subtitles.recognition_profile('balanced')
    monkeypatch.setattr(
        subtitles.config, 'get_recognition_quality', lambda: 'fast')

    assert subtitles.recognition_profile().key == 'fast'
    with subtitles._recognition_profile_scope(selected):
        assert subtitles.recognition_profile() is selected
    assert subtitles.recognition_profile().key == 'fast'
