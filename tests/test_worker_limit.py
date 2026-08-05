import concurrent.futures

import M3U8Sites
import config
import M3U8Sites.M3U8Crawler as crawler_mod


class _DummyCrawler(crawler_mod.M3U8Crawler):
    website_dirname_pattern = r'https://example\.test/(.+)$'

    def get_url_infos(self):
        self._targetName = 'example'
        self._m3u8url = 'https://cdn.example.test/master.m3u8'


def test_crawler_accepts_a_clamped_per_video_worker_limit(tmp_path):
    low = _DummyCrawler(
        'https://example.test/video', str(tmp_path), silence=True,
        max_workers=0)
    high = _DummyCrawler(
        'https://example.test/video', str(tmp_path), silence=True,
        max_workers=999)

    assert low._max_workers == 1
    assert high._max_workers == config.MAX_WORKERS_PER_VIDEO == 16


def test_crawler_uses_persisted_worker_limit_when_not_explicit(
        tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'get_max_workers_per_video', lambda: 3)

    crawler = _DummyCrawler(
        'https://example.test/video', str(tmp_path), silence=True)

    assert crawler._max_workers == 3


def test_create_site_forwards_explicit_worker_limit(monkeypatch, tmp_path):
    captured = {}

    class _FakeSite:
        @classmethod
        def validate_url(cls, url):
            return 'video'

        def __init__(self, url, savepath='', silence=False, max_workers=None):
            captured.update(
                url=url, savepath=savepath, silence=silence,
                max_workers=max_workers)

    monkeypatch.setattr(M3U8Sites, 'siteList', (_FakeSite,))

    result = M3U8Sites.CreateSite(
        'https://example.test/video', str(tmp_path), silence=True,
        max_workers=4)

    assert isinstance(result, _FakeSite)
    assert captured['max_workers'] == 4


def test_segment_executor_receives_the_job_worker_limit(monkeypatch):
    seen = []

    class _ImmediateExecutor:
        def __init__(self, max_workers):
            seen.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def map(self, fn, tasks, timeout=None):
            return [fn(task) for task in tasks]

    crawler = _DummyCrawler.__new__(_DummyCrawler)
    crawler._max_workers = 2
    crawler._tsList = ['https://cdn.example.test/0.ts']
    crawler._pending_set = {(0, 'https://cdn.example.test/0.ts')}
    crawler._cancel_job = False
    crawler._speed_start = 0
    crawler._bytes_downloaded = 0
    crawler._t2_executor = None
    crawler._scrape = lambda task: crawler._pending_set.discard(task) or True

    monkeypatch.setattr(
        concurrent.futures, 'ThreadPoolExecutor', _ImmediateExecutor)

    crawler._startCrawl()

    assert seen == [2]
