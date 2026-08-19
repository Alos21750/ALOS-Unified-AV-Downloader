# coding: utf-8
"""JableTV page parsing (precise, non-greedy on minified HTML) and URL anchoring."""
import sys
import types


def _stub(name, factory=None):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = factory() if factory else types.ModuleType(name)


_stub('cloudscraper')
_stub('customtkinter')

from alos_downloader.sites import jabletv as jable_mod
from alos_downloader.sites.jabletv import JableTVBrowser, SiteJableTV


def test_parse_page_precise_on_minified_html():
    # Minified single-line HTML with multiple content=" and .m3u8. A greedy `.+` would grab
    # the LAST delimiter (wrong title / a URL spanning across quotes). Precise captures win.
    html = (
        '<meta property="og:title" content="REAL TITLE"/>'
        '<meta property="og:image" content="https://cdn/x/thumb.jpg"/>'
        '<meta property="og:description" content="DECOY DESC"/>'
        'var s="https://cdn.example/hls/video.m3u8";var b="https://other/decoy.m3u8"'
    )
    title, image, m3u8 = SiteJableTV._parse_page(html)
    assert title == 'REAL TITLE'
    assert image == 'https://cdn/x/thumb.jpg'
    assert m3u8 == 'https://cdn.example/hls/video.m3u8'   # first token, not spanning to decoy


def test_parse_page_returns_none_when_missing():
    assert SiteJableTV._parse_page('<html>no og meta and no playlist here</html>') is None


def test_validate_url_anchored():
    assert SiteJableTV.validate_url('https://jable.tv/videos/abc-123/') == 'abc-123'
    assert SiteJableTV.validate_url('https://jable.tv/videos/abc-123') is None   # needs trailing /
    assert SiteJableTV.validate_url('https://missav.ai/sone-543') is None


def test_category_counts_parse_english_video_suffix(monkeypatch):
    html = (
        '<a href="https://jable.tv/categories/">All</a>'
        '<a href="https://jable.tv/categories/bdsm/">BDSM5271 videos</a>'
    )
    response = types.SimpleNamespace(content=html.encode('utf-8'))
    monkeypatch.setattr(JableTVBrowser, '_get_scraper', classmethod(lambda cls: object()))
    monkeypatch.setattr(
        jable_mod,
        'fetch_with_mirrors',
        lambda *args, **kwargs: (response, 'jable.tv', 'ok'),
    )

    category = next(c for c in JableTVBrowser.fetch_categories()
                    if c.get('slug') == 'bdsm')
    assert category['name'] == 'BDSM'
    assert category['count'] == 5271
