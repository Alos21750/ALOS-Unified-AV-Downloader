import sys
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
    return mod


_stub_runtime_dependency('cloudscraper', _cloudscraper_stub)
_stub_runtime_dependency('m3u8', _m3u8_stub)

from alos_downloader.i18n import locales
from alos_downloader.i18n import sites as site_i18n
from alos_downloader.sites.jabletv import JableTVBrowser


@pytest.fixture(autouse=True)
def _reset_locale():
    yield
    locales.set_lang('en')


def test_jable_sidebar_tags_have_i18n_entries():
    missing = [
        slug
        for tags in JableTVBrowser.SIDEBAR_TAGS.values()
        for _, slug in tags
        if slug not in site_i18n.TAGS
    ]
    assert missing == []


def test_jable_sidebar_groups_have_i18n_entries():
    missing = [
        group
        for group in JableTVBrowser.SIDEBAR_TAGS
        if group not in site_i18n.TAG_GROUPS
    ]
    assert missing == []


def test_loc_uses_current_language_and_unknown_key_fallback():
    locales.set_lang('en')
    assert site_i18n.loc(site_i18n.TAGS, 'creampie') == 'Creampie'

    locales.set_lang('ja')
    assert site_i18n.loc(site_i18n.TAGS, 'creampie') == '中出し'

    assert site_i18n.loc(site_i18n.TAGS, 'missing-slug', 'Fallback') == 'Fallback'


def test_loc_spot_checks():
    locales.set_lang('en')
    assert site_i18n.loc(site_i18n.TAG_GROUPS, '身材') == 'Body'
    assert site_i18n.loc(site_i18n.TAGS, 'creampie') == 'Creampie'

    locales.set_lang('ja')
    assert site_i18n.loc(site_i18n.TAGS, 'creampie')
