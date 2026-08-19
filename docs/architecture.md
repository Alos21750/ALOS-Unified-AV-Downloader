# Architecture and source layout

ALOS Unified AV Downloader uses a `src` layout so runtime packages, build
files, documentation, and tests have explicit boundaries.

```text
src/alos_downloader/
  apps/          ALOS Browse and ALOS Watch desktop applications
  cli/           ALOS Headless and command-line argument handling
  core/          configuration, paths, migration, SSL, updater, crash logging
  entrypoints/   Windows and installed application entrypoints
  i18n/          application strings and site labels
  legacy/        supported fallback UI kept outside the primary applications
  sites/         shared crawler contract and per-site implementations
  subtitles/     recognition, translation, LLM, settings, and provenance
  ui/            shared theme and settings components
packaging/windows/
  PyInstaller specifications and Windows version resources
scripts/
  deterministic build and repository-maintenance automation
tools/
  manual development and screenshot utilities
tests/
  unit, integration, regression, packaging, and migration contracts
docs/
  user and contributor documentation plus visual assets
```

## Public entrypoints

- `alos-browse` → `alos_downloader.entrypoints.browse:main`
- `alos-watch` → `alos_downloader.entrypoints.watch:main`
- `alos-headless` → `alos_downloader.cli.headless:main`

Both Windows entrypoints install shared runtime guards before importing GUI or
subtitle dependencies. This keeps SSL certificate setup, crash reporting, and
the frozen translation diagnostic consistent.

## Site boundary

`alos_downloader.sites` owns the current registry and exposes canonical
`validate_url` and `create_site` functions. Misspelled v2 aliases remain only
as compatibility shims. Each supported site implementation shares the crawler
contract, quality preference, proxy settings, naming rules, and download
worker limits.

## Persistence boundary

New user data belongs under `ALOS Unified AV Downloader`; legacy locations are
read only as migration sources. Migration is copy-only, skips links, never
deletes old data, and never overwrites a file already present at the new
location.

## Release boundary

Windows release bytes are produced by pinned CI and then verified as the same
bytes through artifact download, release upload, checksums, and attestations.
Canonical v3 assets and legacy aliases are both generated from that one build.
