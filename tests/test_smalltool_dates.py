import sys
import types
from datetime import date, datetime, timedelta, timezone


def _stub_runtime_dependency(name, factory=None):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = factory() if factory else types.ModuleType(name)


def _cloudscraper_stub():
    mod = types.ModuleType('cloudscraper')

    def create_scraper(*args, **kwargs):
        raise AssertionError('cloudscraper should not be used by date parser tests')

    mod.create_scraper = create_scraper
    return mod


def _m3u8_stub():
    mod = types.ModuleType('m3u8')
    mod.load = lambda *args, **kwargs: None
    return mod


_stub_runtime_dependency('cloudscraper', _cloudscraper_stub)
_stub_runtime_dependency('m3u8', _m3u8_stub)

from uav_downloader.apps.watch import SmallToolWorker, _months_before


def test_parse_relative_date_multilingual():
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)

    assert SmallToolWorker._parse_relative_date('3天前', now) == now - timedelta(days=3)
    assert SmallToolWorker._parse_relative_date('3 days ago', now) == now - timedelta(days=3)
    assert SmallToolWorker._parse_relative_date('yesterday', now) == now - timedelta(days=1)
    assert SmallToolWorker._parse_relative_date('3日前', now) == now - timedelta(days=3)
    assert SmallToolWorker._parse_relative_date('昨日', now) == now - timedelta(days=1)


def test_month_shortcuts_use_calendar_months_and_clamp_end_of_month():
    assert _months_before(date(2026, 7, 12), 1) == date(2026, 6, 12)
    assert _months_before(date(2026, 7, 12), 2) == date(2026, 5, 12)
    assert _months_before(date(2025, 3, 31), 1) == date(2025, 2, 28)
    assert _months_before(date(2024, 3, 31), 1) == date(2024, 2, 29)
    assert _months_before(date(2026, 1, 31), 2) == date(2025, 11, 30)
