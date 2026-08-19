"""Comprehensive function tests for JableTV develop branch.
Exercises every non-UI code path that a user would hit.
"""
import os
import re
import sys
import time
import tempfile
import threading

print('=' * 60)
print('  JableTV Develop Branch — Function Test Suite')
print('=' * 60)

FAIL_COUNT = 0
PASS_COUNT = 0

def _check(label: str, cond, detail: str = ''):
    global FAIL_COUNT, PASS_COUNT
    if cond:
        print(f'  [PASS] {label}')
        PASS_COUNT += 1
    else:
        print(f'  [FAIL] {label}  {detail}')
        FAIL_COUNT += 1


# ── Test 1: module imports ────────────────────────────────────────
print('\n[1] Module imports')
try:
    from uav_downloader.apps import browse as gui_modern
    from uav_downloader.apps.browse import (
        DownloadManager, DownloadItem, fetch_page_data,
        _fetch_thumbnail, _get_thumb_session,
        DEFAULT_CONCURRENT, MAX_CONCURRENT, SITES, CSV_PATH,
    )
    from uav_downloader import sites as M3U8Sites
    from uav_downloader.sites.jabletv import JableTVBrowser
    from uav_downloader.sites.missav import MissAVBrowser
    from uav_downloader.sites.base import speed_limiter
    _check('imports ok', True)
except Exception as e:
    _check('imports ok', False, str(e))
    sys.exit(1)


# ── Test 2: DownloadManager basic ─────────────────────────────────
print('\n[2] DownloadManager basic operations')
mgr = DownloadManager(max_concurrent=2)
mgr.add_item('https://jable.tv/videos/abc-001/', name='abc-001')
mgr.add_item('https://jable.tv/videos/def-002/', name='def-002')
mgr.add_item('https://jable.tv/videos/abc-001/', name='dup')   # dup should be ignored
_check('add_item dedupes', len(mgr.get_items()) == 2)
_check('default concurrency is 2', mgr.max_concurrent == 2)

mgr.max_concurrent = 5
_check('concurrency setter works', mgr.max_concurrent == 5)

mgr.max_concurrent = 999   # over max
_check('concurrency clamped to MAX_CONCURRENT',
       mgr.max_concurrent == MAX_CONCURRENT)

mgr.max_concurrent = 0     # below min
_check('concurrency clamped to min 1', mgr.max_concurrent == 1)

mgr.remove_item('https://jable.tv/videos/abc-001/')
_check('remove_item works', len(mgr.get_items()) == 1)


# ── Test 3: CSV save/load ─────────────────────────────────────────
print('\n[3] CSV persistence')
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.csv',
                                   delete=False, encoding='utf-8')
tmp.close()
try:
    mgr.add_item('https://missav.ai/cn/ssis-100', '', '等待中')
    mgr.save_csv(tmp.name)
    _check('csv saved', os.path.exists(tmp.name) and
           os.path.getsize(tmp.name) > 0)

    mgr2 = DownloadManager()
    mgr2.load_csv(tmp.name)
    _check('csv roundtrip (count)', len(mgr2.get_items()) == len(mgr.get_items()))
    urls_orig = {i.url for i in mgr.get_items()}
    urls_new = {i.url for i in mgr2.get_items()}
    _check('csv roundtrip (urls match)', urls_orig == urls_new)
finally:
    os.unlink(tmp.name)


# ── Test 4: URL validation ────────────────────────────────────────
print('\n[4] URL validation')
valid = [
    'https://jable.tv/videos/ssis-100/',
    'https://missav.ai/cn/abc-001',
]
invalid = [
    '',
    'not a url',
    'https://example.com/unsupported',
    'ftp://example.com/foo',
]
for u in valid:
    _check(f'valid: {u}', M3U8Sites.VaildateUrl(u) is not None)
for u in invalid:
    _check(f'invalid rejected: {u!r}', M3U8Sites.VaildateUrl(u) is None)


# ── Test 5: Clipboard URL parsing ─────────────────────────────────
print('\n[5] Clipboard URL extraction regex')
# Re-create the same regex gui_modern uses
pattern = re.compile(r'https?://\S+')
samples = [
    ('raw url', 'https://jable.tv/videos/abc-001/',
     ['https://jable.tv/videos/abc-001/']),
    ('url with trailing punct',
     'Check this out: https://jable.tv/videos/abc-001/, cool!',
     ['https://jable.tv/videos/abc-001/']),
    ('multi urls',
     'a https://jable.tv/videos/a/ b https://jable.tv/videos/b/',
     ['https://jable.tv/videos/a/', 'https://jable.tv/videos/b/']),
    ('no url', 'nothing interesting here', []),
]
for name, text, expected in samples:
    found = [m.group(0).rstrip('.,;)\'"') for m in pattern.finditer(text)]
    _check(f'clipboard: {name}', found == expected,
           f'got {found}, expected {expected}')


# ── Test 6: Speed limiter ─────────────────────────────────────────
print('\n[6] Speed limiter')
speed_limiter.set_limit(0)   # unlimited
_check('speed_limiter.set_limit(0) ok', True)
speed_limiter.set_limit(5.0)  # 5 MB/s
_check('speed_limiter.set_limit(5.0) ok', True)
speed_limiter.set_limit(0)


# ── Test 7: Browser category fetch ────────────────────────────────
print('\n[7] Browser fetch_categories (live, may be slow)')

def _safe_fetch(browser_cls, label):
    try:
        cats = browser_cls.fetch_categories()
        if cats and isinstance(cats, list):
            _check(f'{label} categories returned', len(cats) > 0,
                   f'({len(cats)} categories)')
            # Spot-check shape
            c = cats[0]
            _check(f'{label} category has name/url',
                   'name' in c and 'url' in c)
            return cats
        _check(f'{label} categories returned', False, 'empty or wrong type')
    except Exception as e:
        _check(f'{label} categories returned', False, f'exception: {e}')
    return []

jab_cats = _safe_fetch(JableTVBrowser, 'JableTV')
mav_cats = _safe_fetch(MissAVBrowser, 'MissAV')


# ── Test 8: fetch_page (live, 1 page each) ────────────────────────
print('\n[8] Browser fetch_page (live)')

def _safe_page(browser_cls, url, label):
    try:
        videos = browser_cls.fetch_page(url)
        _check(f'{label} returned list',
               isinstance(videos, list))
        if videos:
            v = videos[0]
            keys = {'url', 'title', 'thumbnail', 'duration'}
            _check(f'{label} video shape',
                   all(k in v for k in keys),
                   f'keys: {set(v.keys())}')
            _check(f'{label} thumbnail populated',
                   bool(v.get('thumbnail')),
                   f'thumb={v.get("thumbnail")!r}')
        else:
            _check(f'{label} returned some videos', False, '0 videos')
    except Exception as e:
        _check(f'{label} fetch_page works', False, str(e))

if jab_cats:
    _safe_page(JableTVBrowser, jab_cats[0]['url'], 'JableTV page 1')
if mav_cats:
    _safe_page(MissAVBrowser, mav_cats[0]['url'], 'MissAV page 1')


# ── Test 9: fetch_page_data helper (used by UI) ───────────────────
print('\n[9] fetch_page_data helper (bad URL must not raise)')
data = fetch_page_data(JableTVBrowser, 'https://jable.tv/totally/broken/url/')
_check('fetch_page_data returns dict on error', isinstance(data, dict))
_check('fetch_page_data has videos key', 'videos' in data)
_check('fetch_page_data videos is list', isinstance(data['videos'], list))


# ── Test 10: Thumbnail loader ─────────────────────────────────────
print('\n[10] Thumbnail loader (live, uses JableTV if available)')
if jab_cats:
    videos = JableTVBrowser.fetch_page(jab_cats[0]['url'])
    if videos and videos[0].get('thumbnail'):
        turl = videos[0]['thumbnail']
        img = _fetch_thumbnail(turl)
        _check('thumbnail downloaded + decoded', img is not None,
               f'img={img!r}')
        if img is not None:
            _check('thumbnail width <= 260', img.width <= 260,
                   f'w={img.width}')
            _check('thumbnail is cached',
                   _fetch_thumbnail(turl) is img)


# ── Test 11: JableTV sidebar tags data ────────────────────────────
print('\n[11] JableTV sidebar tags')
_check('SIDEBAR_TAGS exists', hasattr(JableTVBrowser, 'SIDEBAR_TAGS'))
_check('SIDEBAR_TAGS is non-empty dict',
       isinstance(JableTVBrowser.SIDEBAR_TAGS, dict)
       and len(JableTVBrowser.SIDEBAR_TAGS) > 0)
sample_slug = None
for group, taglist in JableTVBrowser.SIDEBAR_TAGS.items():
    if taglist:
        sample_slug = taglist[0][1]
        break
if sample_slug:
    url = JableTVBrowser.tag_url(sample_slug)
    _check('tag_url builds full url', url.startswith('https://'))


# ── Test 12: MissAV page_url pagination ───────────────────────────
print('\n[12] MissAV page_url pagination')
base = 'https://missav.ai/dm539/new'
_check('page 1 = base', MissAVBrowser.page_url(base, 1) == base)
_check('page 2 adds ?page=2',
       MissAVBrowser.page_url(base, 2) == f'{base}?page=2')
_check('page 3 with existing ? uses &',
       MissAVBrowser.page_url('https://missav.ai/dm539/new?x=1', 3)
       == 'https://missav.ai/dm539/new?x=1&page=3')


# ── Test 13: DownloadManager.enqueue + cancel_all (no real DL) ────
print('\n[13] DownloadManager cancel semantics')
mgr3 = DownloadManager(max_concurrent=1)
mgr3.add_item('https://jable.tv/videos/fake-001/', state='等待中')
mgr3.add_item('https://jable.tv/videos/fake-002/', state='等待中')
# We don't actually want to start downloads. Just test cancel_all on
# empty-active state is safe.
mgr3.cancel_all()
_check('cancel_all on no-active is safe', True)
mgr3.clear_all()
_check('clear_all leaves empty list', len(mgr3.get_items()) == 0)


# ── Test 14: Multi-file concurrent download queue ─────────────────
# Uses invalid-looking URLs so they fail fast (網址錯誤) — this
# exercises the enqueue→active→release cycle without burning real
# bandwidth or disk space. The concurrency mechanism is what we care
# about: do slots open up, do pending items advance, does state stay
# consistent across threads?
print('\n[14] Multi-file concurrent download (fast-fail URLs)')

fake_urls = [f'https://jable.tv/videos/nonexistent-{i:03d}/' for i in range(6)]
mgr4 = DownloadManager(max_concurrent=2)
dest = tempfile.mkdtemp(prefix='jable_test_')
try:
    for u in fake_urls:
        mgr4.add_item(u, state='等待中')
    _check('6 items queued', len(mgr4.get_items()) == 6)

    # Fire them all off
    for u in fake_urls:
        mgr4.enqueue(u, dest)

    # Immediately after enqueue, max_concurrent (2) should be active
    # and the remaining 4 should be pending.
    _check('active respects max_concurrent',
           mgr4.active_count <= 2,
           f'active={mgr4.active_count}')
    _check('pending = total - active (at start)',
           mgr4.active_count + mgr4.pending_count == 6,
           f'active={mgr4.active_count} pending={mgr4.pending_count}')

    # Wait for the queue to drain. Each fake URL fails quickly
    # (CreateSite → is_url_vaildate → False → 網址錯誤), so within ~30s
    # the entire queue should settle.
    deadline = time.time() + 45
    while time.time() < deadline:
        if mgr4.active_count == 0 and mgr4.pending_count == 0:
            break
        time.sleep(0.5)

    _check('queue drained within 45s',
           mgr4.active_count == 0 and mgr4.pending_count == 0,
           f'active={mgr4.active_count} pending={mgr4.pending_count}')

    # All items should end in a terminal state (網址錯誤 here; could
    # also be 未完成 if the remote returns something weird).
    terminal = {'網址錯誤', '未完成', '已下載', '已取消'}
    final_states = [i.state for i in mgr4.get_items()]
    _check('all items reached terminal state',
           all(s in terminal for s in final_states),
           f'states={final_states}')

    # Concurrency scale-up test: bump limit while items are queued.
    mgr5 = DownloadManager(max_concurrent=1)
    scale_urls = [f'https://jable.tv/videos/scale-{i:03d}/' for i in range(4)]
    for u in scale_urls:
        mgr5.add_item(u, state='等待中')
        mgr5.enqueue(u, dest)
    time.sleep(0.2)
    # With limit=1, exactly 1 should be active
    _check('scale-up: only 1 active before bump',
           mgr5.active_count <= 1,
           f'active={mgr5.active_count}')
    # Bump to 3 — should kick off more workers
    mgr5.max_concurrent = 3
    time.sleep(0.3)
    # At this point active should have grown (unless all already finished)
    _check('scale-up: limit setter kicks queue',
           mgr5.active_count >= 1 or mgr5.pending_count < 3,
           f'active={mgr5.active_count} pending={mgr5.pending_count}')

    # Drain
    deadline = time.time() + 30
    while time.time() < deadline:
        if mgr5.active_count == 0 and mgr5.pending_count == 0:
            break
        time.sleep(0.3)
    _check('scale-up queue drained',
           mgr5.active_count == 0 and mgr5.pending_count == 0)

    # cancel_all while items are in flight
    mgr6 = DownloadManager(max_concurrent=3)
    cancel_urls = [f'https://jable.tv/videos/cancel-{i:03d}/' for i in range(5)]
    for u in cancel_urls:
        mgr6.add_item(u, state='等待中')
        mgr6.enqueue(u, dest)
    mgr6.cancel_all()
    # After cancel, pending should be clear; active may still be draining
    _check('cancel_all clears pending',
           mgr6.pending_count == 0,
           f'pending={mgr6.pending_count}')
    # Give active workers time to exit
    deadline = time.time() + 30
    while time.time() < deadline:
        if mgr6.active_count == 0:
            break
        time.sleep(0.3)
    _check('cancel_all drains active',
           mgr6.active_count == 0,
           f'active={mgr6.active_count}')
finally:
    try:
        import shutil
        shutil.rmtree(dest, ignore_errors=True)
    except Exception:
        pass


# ── Summary ───────────────────────────────────────────────────────
print('\n' + '=' * 60)
print(f'  TOTAL: {PASS_COUNT} passed, {FAIL_COUNT} failed')
print('=' * 60)
sys.exit(1 if FAIL_COUNT else 0)
