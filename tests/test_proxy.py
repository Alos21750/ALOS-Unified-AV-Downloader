import json

import pytest
import requests

from alos_downloader.core import config
from alos_downloader.sites import base as crawler


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('127.0.0.1:7890', 'http://127.0.0.1:7890'),
        ('http://localhost:8080', 'http://localhost:8080'),
        ('https://proxy.example:8443', 'https://proxy.example:8443'),
        ('socks4://127.0.0.1:1080', 'socks4://127.0.0.1:1080'),
        ('socks5h://user:pass@proxy.example:1080',
         'socks5h://user:pass@proxy.example:1080'),
        ('', ''),
    ],
)
def test_normalize_proxy_url(raw, expected):
    assert config.normalize_proxy_url(raw) == expected


@pytest.mark.parametrize(
    'raw',
    [
        'ftp://proxy.example:21',
        'http://',
        'proxy.example:not-a-port',
        'proxy.example:70000',
        'http://proxy.example/path',
        'http://proxy.example?query=1',
        'http://proxy example:8080',
    ],
)
def test_normalize_proxy_url_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        config.normalize_proxy_url(raw)


def test_proxy_preference_round_trip_preserves_other_preferences(tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))
    monkeypatch.setattr(config, '_proxy_url_cache', config._PROXY_UNSET)

    config.set_theme('dark')
    config.set_ui_lang('zh-Hans')
    saved = config.set_proxy_url('127.0.0.1:7890')

    assert saved == 'http://127.0.0.1:7890'
    assert config.get_proxy_url() == saved
    assert config.proxy_request_kwargs() == {
        'proxies': {'http': saved, 'https': saved, 'all': ''},
    }
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert raw['proxy_mode'] == 'manual'
    assert raw['theme'] == 'dark'
    assert raw['lang'] == 'zh-Hans'

    config.set_proxy_url('')

    assert config.get_proxy_url() == ''
    assert config.proxy_request_kwargs() == {
        'proxies': {'http': '', 'https': '', 'all': ''},
    }
    raw = json.loads(path.read_text(encoding='utf-8'))
    assert 'proxy_url' not in raw
    assert raw['proxy_mode'] == 'direct'
    assert raw['theme'] == 'dark'
    assert raw['lang'] == 'zh-Hans'


def test_proxy_preference_is_cached_between_requests(monkeypatch):
    calls = []
    monkeypatch.setattr(config, '_proxy_url_cache', config._PROXY_UNSET)
    monkeypatch.setattr(
        config, '_load_prefs',
        lambda: calls.append(True) or {'proxy_url': '127.0.0.1:7890'})

    assert config.get_proxy_url() == 'http://127.0.0.1:7890'
    assert config.get_proxy_url() == 'http://127.0.0.1:7890'
    assert calls == [True]


def test_direct_mode_blocks_environment_proxies_for_requests(monkeypatch):
    monkeypatch.setattr(config, '_proxy_mode_cache', 'direct')
    monkeypatch.setenv('HTTP_PROXY', 'http://environment.invalid:8080')
    monkeypatch.setenv('HTTPS_PROXY', 'http://environment.invalid:8443')
    monkeypatch.setenv('ALL_PROXY', 'socks5://environment.invalid:1080')
    monkeypatch.setenv('NO_PROXY', '')

    kwargs = config.proxy_request_kwargs()
    session = requests.Session()
    merged = session.merge_environment_settings(
        'https://example.test/', dict(kwargs['proxies']),
        stream=None, verify=None, cert=None)

    assert kwargs == {
        'proxies': {'http': '', 'https': '', 'all': ''},
    }
    assert not any(merged['proxies'].values())


def test_parse_windows_proxy_server_supports_single_and_protocol_values():
    assert config.parse_windows_proxy_server('127.0.0.1:7890') == {
        'http': 'http://127.0.0.1:7890',
        'https': 'http://127.0.0.1:7890',
    }
    assert config.parse_windows_proxy_server(
        'http=127.0.0.1:8080;https=127.0.0.1:8443') == {
            'http': 'http://127.0.0.1:8080',
            'https': 'http://127.0.0.1:8443',
        }


def test_parse_windows_proxy_server_supports_socks_fallback():
    assert config.parse_windows_proxy_server(
        'http=127.0.0.1:8080;socks=127.0.0.1:1080') == {
            'http': 'http://127.0.0.1:8080',
            'https': 'socks4://127.0.0.1:1080',
        }
    assert config.parse_windows_proxy_server(
        'socks=socks5h://127.0.0.1:1080') == {
            'http': 'socks5h://127.0.0.1:1080',
            'https': 'socks5h://127.0.0.1:1080',
        }


def test_parse_windows_proxy_server_ignores_malformed_routes():
    assert config.parse_windows_proxy_server(
        'ftp=127.0.0.1:21;http=bad port;garbage') == {}


def test_detect_windows_proxy_prefers_https_route(monkeypatch):
    monkeypatch.setattr(
        config, '_read_windows_proxy_settings',
        lambda: {
            'enabled': True,
            'server': 'http=127.0.0.1:8080;https=127.0.0.1:8443',
            'pac_url': '',
        },
        raising=False)

    assert config.detect_windows_proxy_url() == (
        'http://127.0.0.1:8443', 'detected')


def test_detect_windows_proxy_reports_pac_without_treating_it_as_proxy(
        monkeypatch):
    monkeypatch.setattr(
        config, '_read_windows_proxy_settings',
        lambda: {
            'enabled': False,
            'server': '',
            'pac_url': 'http://127.0.0.1:9000/proxy.pac',
        },
        raising=False)

    assert config.detect_windows_proxy_url() == ('', 'pac')


def test_detect_windows_proxy_ignores_stale_disabled_server(monkeypatch):
    monkeypatch.setattr(
        config, '_read_windows_proxy_settings',
        lambda: {
            'enabled': False,
            'server': '127.0.0.1:7890',
            'pac_url': '',
        })

    assert config.detect_windows_proxy_url() == ('', 'disabled')


def test_detect_windows_proxy_reports_enabled_empty_server_as_invalid(
        monkeypatch):
    monkeypatch.setattr(
        config, '_read_windows_proxy_settings',
        lambda: {
            'enabled': True,
            'server': '',
            'pac_url': '',
        })

    assert config.detect_windows_proxy_url() == ('', 'invalid')


def test_detect_windows_proxy_redacts_credentials(monkeypatch):
    monkeypatch.setattr(
        config, '_read_windows_proxy_settings',
        lambda: {
            'enabled': True,
            'server': 'http://user:secret@127.0.0.1:7890',
            'pac_url': '',
        })

    display_url, status = config.detect_windows_proxy_url()

    assert status == 'detected'
    assert display_url == 'http://127.0.0.1:7890'
    assert 'user' not in display_url
    assert 'secret' not in display_url


@pytest.mark.parametrize(
    ('prefs', 'expected'),
    [
        ({'proxy_url': '127.0.0.1:7890'}, 'manual'),
        ({'proxy_url': ''}, 'direct'),
        ({}, 'direct'),
        ({'proxy_mode': 'system'}, 'system'),
    ],
)
def test_proxy_mode_migrates_legacy_preferences_in_memory(
        prefs, expected, monkeypatch):
    monkeypatch.setattr(config, '_proxy_mode_cache', config._PROXY_UNSET)
    monkeypatch.setattr(config, '_load_prefs', lambda: dict(prefs))

    assert config.get_proxy_mode() == expected


def test_set_proxy_mode_preserves_manual_url_and_other_preferences(
        tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    path.write_text(
        json.dumps({'proxy_url': 'http://user:secret@127.0.0.1:7890',
                    'theme': 'dark'}),
        encoding='utf-8')
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))
    monkeypatch.setattr(config, '_proxy_mode_cache', config._PROXY_UNSET)
    monkeypatch.setattr(config, '_system_proxy_cache', config._PROXY_UNSET)

    assert config.set_proxy_mode('system') == 'system'

    raw = json.loads(path.read_text(encoding='utf-8'))
    assert raw == {
        'proxy_mode': 'system',
        'proxy_url': 'http://user:secret@127.0.0.1:7890',
        'theme': 'dark',
    }
    assert config.get_proxy_mode() == 'system'


def test_set_proxy_mode_rejects_invalid_value():
    with pytest.raises(ValueError):
        config.set_proxy_mode('automatic')


def test_system_mode_uses_cached_detection_until_refresh(monkeypatch):
    states = [
        ({'http': 'http://first:8080',
          'https': 'http://first:8080'}, 'http://first:8080', 'detected'),
        ({'http': 'http://second:8080',
          'https': 'http://second:8080'}, 'http://second:8080', 'detected'),
    ]
    calls = []

    def detect():
        index = min(len(calls), len(states) - 1)
        calls.append(index)
        return states[index]

    monkeypatch.setattr(config, '_proxy_mode_cache', 'system')
    monkeypatch.setattr(config, '_system_proxy_cache', config._PROXY_UNSET)
    monkeypatch.setattr(config, '_detect_windows_proxy_state', detect)

    expected_first = {
        'proxies': {
            'http': 'http://first:8080',
            'https': 'http://first:8080',
            'all': '',
        },
    }
    assert config.proxy_request_kwargs() == expected_first
    assert config.proxy_request_kwargs() == expected_first
    assert calls == [0]

    assert config.refresh_system_proxy() == (
        'http://second:8080', 'detected')
    assert config.proxy_request_kwargs() == {
        'proxies': {
            'http': 'http://second:8080',
            'https': 'http://second:8080',
            'all': '',
        },
    }
    assert calls == [0, 1]


def test_system_mode_blocks_environment_fallback_for_missing_routes(
        monkeypatch):
    monkeypatch.setattr(config, '_proxy_mode_cache', 'system')
    monkeypatch.setattr(
        config, '_system_proxy_cache',
        ({'http': 'http://manual.test:8080'}, 'detected'))

    assert config.proxy_request_kwargs() == {
        'proxies': {
            'http': 'http://manual.test:8080',
            'https': '',
            'all': '',
        },
    }


def test_system_detection_does_not_persist_endpoint(tmp_path, monkeypatch):
    path = tmp_path / 'ui_prefs.json'
    path.write_text(
        json.dumps({'proxy_mode': 'system', 'theme': 'dark'}),
        encoding='utf-8')
    monkeypatch.setattr(config, '_ui_prefs_path', lambda: str(path))
    monkeypatch.setattr(config, '_proxy_mode_cache', 'system')
    monkeypatch.setattr(config, '_system_proxy_cache', config._PROXY_UNSET)
    monkeypatch.setattr(
        config, '_read_windows_proxy_settings',
        lambda: {
            'enabled': True,
            'server': 'http://user:secret@127.0.0.1:7890',
            'pac_url': '',
        })

    assert config.proxy_request_kwargs() == {
        'proxies': {
            'http': 'http://user:secret@127.0.0.1:7890',
            'https': 'http://user:secret@127.0.0.1:7890',
            'all': '',
        },
    }
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'proxy_mode': 'system',
        'theme': 'dark',
    }


class _FakeResponse:
    status_code = 200
    headers = {}
    content = b'ok'
    text = 'ok'

    def __init__(self, url='https://example.test/video'):
        self.url = url


class _RecordingSession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _FakeResponse(url)


def test_page_fetch_passes_proxy_to_scraper(monkeypatch):
    session = _RecordingSession()
    proxy = {'http': 'http://127.0.0.1:7890',
             'https': 'http://127.0.0.1:7890'}
    monkeypatch.setattr(config, 'MIRRORS', {'test': ['example.test']})
    monkeypatch.setattr(config, 'get_cf_override', lambda _host: None)
    monkeypatch.setattr(config, 'proxy_request_kwargs',
                        lambda: {'proxies': dict(proxy)})

    response, host, reason = crawler.fetch_with_mirrors(
        session, 'https://example.test/video', 'test', lambda _response: True)

    assert response.status_code == 200
    assert host == 'example.test'
    assert reason == 'ok'
    assert session.calls[0][1]['proxies'] == proxy


def test_media_fetch_passes_proxy_to_curl_cffi(monkeypatch):
    session = _RecordingSession()
    proxy = {'http': 'socks5h://127.0.0.1:1080',
             'https': 'socks5h://127.0.0.1:1080'}
    monkeypatch.setattr(crawler, '_use_cffi', True)
    monkeypatch.setattr(crawler, '_get_cffi_session', lambda: session)
    monkeypatch.setattr(config, 'proxy_request_kwargs',
                        lambda: {'proxies': dict(proxy)})

    crawler._http_get('https://cdn.example/video.m3u8',
                      {'User-Agent': 'ignored-by-cffi', 'Referer': 'https://example.test'})

    assert session.calls[0][1]['proxies'] == proxy
    assert session.calls[0][1]['headers'] == {'Referer': 'https://example.test'}


def test_direct_mode_passes_explicit_empty_routes_to_curl_cffi(monkeypatch):
    session = _RecordingSession()
    monkeypatch.setattr(crawler, '_use_cffi', True)
    monkeypatch.setattr(crawler, '_get_cffi_session', lambda: session)
    monkeypatch.setattr(config, '_proxy_mode_cache', 'direct')

    crawler._http_get(
        'https://cdn.example/video.m3u8',
        {'User-Agent': 'ignored-by-cffi', 'Referer': 'https://example.test'})

    assert session.calls[0][1]['proxies'] == {
        'http': '', 'https': '', 'all': '',
    }
