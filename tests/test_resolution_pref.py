import json
import sys
import types


def _stub_runtime_dependency(name, factory=None):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = factory() if factory else types.ModuleType(name)


def _m3u8_stub():
    mod = types.ModuleType('m3u8')
    mod.load = lambda *args, **kwargs: None
    mod.loads = lambda *args, **kwargs: None
    return mod


_stub_runtime_dependency('m3u8', _m3u8_stub)

from uav_downloader.core import config
from uav_downloader.sites import base as crawler_mod


def _variant(name, height=None, bandwidth=0, stream_info=True):
    info = None
    if stream_info:
        resolution = (1280, height) if height is not None else None
        info = types.SimpleNamespace(resolution=resolution, bandwidth=bandwidth)
    return types.SimpleNamespace(name=name, uri=f'{name}.m3u8', stream_info=info)


def test_select_variant_highest_prefers_known_height_then_bandwidth():
    variants = [
        _variant('360', 360, 900),
        _variant('1080-low-bw', 1080, 100),
        _variant('720', 720, 2000),
        _variant('1080-high-bw', 1080, 500),
    ]

    assert crawler_mod.select_variant(variants, 'highest').name == '1080-high-bw'


def test_select_variant_lowest_prefers_known_height_then_lowest_bandwidth():
    variants = [
        _variant('360-high-bw', 360, 900),
        _variant('480', 480, 100),
        _variant('360-low-bw', 360, 300),
    ]

    assert crawler_mod.select_variant(variants, 'lowest').name == '360-low-bw'


def test_select_variant_720_uses_best_at_or_below_target():
    variants = [
        _variant('360', 360, 900),
        _variant('720-low-bw', 720, 100),
        _variant('720-high-bw', 720, 500),
        _variant('1080', 1080, 2000),
    ]

    assert crawler_mod.select_variant(variants, '720').name == '720-high-bw'


def test_select_variant_480_uses_best_at_or_below_target():
    variants = [
        _variant('360', 360, 900),
        _variant('480-low-bw', 480, 100),
        _variant('480-high-bw', 480, 500),
        _variant('720', 720, 2000),
    ]

    assert crawler_mod.select_variant(variants, '480').name == '480-high-bw'


def test_select_variant_numeric_falls_forward_when_nothing_at_or_below():
    variants = [
        _variant('720-low-bw', 720, 100),
        _variant('720-high-bw', 720, 500),
        _variant('1080', 1080, 2000),
    ]

    assert crawler_mod.select_variant(variants, '480').name == '720-high-bw'


def test_select_variant_all_none_heights_keeps_bandwidth_only_behavior():
    variants = [
        _variant('low-bw', None, 100),
        _variant('high-bw', None, 900),
        _variant('mid-bw', None, 500),
    ]

    assert crawler_mod.select_variant(variants, 'highest').name == 'high-bw'
    assert crawler_mod.select_variant(variants, 'lowest').name == 'low-bw'
    assert crawler_mod.select_variant(variants, '720').name == 'high-bw'


def test_select_variant_handles_none_bandwidth_and_missing_stream_info():
    variants = [
        _variant('missing-stream', stream_info=False),
        _variant('none-bandwidth-720', 720, None),
        _variant('480', 480, 300),
    ]

    assert crawler_mod.select_variant(variants, 'highest').name == 'none-bandwidth-720'
    assert crawler_mod.select_variant(variants, 'lowest').name == '480'
    assert crawler_mod.select_variant(variants, '720').name == 'none-bandwidth-720'


def test_select_variant_single_and_empty_list():
    only = _variant('only', 720, 100)

    assert crawler_mod.select_variant([only], '480') is only
    assert crawler_mod.select_variant([], 'highest') is None
    assert crawler_mod.select_variant(None, 'highest') is None


def test_resolution_global_setters_are_isolated_and_validate(monkeypatch):
    monkeypatch.setattr(crawler_mod, '_resolution_pref', 'highest')

    crawler_mod.set_resolution_pref('720')
    assert crawler_mod.get_resolution_pref() == '720'

    crawler_mod.set_resolution_pref('bad')
    assert crawler_mod.get_resolution_pref() == '720'

    crawler_mod.set_prefer_lowest_res(True)
    assert crawler_mod.get_resolution_pref() == 'lowest'
    assert crawler_mod.get_prefer_lowest_res() is True

    crawler_mod.set_prefer_lowest_res(False)
    assert crawler_mod.get_resolution_pref() == 'highest'
    assert crawler_mod.get_prefer_lowest_res() is False


def test_config_resolution_round_trip_invalid_and_preserves_theme_lang(tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))

    config.set_theme('dark')
    config.set_ui_lang('ja')
    config.set_resolution_pref('720')

    assert config.get_theme() == 'dark'
    assert config.get_ui_lang() == 'ja'
    assert config.get_resolution_pref() == '720'

    with open(path, 'r', encoding='utf-8') as f:
        stored = json.load(f)
    assert stored['theme'] == 'dark'
    assert stored['lang'] == 'ja'
    assert stored['resolution'] == '720'

    config.set_resolution_pref('bad')

    assert config.get_theme() == 'dark'
    assert config.get_ui_lang() == 'ja'
    assert config.get_resolution_pref() == 'highest'

    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'theme': 'light', 'lang': 'en', 'resolution': 'bad'}, f)
    assert config.get_resolution_pref() == 'highest'


def test_config_subtitle_mode_round_trip_and_validation(tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))

    assert config.get_subtitle_pref() == 'none'
    config.set_subtitle_pref('all')
    assert config.get_subtitle_pref() == 'all'

    config.set_subtitle_pref('not-a-mode')
    assert config.get_subtitle_pref() == 'none'

    with open(path, 'r', encoding='utf-8') as handle:
        assert json.load(handle)['subtitle_mode'] == 'none'


def test_recognition_quality_defaults_normalizes_and_shares_ui_prefs(
        tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))

    assert config.get_recognition_quality() == 'auto'
    assert config.set_recognition_quality('recommended') == 'auto'
    assert config.set_recognition_quality('cpu') == 'auto'
    assert config.set_recognition_quality('small') == 'balanced'
    assert config.get_recognition_quality() == 'balanced'

    config.set_theme('dark')
    assert config.set_recognition_quality('fast') == 'fast'
    stored = json.loads(path.read_text(encoding='utf-8'))
    assert stored == {
        'recognition_quality': 'fast',
        'theme': 'dark',
    }

    assert config.set_recognition_quality('unknown') == 'auto'
    assert config.get_recognition_quality() == 'auto'


def test_download_concurrency_round_trip_clamps_and_preserves_preferences(
        tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))

    config.set_theme('dark')
    assert config.get_download_concurrency() == 2
    assert config.set_download_concurrency('12') == 12
    assert config.get_download_concurrency() == 12
    assert config.set_download_concurrency(0) == 1
    assert config.set_download_concurrency(999) == 32

    stored = json.loads(path.read_text(encoding='utf-8'))
    assert stored['theme'] == 'dark'
    assert stored['download_concurrency'] == 32

    path.write_text(
        json.dumps({'download_concurrency': 'not-a-number'}),
        encoding='utf-8')
    assert config.get_download_concurrency() == 2


def test_max_workers_per_video_round_trip_clamps_and_preserves_preferences(
        tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))

    config.set_theme('dark')
    assert config.get_max_workers_per_video() == config.DEFAULT_MAX_WORKERS_PER_VIDEO
    assert config.set_max_workers_per_video('3') == 3
    assert config.get_max_workers_per_video() == 3
    assert config.set_max_workers_per_video(0) == 1
    assert config.set_max_workers_per_video(999) == 16

    stored = json.loads(path.read_text(encoding='utf-8'))
    assert stored['theme'] == 'dark'
    assert stored['max_workers_per_video'] == 16

    path.write_text(
        json.dumps({'max_workers_per_video': 'not-a-number'}),
        encoding='utf-8')
    assert config.get_max_workers_per_video() == config.DEFAULT_MAX_WORKERS_PER_VIDEO
