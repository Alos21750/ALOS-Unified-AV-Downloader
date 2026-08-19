# Migrating to UAV Downloader

Version 3.1 adopts the public name **UAV Downloader** and the three workflow
names **UAV Browser**, **UAV Watcher**, and **UAV Downloader CLI**. Existing
settings and download history are migrated automatically and non-destructively.

## Name mapping

| Previous name | UAV canonical name |
|---|---|
| Repository `ALOS-Unified-AV-Downloader` | `UAV-Downloader` |
| ALOS Browse / `ALOS_Browse.exe` | UAV Browser / `UAV_Browser.exe` |
| ALOS Watch / `ALOS_Watch.exe` | UAV Watcher / `UAV_Watcher.exe` |
| `ALOS_Watch_portable.zip` | `UAV_Watcher_portable.zip` |
| `ALOS_reazonspeech_asr_v1.zip` | `UAV_reazonspeech_asr_v1.zip` |
| Modern / `JableTV_Modern.exe` | UAV Browser / `UAV_Browser.exe` |
| SmallTool / `Jable_smalltool.exe` | UAV Watcher / `UAV_Watcher.exe` |
| Docker / CLI | UAV Downloader CLI |
| Former GHCR image names | `ghcr.io/alos21750/uav-downloader` |

GitHub redirects the former repository URLs. New documentation, update checks,
badges, source links, package metadata, and examples use the UAV names.

## Existing installations

No uninstall is required. Download a canonical UAV executable and run it from
a writable folder. UAV Downloader copies compatible preferences, queue data,
subtitle settings, Watch selections, and Watch history into the new locations.

Migration is intentionally non-destructive:

- Source files remain at the old location.
- Existing files at the new location are never overwritten.
- Symbolic links and directory junctions are not followed.
- A failed copy does not delete or modify the source.

The portable Watch state directory is now `.uav-watcher`. It can import from
`.alos-watch` and `.Jable_smalltool`. The AppData root is now
`%APPDATA%\UAV Downloader`; it can import from `%APPDATA%\ALOS Unified AV
Downloader` and `%APPDATA%\JableTV Downloader`.

## Release and updater compatibility

Version 3.1 releases publish canonical UAV assets. They also publish exact
ALOS v3.0 and Jable v2 executable/model aliases so installed update clients can
keep resolving downloads. Each alias is a byte-for-byte copy of its canonical
asset and is listed independently in `SHA256SUMS.txt` and release attestations.
New installations should always choose the UAV filename.

The former GHCR image names continue as compatibility channels. New
deployments should use `ghcr.io/alos21750/uav-downloader` so configuration and
documentation remain clear.
