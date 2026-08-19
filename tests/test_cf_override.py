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
    return mod


_stub_runtime_dependency('m3u8', _m3u8_stub)

from uav_downloader.core import config
from uav_downloader.sites.base import fetch_with_mirrors


def _reset_cf():
    with config._cf_lock:
        config.CF_OVERRIDES = {}


def test_parse_cf_clearance_accepts_cookie_or_token():
    assert config._parse_cf_clearance('abc') == 'abc'
    assert config._parse_cf_clearance('cf_clearance=abc') == 'abc'
    assert config._parse_cf_clearance('cf_clearance=abc; other=1') == 'abc'
    assert config._parse_cf_clearance('a=1; cf_clearance=xyz; b=2') == 'xyz'
    assert config._parse_cf_clearance('ab\r\ncd') == 'abcd'
    assert config._parse_cf_clearance('"abc"') == 'abc'
    assert config._parse_cf_clearance('') == ''
    assert config._parse_cf_clearance(None) == ''


def test_set_get_clear_round_trip_persists(tmp_path, monkeypatch):
    path = tmp_path / 'cf_overrides.json'
    monkeypatch.setattr(config, '_cf_store_path', lambda: str(path))
    _reset_cf()

    config.set_cf_override('supjav.com', 'XYZ', 'UA/1')

    assert config.get_cf_override('supjav.com') == {'cookie': 'XYZ', 'ua': 'UA/1'}
    assert path.exists()

    config.clear_cf_override('supjav.com')

    assert config.get_cf_override('supjav.com') is None


def test_host_normalization(tmp_path, monkeypatch):
    path = tmp_path / 'cf_overrides.json'
    monkeypatch.setattr(config, '_cf_store_path', lambda: str(path))
    _reset_cf()

    config.set_cf_override('SupJav.Com:443', 'A', 'B')

    assert config.get_cf_override('supjav.com') == {'cookie': 'A', 'ua': 'B'}


def test_load_cf_overrides_tolerates_missing_and_corrupt(tmp_path, monkeypatch):
    path = tmp_path / 'cf_overrides.json'
    monkeypatch.setattr(config, '_cf_store_path', lambda: str(path))
    _reset_cf()

    with config._cf_lock:
        config.CF_OVERRIDES = {'supjav.com': {'cookie': 'old'}}

    config.load_cf_overrides()

    assert config.cf_override_hosts() == []

    path.write_bytes(b'{not json')
    with config._cf_lock:
        config.CF_OVERRIDES = {'supjav.com': {'cookie': 'old'}}

    config.load_cf_overrides()

    assert config.cf_override_hosts() == []
    assert path.with_name(path.name + '.bak').exists()


class Resp:
    def __init__(self, url, status_code=200, content=b'<html>ok</html>'):
        self.url = url
        self.status_code = status_code
        self.content = content
        self.headers = {}


class FakeScraper:
    def __init__(self, status_codes=None):
        self.status_codes = list(status_codes or [200])
        self.calls = []

    def get(self, url, timeout=None, headers=None, cookies=None, proxies=None):
        self.calls.append((dict(headers or {}), cookies))
        status = self.status_codes.pop(0) if self.status_codes else 200
        return Resp(url, status_code=status)


def test_fetch_with_mirrors_sends_override_cookie_and_ua(tmp_path, monkeypatch):
    path = tmp_path / 'cf_overrides.json'
    monkeypatch.setattr(config, '_cf_store_path', lambda: str(path))
    monkeypatch.setattr(config, 'MIRRORS', {'t': ['supjav.com']})
    _reset_cf()
    config.set_cf_override('supjav.com', 'XYZ', 'UA/1')
    scraper = FakeScraper()

    resp, host, reason = fetch_with_mirrors(
        scraper,
        'https://supjav.com/1.html',
        't',
        validate=lambda r: True,
        headers_factory=lambda h: {'Referer': 'https://supjav.com/'},
    )

    assert resp is not None
    assert host == 'supjav.com'
    assert reason == 'ok'
    headers, cookies = scraper.calls[0]
    assert cookies == {'cf_clearance': 'XYZ'}
    assert headers['User-Agent'] == 'UA/1'
    assert headers['Referer'] == 'https://supjav.com/'


def test_fetch_with_mirrors_without_override_does_not_inject_cookie_or_ua(tmp_path, monkeypatch):
    path = tmp_path / 'cf_overrides.json'
    monkeypatch.setattr(config, '_cf_store_path', lambda: str(path))
    monkeypatch.setattr(config, 'MIRRORS', {'t': ['supjav.com']})
    _reset_cf()
    scraper = FakeScraper()

    resp, host, reason = fetch_with_mirrors(
        scraper,
        'https://supjav.com/1.html',
        't',
        validate=lambda r: True,
        headers_factory=lambda h: {'Referer': 'https://supjav.com/'},
    )

    assert resp is not None
    assert host == 'supjav.com'
    assert reason == 'ok'
    assert scraper.calls == [({'Referer': 'https://supjav.com/'}, None)]


def test_fetch_with_mirrors_falls_back_to_plain_after_blocked_cookie_trial(tmp_path, monkeypatch):
    path = tmp_path / 'cf_overrides.json'
    monkeypatch.setattr(config, '_cf_store_path', lambda: str(path))
    monkeypatch.setattr(config, 'MIRRORS', {'t': ['supjav.com']})
    _reset_cf()
    config.set_cf_override('supjav.com', 'XYZ', 'UA/1')

    scraper = FakeScraper([403, 200])
    resp, host, reason = fetch_with_mirrors(
        scraper,
        'https://supjav.com/1.html',
        't',
        validate=lambda r: True,
    )

    assert resp is not None
    assert host == 'supjav.com'
    assert reason == 'ok'
    assert len(scraper.calls) == 2
    assert scraper.calls[0][1] == {'cf_clearance': 'XYZ'}
    assert scraper.calls[1][1] is None

    scraper = FakeScraper([403, 403])
    resp, host, reason = fetch_with_mirrors(
        scraper,
        'https://supjav.com/1.html',
        't',
        validate=lambda r: True,
    )

    assert resp is None
    assert host is None
    assert reason == 'blocked'
    assert len(scraper.calls) == 2
