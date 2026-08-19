"""ALOS Watch entry point.

Runtime guards and machine-consumed diagnostics run before importing Tk or the
site resolver, which is required by the frozen Windows verification workflow.
"""

from __future__ import annotations

import multiprocessing

from alos_downloader.core.bootstrap import (
    install_runtime_guards,
    run_translation_diagnostic_if_requested,
)


if __name__ == "__main__":
    multiprocessing.freeze_support()

install_runtime_guards()


def main():
    run_translation_diagnostic_if_requested()
    from alos_downloader.apps.watch import main as app_main

    return app_main()


if __name__ == "__main__":
    main()
