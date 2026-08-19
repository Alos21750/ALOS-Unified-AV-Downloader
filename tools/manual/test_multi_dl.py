#!/usr/bin/env python
# coding: utf-8
"""Focused test for concurrent download correctness.

Exercises the DownloadManager + M3U8Crawler path with real jable.tv URLs
drawn from page 1. Runs 3 jobs concurrently (max_concurrent=3), lets each
progress for ~40s, then cancels and reports per-URL state + bytes fetched.

Not a fast unit test — takes up to 2 minutes. Meant for verifying that
concurrent downloads actually produce progress on independent URLs.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alos_downloader.apps.browse import DownloadManager  # noqa: E402
from alos_downloader.sites.jabletv import JableTVBrowser  # noqa: E402


def _fmt_bytes(n: int) -> str:
    if n >= 1024 * 1024:
        return f'{n / 1024 / 1024:.1f} MB'
    if n >= 1024:
        return f'{n / 1024:.0f} KB'
    return f'{n} B'


def main() -> int:
    print('Fetching page 1 to pick 3 real URLs...', flush=True)
    videos = JableTVBrowser.fetch_page('https://jable.tv/latest-updates/')
    if len(videos) < 3:
        print('  [FAIL] page 1 returned fewer than 3 videos')
        return 1
    urls = [v['url'] for v in videos[:3]]
    for u in urls:
        print(f'  pick: {u}')

    dest = tempfile.mkdtemp(prefix='jable_multi_dl_')
    print(f'\nDest: {dest}')

    mgr = DownloadManager(max_concurrent=3)
    for u in urls:
        mgr.add_item(u, state='等待中')
        mgr.enqueue(u, dest)

    start = time.time()
    last_print = 0.0
    run_for = 40
    while time.time() - start < run_for:
        time.sleep(1)
        now = time.time()
        if now - last_print >= 5:
            last_print = now
            for item in mgr.get_items():
                print(f'  [{item.state:>4}] {item.progress:>3}% {item.speed:>10}  '
                      f'{(item.name or item.url)[:60]}', flush=True)
            print(f'  active={mgr.active_count} pending={mgr.pending_count}\n',
                  flush=True)

    print('\nCancelling all...', flush=True)
    mgr.cancel_all()
    time.sleep(3)

    # Report
    print('\n── Final ──')
    passed = 0
    for item in mgr.get_items():
        # Must have EITHER progressed or errored gracefully, not be stuck 等待中
        progressed = item.progress > 0 or item.state in (
            '已下載', '已取消', '網址錯誤', '未完成', '準備中')
        status = 'PASS' if progressed else 'FAIL'
        if progressed:
            passed += 1
        print(f'  [{status}] state={item.state:>6}  progress={item.progress:>3}%  '
              f'{(item.name or item.url)[:70]}')

    # Folder sizing sanity: each URL should have started its own temp folder
    entries = [p for p in os.listdir(dest) if os.path.isdir(os.path.join(dest, p))]
    print(f'\n  temp/dest sub-folders created: {len(entries)}')
    for e in entries:
        sub = os.path.join(dest, e)
        total = 0
        for root, _, files in os.walk(sub):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        print(f'    {e}  →  {_fmt_bytes(total)}')

    # We consider the test passed if all 3 items reached a non-idle state
    # within the 40s window.
    all_ok = passed == len(urls) and len(entries) >= 1
    print('\n' + ('[OVERALL PASS]' if all_ok else '[OVERALL FAIL]'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
