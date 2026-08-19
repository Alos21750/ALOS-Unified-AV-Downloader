# ALOS Headless: Docker and CLI

ALOS Headless downloads supported URLs without a desktop interface. It is a
run-to-completion job for Docker hosts, NAS systems, servers, and scripts.

## Docker

The canonical multi-architecture image is:

```text
ghcr.io/alos21750/alos-unified-av-downloader:latest
```

GitHub Actions publishes Linux amd64 and arm64 manifests. The legacy
`ghcr.io/alos21750/jabletv` image name remains an exact compatibility channel.

Download one URL:

```bash
docker run --rm \
  -v "/path/to/downloads:/downloads" \
  ghcr.io/alos21750/alos-unified-av-downloader:latest \
  "https://jable.tv/videos/example/"
```

With Compose:

```bash
docker compose run --rm alos "https://jable.tv/videos/example/"
```

To process a list, write one URL per line to `./downloads/urls.txt`, then run:

```bash
docker compose run --rm alos
```

Supported environment variables:

| Variable | Purpose |
|---|---|
| `DOWNLOAD_DIR` | Container destination; default `/downloads` |
| `URL` / `URLS` | One or more URLs |
| `URLS_FILE` | Mounted URL list; default `/downloads/urls.txt` |
| `RESOLUTION` | `highest`, `1080`, `720`, `480`, `360`, or `lowest` |
| `MAX_WORKERS_PER_VIDEO` | Segment-worker limit from 1–16 |

## Installed commands

After an editable or package installation:

```bash
alos-headless "https://jable.tv/videos/example/"
alos-browse --nogui --url "https://jable.tv/videos/example/" -o ./download
```

The first command follows the Docker-style URL and environment interface. The
second exposes the classic arguments shared with ALOS Browse.
