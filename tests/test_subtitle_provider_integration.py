from types import SimpleNamespace

import pytest

from uav_downloader.core import config
from uav_downloader.subtitles import llm as llm_translation
from uav_downloader.subtitles import engine as subtitles
from uav_downloader.subtitles.settings import TranslationSettings


def _profile(
        provider="openai",
        model="test-model",
        base_url="https://api.example.test/v1",
        api_key="test-secret"):
    return TranslationSettings(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        api_key_source="protected" if api_key else "none",
    )


def _sample_srt(text):
    return f"1\n00:00:00,000 --> 00:00:01,500\n{text}\n"


def test_api_translates_only_unknown_cues_and_never_prepares_local_pack(
        monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        subtitles,
        "_prepare_translation_runtime",
        lambda *_args: pytest.fail("API translation must not load local models"),
    )
    monkeypatch.setattr(
        subtitles, "_to_taiwan_chinese", lambda value: value)
    calls = []

    def fake_translate(texts, settings, **kwargs):
        calls.append((list(texts), settings, kwargs))
        return SimpleNamespace(translations=("這是 API 直接翻譯。",))

    monkeypatch.setattr(llm_translation, "translate_cues", fake_translate)
    with subtitles._translation_profile_scope(_profile()):
        result = subtitles.translate_cues(
            ["やめて", "人工詞庫にない長い文章", "人工詞庫にない長い文章"],
            "ja",
            "zh-TW",
            "translate_zh",
        )

    assert result == [
        "停下來。",
        "這是 API 直接翻譯。",
        "這是 API 直接翻譯。",
    ]
    assert len(calls) == 1
    texts, runtime_settings, kwargs = calls[0]
    assert texts == ["人工詞庫にない長い文章"]
    assert runtime_settings.provider == "openai"
    assert kwargs["source_language"] == "Japanese"
    assert kwargs["target_language"] == "Taiwan Traditional Chinese"
    assert kwargs["api_key"] == "test-secret"


def test_api_cache_identity_uses_provider_model_endpoint_but_not_key():
    original = _profile(api_key="first-key")
    same_identity = _profile(api_key="second-key")
    different_model = _profile(model="other-model")
    different_endpoint = _profile(
        base_url="https://second.example.test/v1")
    different_provider = _profile(
        provider="anthropic",
        base_url="https://api.example.test/v1",
    )

    assert subtitles._translation_api_memory_version(original) == (
        subtitles._translation_api_memory_version(same_identity))
    assert subtitles._translation_api_memory_version(original) != (
        subtitles._translation_api_memory_version(different_model))
    assert subtitles._translation_api_memory_version(original) != (
        subtitles._translation_api_memory_version(different_endpoint))
    assert subtitles._translation_api_memory_version(original) != (
        subtitles._translation_api_memory_version(different_provider))
    assert "first-key" not in subtitles._translation_api_memory_version(
        original)


def test_api_translation_cache_hit_skips_network_and_local_runtime(
        monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        subtitles,
        "_prepare_translation_runtime",
        lambda *_args: pytest.fail("API translation must not load local models"),
    )
    calls = []

    def fake_translate(_texts, _settings, **_kwargs):
        calls.append(True)
        return SimpleNamespace(translations=("Cached API output.",))

    monkeypatch.setattr(llm_translation, "translate_cues", fake_translate)
    profile = _profile()
    with subtitles._translation_profile_scope(profile):
        first = subtitles.translate_cues(
            ["人工詞庫にないキャッシュ文章"],
            "ja",
            "en",
            "translate_en",
        )
    with subtitles._translation_profile_scope(
            _profile(api_key="rotated-key")):
        second = subtitles.translate_cues(
            ["人工詞庫にないキャッシュ文章"],
            "ja",
            "en",
            "translate_en",
        )

    assert first == second == ["Cached API output."]
    assert calls == [True]


def test_api_errors_and_cancellation_are_safely_mapped(
        monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    profile = _profile(api_key="must-never-leak")

    def fail_with_secret(*_args, **_kwargs):
        raise llm_translation.LlmTranslationError(
            "provider rejected must-never-leak")

    monkeypatch.setattr(llm_translation, "translate_cues", fail_with_secret)
    with subtitles._translation_profile_scope(profile):
        with pytest.raises(subtitles.SubtitleError) as caught:
            subtitles.translate_cues(
                ["人工詞庫にないエラー文章"],
                "ja",
                "en",
                "translate_en",
            )
    assert "must-never-leak" not in str(caught.value)
    assert "[redacted]" in str(caught.value)
    assert caught.value.__cause__ is None

    def cancel(*_args, **_kwargs):
        raise llm_translation.LlmTranslationCancelled("cancelled")

    monkeypatch.setattr(llm_translation, "translate_cues", cancel)
    with subtitles._translation_profile_scope(profile):
        with pytest.raises(subtitles.SubtitleCancelled):
            subtitles.translate_cues(
                ["別の人工詞庫にない文章"],
                "ja",
                "en",
                "translate_en",
            )


def test_generate_api_chinese_uses_japanese_not_existing_english(
        monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "cache"))
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    japanese = tmp_path / "movie.ja.srt"
    english = tmp_path / "movie.en.srt"
    japanese.write_text(
        _sample_srt("人工詞庫にない日本語文章"), encoding="utf-8")
    english.write_text(
        _sample_srt("Existing English must not be used."), encoding="utf-8")

    monkeypatch.setattr(
        subtitles, "_selected_translation_profile", lambda: _profile())
    monkeypatch.setattr(
        subtitles,
        "_prepare_runtime",
        lambda *_args: pytest.fail("existing Japanese must skip Whisper"),
    )
    monkeypatch.setattr(
        subtitles,
        "_prepare_translation_runtime",
        lambda *_args: pytest.fail("API translation must not load local models"),
    )
    monkeypatch.setattr(
        subtitles, "_to_taiwan_chinese", lambda value: value)
    requests = []

    def fake_translate(texts, _settings, **kwargs):
        requests.append((list(texts), kwargs["target_language"]))
        return SimpleNamespace(translations=("API 繁中結果。",))

    monkeypatch.setattr(llm_translation, "translate_cues", fake_translate)
    result = subtitles.generate_subtitles(str(video), "zh")

    assert requests == [
        (["人工詞庫にない日本語文章"], "Taiwan Traditional Chinese")]
    assert [path.rsplit(".", 2)[-2:] for path in result.files] == [
        ["zh-TW", "srt"]]
    assert "API 繁中結果。" in (
        tmp_path / "movie.zh-TW.srt").read_text(encoding="utf-8")


def test_none_and_japanese_modes_never_load_translation_provider_or_pack(
        monkeypatch, tmp_path):
    monkeypatch.setattr(
        config, "get_recognition_quality", lambda: "quality")
    monkeypatch.setattr(
        subtitles,
        "_selected_translation_profile",
        lambda: pytest.fail("non-translation modes must not load provider"),
    )
    monkeypatch.setattr(
        subtitles,
        "_prepare_translation_runtime",
        lambda *_args: pytest.fail("non-translation modes must not load pack"),
    )
    assert subtitles.generate_subtitles(
        str(tmp_path / "missing.mp4"), "none") == subtitles.SubtitleResult(
            (), ())

    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        subtitles,
        "_prepare_runtime",
        lambda *_args: ("whisper.exe", "model.bin", "vad.bin"),
    )
    monkeypatch.setattr(
        subtitles,
        "_extract_audio",
        lambda _video, wav, _log, _cancel: open(wav, "wb").close(),
    )

    def fake_whisper(
            _exe, _model, _vad, _wav, output_base, _log, _cancel,
            progress_callback=None):
        output = output_base + ".srt"
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(_sample_srt("日本語"))
        return output

    monkeypatch.setattr(subtitles, "_run_whisper", fake_whisper)
    result = subtitles.generate_subtitles(str(video), "ja")
    assert [path.rsplit(".", 2)[-2:] for path in result.files] == [
        ["ja", "srt"]]
