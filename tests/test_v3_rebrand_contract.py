"""Public product and repository contracts for the v3 rebrand.

These tests intentionally describe the finished migration rather than an
intermediate file layout.  They protect existing v2 users while the public
product becomes ALOS Unified AV Downloader.
"""

from pathlib import Path

from alos_downloader import metadata
from alos_downloader.core import crashlog
from alos_downloader.core import paths


ROOT = Path(__file__).resolve().parents[1]


def test_product_identity_and_release_channels_are_centralized():
    assert metadata.PRODUCT_NAME == "ALOS Unified AV Downloader"
    assert metadata.VERSION == "3.0.0"
    assert metadata.GITHUB_REPOSITORY == (
        "Alos21750/ALOS-Unified-AV-Downloader"
    )
    assert metadata.APP_DISPLAY_NAMES == {
        "browse": "ALOS Browse",
        "watch": "ALOS Watch",
        "headless": "ALOS Headless",
    }


def test_release_asset_candidates_keep_every_v2_updater_working():
    assert metadata.release_asset_candidates("browse") == (
        "ALOS_Browse.exe",
        "JableTV_Modern.exe",
    )
    assert metadata.release_asset_candidates("watch") == (
        "ALOS_Watch.exe",
        "Jable_smalltool.exe",
    )
    assert metadata.release_asset_candidates("watch-portable") == (
        "ALOS_Watch_portable.zip",
        "Jable_smalltool_portable.zip",
    )


def test_legacy_user_data_is_copied_without_destroying_or_overwriting(tmp_path):
    legacy = tmp_path / "JableTV Downloader"
    current = tmp_path / metadata.PRODUCT_NAME
    (legacy / "smalltool").mkdir(parents=True)
    (legacy / "ui_prefs.json").write_text("legacy-prefs", encoding="utf-8")
    (legacy / "smalltool" / "seen.json").write_text(
        "legacy-seen", encoding="utf-8"
    )
    current.mkdir()
    (current / "ui_prefs.json").write_text("current-prefs", encoding="utf-8")

    report = paths.migrate_directory(legacy, current)

    assert (current / "ui_prefs.json").read_text(encoding="utf-8") == (
        "current-prefs"
    )
    assert (current / "smalltool" / "seen.json").read_text(
        encoding="utf-8"
    ) == "legacy-seen"
    assert (legacy / "smalltool" / "seen.json").is_file()
    assert report.copied_files == 1
    assert report.skipped_files == 1


def test_portable_watch_state_migrates_to_new_hidden_directory(tmp_path):
    legacy = tmp_path / ".Jable_smalltool"
    current = tmp_path / ".alos-watch"
    legacy.mkdir()
    (legacy / "config.json").write_text("{}", encoding="utf-8")

    selected = paths.select_portable_state_dir(tmp_path)

    assert selected == current
    assert (current / "config.json").is_file()
    assert (legacy / "config.json").is_file()


def test_runtime_source_uses_a_src_package_instead_of_root_modules():
    assert (ROOT / "pyproject.toml").is_file()
    assert (ROOT / "src" / "alos_downloader" / "__init__.py").is_file()
    assert list(ROOT.glob("*.py")) == []


def test_crash_reports_use_the_v3_product_identity():
    source = (ROOT / "src" / "alos_downloader" / "core" / "crashlog.py").read_text(
        encoding="utf-8"
    )
    assert crashlog._app_version() == metadata.VERSION
    assert "JableTV crash log" not in source
    assert "JableTV native-fault log" not in source
    assert "ALOS — Crash" in source
