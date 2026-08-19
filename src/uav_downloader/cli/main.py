"""Default installed command: the headless downloader."""

from __future__ import annotations

from .headless import main


if __name__ == "__main__":
    raise SystemExit(main())
