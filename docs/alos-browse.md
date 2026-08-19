# ALOS Browse

ALOS Browse is the interactive Windows application in ALOS Unified AV
Downloader. It is designed for people who want to search, inspect, select, and
queue individual videos from JableTV, MissAV, SupJav, and Hanime1.

## Typical workflow

1. Open the Browse tab and select a supported site.
2. Choose a category or enter a search query.
3. Select one or more video cards.
4. Add the selection to the persistent queue or download it immediately.
5. Follow progress on the Download tab while continuing to browse.

URLs can also be pasted directly or imported from text and CSV files. Active
downloads can be stopped and placed at the front of the queue again; failed
items can be retried independently.

## Controls

- Concurrent video downloads: 1–32, with 2 as the default.
- Segment workers per video: 1–16; individual sources may enforce a lower
  limit.
- Quality preference: highest, 1080p, 720p, 480p, 360p, or lowest.
- Optional download speed limit.
- Custom HTTP, HTTPS, SOCKS4, or SOCKS5 proxy, or the enabled Windows manual
  proxy.
- Local-first Japanese, English, and Traditional Chinese AI subtitles.

Download work and subtitle generation use separate queues. A long subtitle job
therefore does not occupy a video download slot.

## Install and run

Download `ALOS_Browse.exe` from the latest GitHub Release. The release build is
portable, includes ffmpeg, and does not require a Python installation.

From a source checkout:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
alos-browse
```

ALOS Browse checks GitHub Releases in the background. It never replaces the
running executable without user confirmation.
