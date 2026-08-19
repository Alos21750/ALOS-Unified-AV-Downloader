# Migrating from v2 to v3

v3 introduces the public name **ALOS Unified AV Downloader** and separates its
three workflows into ALOS Browse, ALOS Watch, and ALOS Headless.

## Name mapping

| v2 | v3 canonical name |
|---|---|
| Repository `JableTV-MissAV-Downloader-GUI-2026` | `ALOS-Unified-AV-Downloader` |
| Modern / `JableTV_Modern.exe` | ALOS Browse / `ALOS_Browse.exe` |
| SmallTool / `Jable_smalltool.exe` | ALOS Watch / `ALOS_Watch.exe` |
| SmallTool portable ZIP | `ALOS_Watch_portable.zip` |
| Docker/CLI | ALOS Headless |
| `ghcr.io/alos21750/jabletv` | `ghcr.io/alos21750/alos-unified-av-downloader` |

GitHub redirects the former repository URL. New documentation, update checks,
badges, source links, and container examples use only the canonical name.

## Existing installations

No uninstall is required. Download the v3 canonical executable and run it from
a writable folder. v3 copies compatible preferences, queue data, subtitle
settings, Watch selections, and Watch history into the new product locations.

Migration is intentionally non-destructive:

- Source files remain at the old location.
- Existing files at the new location are never overwritten.
- Symbolic links and directory junctions are not followed.
- A failed copy does not delete or modify the source.

The portable Watch state directory changes from `.Jable_smalltool` to
`.alos-watch`. The AppData root changes from `%APPDATA%\JableTV Downloader` to
`%APPDATA%\ALOS Unified AV Downloader`.

## Release and updater compatibility

Every v3 release publishes canonical assets. It also publishes these exact v2
aliases so installed v2 update clients continue to resolve a download:

- `JableTV_Modern.exe`
- `Jable_smalltool.exe`
- `Jable_smalltool_portable.zip`
- `Jable_reazonspeech_asr_v1.zip`

Each alias is a byte-for-byte copy of its corresponding canonical asset and is
listed independently in `SHA256SUMS.txt` and release attestations. New clients
prefer canonical names and can still read a legacy-only release.

The former GHCR image name is also published as a compatibility channel. New
deployments should use the canonical image so configuration and documentation
remain clear.
