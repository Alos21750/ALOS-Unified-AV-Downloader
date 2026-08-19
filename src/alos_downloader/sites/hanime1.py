#!/usr/bin/env python
# coding: utf-8
"""Hanime1.me direct-MP4 downloader and browse/search adapter."""

import html
import re
import threading
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import cloudscraper
try:
    from curl_cffi import requests as cffi_requests
    _use_cffi = True
except ImportError:
    _use_cffi = False
from bs4 import BeautifulSoup

from alos_downloader.core import config
from alos_downloader.i18n import sites as site_i18n
from alos_downloader.sites.base import (
    MirrorsBlockedError,
    get_resolution_pref,
    request_headers,
)
from alos_downloader.sites.supjav import SiteSupJav


HANIME1_ROOT = 'https://hanime1.me'
HANIME1_HOME = HANIME1_ROOT + '/'
_BLOCKED_STATUS = frozenset({403, 429, 503})
_browser_local = threading.local()


def _make_scraper():
    """Return a browser-fingerprint session able to establish Hanime1 cookies."""
    if _use_cffi:
        return cffi_requests.Session(impersonate='chrome')
    return cloudscraper.create_scraper(browser=request_headers, delay=10)


def _blocked_response(response) -> bool:
    status = int(getattr(response, 'status_code', 0) or 0)
    if status in _BLOCKED_STATUS:
        return True
    body = str(getattr(response, 'text', '') or '')[:20000].casefold()
    return ('attention required' in body or 'just a moment' in body or
            'cf-chl-' in body)


def _request(session, url, *, timeout=30):
    response = session.get(
        url,
        headers={'Referer': HANIME1_HOME},
        timeout=timeout,
        allow_redirects=True,
        **config.proxy_request_kwargs(),
    )
    if _blocked_response(response):
        raise MirrorsBlockedError(url)
    return response


def _prime_session(session):
    """Visit the homepage first; Hanime1 issues both XSRF and session cookies there."""
    response = _request(session, HANIME1_HOME)
    if int(getattr(response, 'status_code', 0) or 0) != 200:
        raise Exception(f'Hanime1 初始化失敗 (HTTP {response.status_code})')
    return session


def _mp4_height(url, label=''):
    value = f'{label} {url}'
    match = re.search(r'(?<!\d)(\d{3,4})\s*p(?!\w)', value, re.I)
    return int(match.group(1)) if match else None


def _extract_sources(soup):
    """Extract fresh signed progressive-MP4 sources from watch/download markup."""
    sources = []
    seen = set()

    def _add(raw_url, label=''):
        url = html.unescape(str(raw_url or '').strip()).replace('\\/', '/')
        try:
            parsed = urlsplit(url)
        except ValueError:
            return
        if (parsed.scheme.casefold() != 'https' or not parsed.hostname or
                not parsed.path.casefold().endswith('.mp4') or url in seen):
            return
        seen.add(url)
        sources.append({'url': url, 'height': _mp4_height(url, label)})

    for element in soup.select('source[src], a[data-url], a[href]'):
        raw_url = element.get('src') or element.get('data-url') or element.get('href')
        _add(raw_url, element.get_text(' ', strip=True))

    # Keep a conservative fallback for MP4 URLs embedded in inline JSON/JavaScript.
    markup = html.unescape(str(soup)).replace('\\/', '/')
    for raw_url in re.findall(r'https://[^\s\'"<>]+?\.mp4(?:\?[^\s\'"<>]*)?', markup, re.I):
        _add(raw_url)
    return sources


def _select_source(sources, preference):
    """Apply the same highest/lowest/target-or-below policy as HLS variants."""
    items = list(sources or [])
    if not items:
        return None
    known = [item for item in items if isinstance(item.get('height'), int)]
    pref = str(preference or '').strip().casefold()
    if pref == 'lowest':
        return min(known, key=lambda item: item['height']) if known else items[0]
    if pref in {'1080', '720', '480', '360'}:
        if not known:
            return items[0]
        target = int(pref)
        at_or_below = [item for item in known if item['height'] <= target]
        if at_or_below:
            return max(at_or_below, key=lambda item: item['height'])
        return min(known, key=lambda item: item['height'])
    return max(known, key=lambda item: item['height']) if known else items[0]


def _clean_text(value):
    return ' '.join(html.unescape(str(value or '')).replace('\xa0', ' ').split())


def _extract_title(soup):
    heading = soup.select_one('h3.video-details-wrapper')
    if heading:
        title = _clean_text(heading.get_text(' ', strip=True))
        if title:
            return title
    meta = soup.select_one('meta[property="og:title"][content]')
    title = _clean_text(meta.get('content')) if meta else ''
    title = re.sub(r'\s+-\s+Hanime1\.me\s*$', '', title, flags=re.I)
    if title:
        return title
    return _clean_text(soup.title.get_text(' ', strip=True) if soup.title else '')


def _extract_image(soup):
    meta = soup.select_one('meta[property="og:image"][content]')
    raw = meta.get('content') if meta else ''
    if not raw:
        video = soup.select_one('video[poster]')
        raw = video.get('poster') if video else ''
    image_url = urljoin(HANIME1_HOME, html.unescape(str(raw or '').strip()))
    try:
        return image_url if urlsplit(image_url).scheme.casefold() == 'https' else None
    except ValueError:
        return None


def _parse_videos(soup, listing_url=''):
    videos = []
    seen = set()
    for card in soup.select('.video-item-container'):
        anchor = card.select_one('a.video-link[href]')
        if not anchor:
            continue
        raw_url = urljoin(HANIME1_HOME, anchor.get('href', ''))
        video_id = SiteHanime1.validate_url(raw_url)
        if not video_id:
            continue
        video_url = f'{HANIME1_ROOT}/watch?v={video_id}'
        if video_url in seen:
            continue
        seen.add(video_url)

        title_el = card.select_one('.title')
        title = _clean_text(
            title_el.get_text(' ', strip=True) if title_el else card.get('title', ''))
        image = card.select_one('img.main-thumb, img[data-src], img[src]')
        thumbnail = ''
        if image:
            thumbnail = urljoin(
                HANIME1_HOME,
                image.get('data-src') or image.get('src') or '',
            )
        duration_el = card.select_one('.duration')
        time_el = card.select_one('.subtitle-time')
        date_text = _clean_text(time_el.get_text(' ', strip=True) if time_el else '')
        date_text = re.sub(r'^[•·\-]\s*', '', date_text)
        author_el = card.select_one('.subtitle a[href]')
        item = {
            'url': video_url,
            'title': title,
            'thumbnail': thumbnail,
            'duration': _clean_text(
                duration_el.get_text(' ', strip=True) if duration_el else ''),
            'date': date_text,
            'author': _clean_text(
                author_el.get_text(' ', strip=True) if author_el else ''),
        }
        if listing_url:
            item['_source_listing_url'] = listing_url
        videos.append(item)
    return videos


def _filter_url(**params):
    pairs = []
    for key, value in params.items():
        if isinstance(value, (list, tuple)):
            pairs.extend((key, item) for item in value)
        elif value not in (None, ''):
            pairs.append((key, value))
    query = urlencode(pairs, doseq=True)
    return f'{HANIME1_ROOT}/search' + (f'?{query}' if query else '')


class SiteHanime1(SiteSupJav):
    website_pattern = r'https://(?:www\.)?hanime1\.me/watch\?v=\d+$'
    website_dirname_pattern = r'https://(?:www\.)?hanime1\.me/watch\?v=(\d+)$'
    direct_site_name = 'Hanime1'
    direct_default_referer = HANIME1_HOME

    def get_url_infos(self):
        self._direct_url = None
        self._direct_referer = None
        self._m3u8url = None
        with _make_scraper() as scraper:
            _prime_session(scraper)
            response = _request(scraper, self._url)
            status = int(getattr(response, 'status_code', 0) or 0)
            if status != 200:
                raise Exception(f'Hanime1 影片頁讀取失敗 (HTTP {status})')
            soup = BeautifulSoup(response.content, 'html.parser')
            sources = _extract_sources(soup)

            # Older/alternate pages may put the signed URLs only on /download.
            if not sources:
                video_id = self.validate_url(self._url)
                download_url = f'{HANIME1_ROOT}/download?v={video_id}'
                download_response = _request(scraper, download_url)
                download_status = int(
                    getattr(download_response, 'status_code', 0) or 0)
                if download_status == 200:
                    sources = _extract_sources(BeautifulSoup(
                        download_response.content, 'html.parser'))

        selected = _select_source(sources, get_resolution_pref())
        if not selected:
            raise Exception('此 Hanime1 影片目前沒有可用的 MP4 下載來源')
        title = _extract_title(soup)
        if not title:
            raise Exception('Hanime1 影片標題解析失敗（版面可能已改版）')
        self._targetName = title
        self._imageUrl = _extract_image(soup)
        self._direct_url = selected['url']
        self._direct_referer = self._url
        self._extra_headers = {'Referer': self._url}


class Hanime1Browser:
    _url_root = HANIME1_ROOT

    SORTS = (
        '最新上市', '最新上傳', '本日排行', '本週排行', '本月排行',
        '觀看次數', '讚好比例', '時長最長', '他們在看',
    )
    GENRES = (
        '裏番', '泡麵番', 'Motion Anime', '3DCG', '2.5D',
        '2D動畫', 'AI生成', 'MMD', 'Cosplay',
    )
    FEATURE_TAGS = ('中文字幕', '中文配音', '無碼', 'AI解碼', '1080p', '60FPS')
    CATEGORIES = (
        [(name, _filter_url(sort=name)) for name in SORTS] +
        [(name, _filter_url(genre=name)) for name in GENRES] +
        [(name, _filter_url(**{'tags[]': [name]})) for name in FEATURE_TAGS]
    )
    HOMEPAGE_SECTIONS = tuple(CATEGORIES)

    @classmethod
    def _get_scraper(cls):
        scraper = getattr(_browser_local, 'scraper', None)
        if scraper is None:
            scraper = _make_scraper()
            try:
                _prime_session(scraper)
            except Exception:
                try:
                    scraper.close()
                except Exception:
                    pass
                raise
            _browser_local.scraper = scraper
        return scraper

    @classmethod
    def _reset_scraper(cls):
        scraper = getattr(_browser_local, 'scraper', None)
        if scraper is not None:
            try:
                scraper.close()
            except Exception:
                pass
        _browser_local.scraper = None

    @classmethod
    def fetch_categories(cls):
        return [{
            'name': site_i18n.loc(site_i18n.CATEGORY_I18N, url, name),
            'url': url,
            'count': 0,
        } for name, url in cls.CATEGORIES]

    @classmethod
    def _listing_url_allowed(cls, url):
        try:
            parsed = urlsplit(str(url or ''))
        except ValueError:
            return False
        return (
            parsed.scheme.casefold() == 'https' and
            not parsed.username and not parsed.password and
            (parsed.hostname or '').casefold() in {'hanime1.me', 'www.hanime1.me'} and
            parsed.path.rstrip('/') in {'', '/search'}
        )

    @classmethod
    def fetch_page(cls, url):
        if not cls._listing_url_allowed(url):
            return []
        for attempt in range(2):
            try:
                response = _request(cls._get_scraper(), url)
                break
            except MirrorsBlockedError:
                cls._reset_scraper()
                if attempt:
                    raise
        else:
            return []
        if int(getattr(response, 'status_code', 0) or 0) != 200:
            return []
        try:
            return _parse_videos(
                BeautifulSoup(response.content, 'html.parser'), str(url))
        except Exception:
            return []

    @classmethod
    def page_url(cls, base, page):
        if page <= 1:
            return base
        parsed = urlsplit(str(base or ''))
        pairs = [(key, value) for key, value in parse_qsl(
            parsed.query, keep_blank_values=True) if key != 'page']
        pairs.append(('page', str(int(page))))
        return urlunsplit((
            parsed.scheme, parsed.netloc, parsed.path, urlencode(pairs), ''))

    @classmethod
    def search_url(cls, query):
        return _filter_url(query=str(query or '').strip())

    @classmethod
    def search(cls, query):
        return cls.fetch_page(cls.search_url(query))
