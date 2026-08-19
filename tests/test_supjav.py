from urllib.parse import urljoin
import sys
import threading
import types

import pytest


def _stub_runtime_dependency(name, factory=None):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = factory() if factory else types.ModuleType(name)


def _cloudscraper_stub():
    mod = types.ModuleType('cloudscraper')

    def create_scraper(*args, **kwargs):
        raise AssertionError('cloudscraper should not be used by offline tests')

    mod.create_scraper = create_scraper
    return mod


def _m3u8_stub():
    mod = types.ModuleType('m3u8')
    mod.load = lambda *args, **kwargs: None
    mod.loads = lambda *a, **k: types.SimpleNamespace(playlists=[], segments=[], keys=[])
    return mod


def _customtkinter_stub():
    mod = types.ModuleType('customtkinter')

    class CTk:
        pass

    mod.CTk = CTk
    mod.CTkLabel = CTk
    return mod


_stub_runtime_dependency('cloudscraper', _cloudscraper_stub)
_stub_runtime_dependency('m3u8', _m3u8_stub)
_stub_runtime_dependency('customtkinter', _customtkinter_stub)

from uav_downloader.sites import base as crawler_mod
from uav_downloader.sites import supjav as supjav_mod
from bs4 import BeautifulSoup
from uav_downloader.sites.base import M3U8Crawler
from uav_downloader.sites.supjav import (
    SiteSupJav,
    SupJavBrowser,
    _extract_m3u8,
    _extract_packed_m3u8,
    _extract_title,
    _extract_tv_link,
    _parse_videos,
    _server_links,
    _streamtape_direct_url,
    _strip_fake_header,
)


class _FakeResp:
    def __init__(self, status_code=200, headers=None, content=b'', text=None, url='https://example.test/master.m3u8'):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self.text = text if text is not None else content.decode('utf-8', errors='ignore')
        self.url = url


def test_supjav_validate_url_is_anchored():
    assert SiteSupJav.validate_url('https://supjav.com/433866.html') == '433866'
    assert SiteSupJav.validate_url('https://supjav.com/zh/12345.html') == '12345'
    assert SiteSupJav.validate_url('https://supjav.com/ja/12345.html') == '12345'
    assert SiteSupJav.validate_url('https://supjav.com/433866.html/x') is None
    assert SiteSupJav.validate_url('https://jable.tv/videos/x/') is None


def test_supjav_video_urls_are_not_listing_urls():
    from uav_downloader.apps.browse import ModernApp

    assert ModernApp._is_listing_url(None, 'https://supjav.com/12345.html') is False
    assert ModernApp._is_listing_url(None, 'https://supjav.com/zh/12345.html') is False
    assert ModernApp._is_listing_url(None, 'https://supjav.com/ja/12345.html') is False
    assert ModernApp._is_listing_url(None, 'https://supjav.com/zh/popular') is True


def test_supjav_page_url():
    assert SupJavBrowser.page_url('https://supjav.com/category/uncensored-jav', 2) == 'https://supjav.com/category/uncensored-jav/page/2'
    assert SupJavBrowser.page_url('https://supjav.com/popular?sort=week', 2) == 'https://supjav.com/popular?sort=week&page=2'
    assert SupJavBrowser.page_url('https://supjav.com/', 2) == 'https://supjav.com/page/2'
    assert SupJavBrowser.page_url('https://supjav.com/?s=fc2', 2) == 'https://supjav.com/page/2/?s=fc2'
    base = 'https://supjav.com/category/uncensored-jav'
    assert SupJavBrowser.page_url(base, 1) == base


def test_extract_m3u8_from_urlplay():
    body = r"var urlPlay = 'https:\/\/cdn1.turboviplay.com\/data1\/abc\/abc.m3u8';"
    assert _extract_m3u8(body) == 'https://cdn1.turboviplay.com/data1/abc/abc.m3u8'


def test_extract_tv_link_selects_tv_button():
    html = '''
    <a data-link="tsf">FST</a>
    <a data-link="321cba">TV</a>
    <a data-link="ts">ST</a>
    <a data-link="eov">VOE</a>
    '''
    tv_link = _extract_tv_link(html)
    assert tv_link == '321cba'
    assert tv_link[::-1] == 'abc123'


def test_extract_title_from_h1_without_og_title():
    soup = BeautifulSoup('''
    <html>
      <head><title>FC2PPV 4916515 [Limited To 200 Copies...]</title></head>
      <body><h1>FC2PPV 4916515 [Limited To 200 Copies...]</h1></body>
    </html>
    ''', 'html.parser')
    assert _extract_title(soup) == 'FC2PPV 4916515 [Limited To 200 Copies...]'


def test_parse_videos_uses_real_thumbnail_src_and_ignores_base64_placeholder():
    soup = BeautifulSoup('''
    <div class="post">
      <a href="https://supjav.com/1.html" title="Home"></a>
      <img class="thumb" src="https://img.supjav.com/home.jpg">
      <div class="meta">2026/07/12 <span>100 Views</span></div>
    </div>
    <div class="post">
      <a href="https://supjav.com/2.html" title="Category"></a>
      <img class="thumb" data-original="https://img.supjav.com/category.jpg" src="data:image/png;base64,placeholder">
    </div>
    <div class="post">
      <a href="https://supjav.com/3.html" title="Placeholder"></a>
      <img class="thumb" src="data:image/png;base64,placeholder">
    </div>
    ''', 'html.parser')
    videos = _parse_videos(soup)
    assert videos[0]['thumbnail'] == 'https://img.supjav.com/home.jpg'
    assert videos[0]['date'] == '2026/07/12'
    assert videos[1]['thumbnail'] == 'https://img.supjav.com/category.jpg'
    assert videos[1]['date'] == ''
    assert videos[2]['thumbnail'] == ''


def test_strip_fake_header_removes_png_prefix_from_ts():
    wrapped = b'\x89PNG\r\n\x1a\n' + b'\x00' * 180 + (b'\x47' + b'\x11' * 187) * 6
    stripped = _strip_fake_header(wrapped)
    assert stripped[:1] == b'\x47'
    assert len(stripped) == 188 * 6


def test_strip_fake_header_leaves_plain_ts_unchanged():
    plain = b'\x47' + b'\x00' * 187 * 5
    assert _strip_fake_header(plain) == plain


def test_strip_fake_header_falls_back_when_no_valid_sync_run():
    data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 300
    assert _strip_fake_header(data) == b''


def test_strip_fake_header_does_not_raise_on_short_input():
    assert _strip_fake_header(b'\x89PNG') == b''


def test_ts_segment_validation_rejects_empty_short_and_non_ts():
    assert crawler_mod._is_valid_ts_segment(b'\x47' + b'\x00' * 187)
    assert not crawler_mod._is_valid_ts_segment(b'')
    assert not crawler_mod._is_valid_ts_segment(b'\x47' + b'\x00' * 186)
    assert not crawler_mod._is_valid_ts_segment(b'<html>' + b'\x00' * 183)


def test_getm3u8_playlist_handles_absolute_and_relative_variants(monkeypatch):
    assert urljoin(
        'https://cdn1.turboviplay.com/data1/x/x.m3u8',
        'https://hls4.turbosplayer.com/file/u/master.m3u8',
    ) == 'https://hls4.turbosplayer.com/file/u/master.m3u8'

    class DummyCrawler(M3U8Crawler):
        def __init__(self):
            self._m3u8url = 'https://cdn1.turboviplay.com/data1/x/x.m3u8'
            self._extra_headers = {}

    loaded = []

    def fake_http_get(url, headers=None, timeout=20):
        loaded.append(url)
        return _FakeResp(
            status_code=200,
            headers={},
            content=b'#EXTM3U\n',
            text='#EXTM3U\n',
            url=url,
        )

    monkeypatch.setattr(crawler_mod, '_http_get', fake_http_get)
    monkeypatch.setattr(crawler_mod.m3u8, 'loads', lambda *a, **k: object())

    dummy = DummyCrawler()
    _, variant_base = dummy._getm3u8PlayList('https://hls4.turbosplayer.com/file/u/master.m3u8')
    assert loaded[-1] == 'https://hls4.turbosplayer.com/file/u/master.m3u8'
    assert variant_base == 'https://hls4.turbosplayer.com/file/u/'

    _, variant_base = dummy._getm3u8PlayList('variant/master.m3u8')
    assert loaded[-1] == 'https://cdn1.turboviplay.com/data1/x/variant/master.m3u8'
    assert variant_base == 'https://cdn1.turboviplay.com/data1/x/variant/'


def test_is_cf_block_resp_detects_only_cloudflare_blocks():
    assert crawler_mod._is_cf_block_resp(_FakeResp(403, headers={'Server': 'cloudflare'}))
    assert crawler_mod._is_cf_block_resp(_FakeResp(403, content=b'... Attention Required ...'))
    assert not crawler_mod._is_cf_block_resp(_FakeResp(404))
    assert not crawler_mod._is_cf_block_resp(_FakeResp(200, headers={'Server': 'cloudflare'}))


def test_load_m3u8_raises_blocked_on_cloudflare_resp(monkeypatch):
    class DummyCrawler(M3U8Crawler):
        def __init__(self):
            self._extra_headers = {}

    monkeypatch.setattr(
        crawler_mod,
        '_http_get',
        lambda *a, **k: _FakeResp(403, headers={'Server': 'cloudflare'}, url=a[0]),
    )

    with pytest.raises(crawler_mod.MirrorsBlockedError):
        DummyCrawler()._load_m3u8('https://example.test/master.m3u8')


def test_load_m3u8_raises_generic_on_non_cf_404(monkeypatch):
    class DummyCrawler(M3U8Crawler):
        def __init__(self):
            self._extra_headers = {}

    monkeypatch.setattr(
        crawler_mod,
        '_http_get',
        lambda *a, **k: _FakeResp(404, url=a[0]),
    )

    with pytest.raises(Exception) as exc:
        DummyCrawler()._load_m3u8('https://example.test/master.m3u8')
    assert not isinstance(exc.value, crawler_mod.MirrorsBlockedError)


def test_load_m3u8_raises_generic_when_content_is_not_playlist(monkeypatch):
    class DummyCrawler(M3U8Crawler):
        def __init__(self):
            self._extra_headers = {}

    monkeypatch.setattr(
        crawler_mod,
        '_http_get',
        lambda *a, **k: _FakeResp(200, content=b'not a playlist', text='not a playlist', url=a[0]),
    )

    with pytest.raises(Exception) as exc:
        DummyCrawler()._load_m3u8('https://example.test/master.m3u8')
    assert not isinstance(exc.value, crawler_mod.MirrorsBlockedError)


def test_server_links_maps_all_btn_servers():
    html = (
        '<a href="javascript:;" class="btn-server active" data-link="AAA">TV</a>'
        '<a href="javascript:;" class="btn-server" data-link="BBB">FST</a>'
        '<a href="javascript:;" class="btn-server" data-link="CCC">ST</a>'
        '<a href="javascript:;" class="btn-server" data-link="DDD">VOE</a>'
    )
    assert _server_links(html) == {'TV': 'AAA', 'FST': 'BBB', 'ST': 'CCC', 'VOE': 'DDD'}
    assert _server_links('<div>no servers here</div>') == {}


def test_streamtape_direct_url_evaluates_js_substring_and_ignores_decoy():
    # Streamtape overwrites #robotlink via JS; the static div text carries a DECOY token,
    # the real token only appears in the JS-computed value.
    html = (
        '<div id="ideoolink" style="display:none;">/streamtape.com/get_video?id=ABC'
        '&expires=123&ip=YYY&token=DECOY_2cde</div>'
        '<div id="robotlink" style="display:none;">/streamtape.com/get_video?id=ABC'
        '&expires=123&ip=YYY&token=DECOY_2cde</div>'
        "<script>document.getElementById('robotlink').innerHTML = '//streamtape.com/get_'"
        "+ ('xcdvideo?id=ABC&expires=123&ip=YYY&token=REAL_2-E6').substring(2).substring(1);</script>"
    )
    url = _streamtape_direct_url(html)
    assert url == 'https://streamtape.com/get_video?id=ABC&expires=123&ip=YYY&token=REAL_2-E6'
    assert 'DECOY' not in url            # never return the static-div decoy token
    assert _streamtape_direct_url('<html>no robotlink</html>') is None


def test_extract_packed_m3u8_keeps_signed_query(monkeypatch):
    monkeypatch.setattr(
        supjav_mod,
        '_unpack_js_eval',
        lambda _script: "var source='https://cdn.example/video/master.m3u8?t=abc&s=1';",
    )
    html = "<script>eval(function(p,a,c,k,e,d){/* m3u8 */})</script>"
    assert _extract_packed_m3u8(html) == (
        'https://cdn.example/video/master.m3u8?t=abc&s=1')
    assert _extract_packed_m3u8('<script>plain</script>') is None


def test_is_url_vaildate_accepts_direct_url_source():
    # Regression: the base gate is `True if self._m3u8url`; a Streamtape source has no
    # m3u8, only _direct_url. Without the override the caller silently skips the URL.
    s = SiteSupJav.__new__(SiteSupJav)
    s._m3u8url = None
    s._direct_url = None
    assert s.is_url_vaildate() is False
    s._direct_url = 'https://streamtape.com/get_video?id=x&token=y'
    assert s.is_url_vaildate() is True
    s._direct_url = None
    s._m3u8url = 'https://cdn.turboviplay.com/data3/x/x.m3u8'
    assert s.is_url_vaildate() is True


def test_direct_download_uses_parallel_ranges_and_assembles_file(monkeypatch, tmp_path):
    payload = bytes(range(256)) * 1024
    calls = []
    calls_lock = threading.Lock()

    class RangeResponse:
        def __init__(self, start, end):
            self.status_code = 206
            self.headers = {
                'content-range': f'bytes {start}-{end}/{len(payload)}',
                'content-length': str(end - start + 1),
            }
            self._data = payload[start:end + 1]

        def iter_content(self, chunk_size):
            for offset in range(0, len(self._data), chunk_size):
                yield self._data[offset:offset + chunk_size]

        def close(self):
            pass

    class RangeSession:
        def get(self, url, headers=None, **kwargs):
            range_header = (headers or {}).get('Range')
            with calls_lock:
                calls.append(range_header)
            assert range_header and range_header.startswith('bytes=')
            start, end = (int(value) for value in range_header[6:].split('-', 1))
            return RangeResponse(start, end)

    monkeypatch.setattr(supjav_mod, '_get_session', lambda: RangeSession(), raising=False)
    monkeypatch.setattr(
        supjav_mod,
        '_make_scraper',
        lambda: (_ for _ in ()).throw(AssertionError('range-capable downloads must not use the serial path')),
    )
    monkeypatch.setattr(supjav_mod.speed_limiter, 'acquire', lambda _size: None)

    crawler = SiteSupJav.__new__(SiteSupJav)
    crawler._cancel_job = False
    crawler._dest_folder = str(tmp_path)
    crawler._targetName = 'parallel'
    crawler._direct_url = 'https://streamtape.example/get_video?id=test'
    crawler._direct_referer = 'https://streamtape.example/e/test'
    crawler._progress_callback = None
    crawler._t2_executor = None
    crawler._max_workers = 2

    assert crawler._download_direct() is True
    assert (tmp_path / 'parallel.mp4').read_bytes() == payload
    assert not (tmp_path / 'parallel.mp4.part').exists()

    range_calls = [value for value in calls if value != 'bytes=0-0']
    assert len(range_calls) == 2


def test_direct_parallel_range_resumes_after_connection_reset(monkeypatch, tmp_path):
    payload = bytes(range(256)) * 1024
    calls = []
    calls_lock = threading.Lock()
    failed_once = False

    class RangeResponse:
        def __init__(self, start, end, fail=False):
            self.status_code = 206
            self.headers = {'content-range': f'bytes {start}-{end}/{len(payload)}'}
            self._data = payload[start:end + 1]
            self._fail = fail

        def iter_content(self, chunk_size):
            if self._fail:
                cut = max(1, len(self._data) // 2)
                yield self._data[:cut]
                raise ConnectionResetError('reset by peer')
            yield self._data

        def close(self):
            pass

    class RangeSession:
        def get(self, url, headers=None, **kwargs):
            nonlocal failed_once
            range_header = (headers or {}).get('Range')
            start, end = (int(value) for value in range_header[6:].split('-', 1))
            with calls_lock:
                calls.append(range_header)
                fail = start == 0 and end > 0 and not failed_once
                if fail:
                    failed_once = True
            return RangeResponse(start, end, fail=fail)

    monkeypatch.setattr(supjav_mod, '_get_session', lambda: RangeSession())
    monkeypatch.setattr(supjav_mod, '_DIRECT_RETRY_BASE_DELAY', 0)
    monkeypatch.setattr(supjav_mod.speed_limiter, 'acquire', lambda _size: None)

    crawler = SiteSupJav.__new__(SiteSupJav)
    crawler._cancel_job = False
    crawler._dest_folder = str(tmp_path)
    crawler._targetName = 'resumed'
    crawler._direct_url = 'https://streamtape.example/get_video?id=test'
    crawler._direct_referer = 'https://streamtape.example/e/test'
    crawler._progress_callback = None
    crawler._t2_executor = None

    assert crawler._download_direct() is True
    assert (tmp_path / 'resumed.mp4').read_bytes() == payload
    initial_starts = {start for start, _end in supjav_mod._split_byte_ranges(len(payload))}
    resumed_starts = {
        int(value[6:].split('-', 1)[0])
        for value in calls
        if value != 'bytes=0-0'
    } - initial_starts
    assert resumed_starts


def test_fst_hls_is_preferred_and_streamtape_is_fallback(monkeypatch):
    crawler = SiteSupJav.__new__(SiteSupJav)
    crawler._m3u8url = 'https://fst.example/master.m3u8'
    crawler._direct_url = 'https://streamtape.example/video.mp4'
    crawler._cancel_job = False
    crawler.cleanup_temp = lambda: None
    direct_calls = []
    crawler._download_direct = lambda: direct_calls.append(True) or True

    monkeypatch.setattr(crawler_mod.M3U8Crawler, 'start_download', lambda self: True)
    assert crawler.start_download() is True
    assert direct_calls == []

    def fail_hls(self):
        raise ConnectionError('FST unavailable')

    monkeypatch.setattr(crawler_mod.M3U8Crawler, 'start_download', fail_hls)
    assert crawler.start_download() is True
    assert direct_calls == [True]


def test_direct_download_keeps_serial_fallback_without_range_support(monkeypatch, tmp_path):
    payload = b'serial-fallback-data'

    class ProbeResponse:
        status_code = 200
        headers = {'content-length': str(len(payload))}

        def close(self):
            pass

    class ProbeSession:
        def get(self, url, headers=None, **kwargs):
            if (headers or {}).get('Range') == 'bytes=0-0':
                return ProbeResponse()
            assert 'Range' not in (headers or {})
            return SerialResponse()

    class SerialResponse:
        status_code = 200
        headers = {'content-length': str(len(payload))}

        def iter_content(self, chunk_size):
            yield payload

    monkeypatch.setattr(supjav_mod, '_get_session', lambda: ProbeSession())
    monkeypatch.setattr(supjav_mod.speed_limiter, 'acquire', lambda _size: None)

    crawler = SiteSupJav.__new__(SiteSupJav)
    crawler._cancel_job = False
    crawler._dest_folder = str(tmp_path)
    crawler._targetName = 'serial'
    crawler._direct_url = 'https://example.test/video.mp4'
    crawler._direct_referer = 'https://example.test/embed'
    crawler._progress_callback = None
    crawler._t2_executor = None

    assert crawler._download_direct() is True
    assert (tmp_path / 'serial.mp4').read_bytes() == payload


def test_create_m3u8_raises_on_zero_segments(monkeypatch):
    class DummyCrawler(M3U8Crawler):
        def __init__(self):
            self._m3u8url = 'https://example.test/master.m3u8'
            self._extra_headers = {}

    monkeypatch.setattr(
        DummyCrawler,
        '_load_m3u8',
        lambda self, url: types.SimpleNamespace(playlists=[], segments=[], keys=[]),
    )

    with pytest.raises(Exception):
        DummyCrawler()._create_m3u8()
