# ALOS Watch

ALOS Watch is the unattended automation application in ALOS Unified AV
Downloader. Select what you care about once; ALOS Watch can then discover new
releases, deduplicate them across categories and sites, choose the preferred
version, download them, and optionally generate subtitles without daily manual
work.

## Why it is different

Most downloaders start with a URL the user already found. ALOS Watch starts
with an intent: selected feeds, rankings, categories, tags, or makers. It keeps
that selection, scans it on schedule, and only downloads candidates that pass
the configured date and version rules.

The current registry exposes grouped targets for all four supported sites:

| Site | Selectable targets | Examples |
|---|---:|---|
| JableTV | 129 | new releases, rankings, categories, tags |
| MissAV | 102 | feeds, categories, tags, makers |
| SupJav | 10 | feeds, rankings, primary categories |
| Hanime1 | 24 | release/upload/ranking feeds, genres, feature tags |

## Set it up once

1. Choose a destination directory.
2. Set the baseline date, quality, worker limit, version preference, subtitle
   mode, and optional proxy.
3. Search or browse each site tab and select targets. Whole groups can be
   selected together.
4. Choose an interval from 1–168 hours, or one daily time in the computer's
   local timezone.
5. Start monitoring.

Check Now performs one immediate scan without creating a duplicate schedule.
The activity panel can remain collapsed while idle and opened only when a log
is needed.

## Deduplication and state

When a stable video identifier is available, ALOS Watch combines duplicates
found in multiple categories or sites and retains the candidate that best
matches the configured version preference. When an identifier cannot be
established safely, only identical URLs are deduplicated; the application does
not guess.

Portable state is stored beside the application in `.alos-watch` when that
location is writable. Otherwise it uses
`%APPDATA%\ALOS Unified AV Downloader\watch`. v3 copies compatible state from
the previous locations without deleting the original data or overwriting newer
files. See the [v3 migration guide](./migration-v3.md).

## Install and run

- `ALOS_Watch.exe`: portable one-file Windows build.
- `ALOS_Watch_portable.zip`: onedir fallback that avoids temporary one-file
  extraction.

From source:

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
alos-watch
```
