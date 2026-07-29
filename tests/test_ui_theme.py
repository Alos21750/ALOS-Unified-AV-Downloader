import inspect
import re
import types
from pathlib import Path

import gui_modern
import jable_smalltool
import locales
import ui_theme


def _rgb(hex_color):
    return tuple(int(hex_color[index:index + 2], 16) / 255
                 for index in (1, 3, 5))


def _luminance(hex_color):
    channels = []
    for value in _rgb(hex_color):
        channels.append(value / 12.92 if value <= 0.04045
                        else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a, b):
    light, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_responsive_breakpoints_prioritize_readability():
    assert ui_theme.browse_columns_for_width(979) == 2
    assert ui_theme.browse_columns_for_width(1080) == 3
    assert ui_theme.browse_columns_for_width(1499) == 3
    assert ui_theme.browse_columns_for_width(1500) == 4
    assert ui_theme.category_columns_for_width(1119) == 2
    assert ui_theme.category_columns_for_width(1120) == 3


def test_shared_palette_is_valid_and_used_by_both_apps():
    tokens = (
        ui_theme.ACCENT, ui_theme.BG_DARK, ui_theme.BG_CARD,
        ui_theme.TEXT_PRI, ui_theme.TEXT_SEC, ui_theme.BORDER,
    )
    assert all(len(token) == 2 for token in tokens)
    assert all(re.fullmatch(r'#[0-9A-Fa-f]{6}', color)
               for token in tokens for color in token)
    assert gui_modern.ACCENT is ui_theme.ACCENT
    assert jable_smalltool.ACCENT is ui_theme.ACCENT


def test_primary_text_contrast_is_accessible_in_both_themes():
    for index in (0, 1):
        assert _contrast(ui_theme.TEXT_PRI[index], ui_theme.BG_DARK[index]) >= 7
        assert _contrast(ui_theme.TEXT_PRI[index], ui_theme.BG_CARD[index]) >= 7


def test_current_version_and_global_smalltool_copy_are_complete():
    assert gui_modern.APP_VERSION == jable_smalltool.APP_VERSION == '2.5.37'
    required = {
        'st_activity', 'st_progress_idle', 'st_footer_short',
        'st_categories_expand', 'st_categories_collapse',
        'st_scanning', 'st_downloading', 'st_scan_progress',
        'st_candidates_found',
        'st_calendar', 'st_date_quick', 'st_date_month_1',
        'st_date_month_2', 'st_folder_error',
        'st_version_preference', 'st_pref_chinese',
        'st_pref_uncensored', 'st_pref_standard',
        'st_pref_english', 'st_pref_reducing_mosaic',
        'st_settings_expand', 'st_settings_collapse',
        'st_activity_show', 'st_activity_hide',
        'st_schedule', 'st_schedule_title', 'st_schedule_interval',
        'st_schedule_hours', 'st_schedule_daily',
        'st_schedule_local_time', 'st_schedule_hint',
        'st_schedule_save', 'st_schedule_summary_interval',
        'st_schedule_summary_daily', 'st_schedule_invalid_hours',
        'st_schedule_invalid_time', 'st_schedule_saved',
        'st_scan_queued', 'st_waiting_schedule', 'st_stopping',
    }
    for language, strings in locales.STRINGS.items():
        assert strings['version_label'] == 'v2.5.37', language
        assert required <= strings.keys(), language


def test_windows_version_resources_match_app_version():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / '.github' / 'workflows' / 'windows-build.yml').read_text(
        encoding='utf-8')
    assert '$expected = "2.5.37.0"' in workflow
    generator = (root / 'build_tmp' / 'gen_version.py').read_text(
        encoding='utf-8')
    assert 'VERSION = (2, 5, 37, 0)' in generator
    for name in ('JableTV_Modern.version', 'Jable_smalltool.version'):
        resource = (root / 'build_tmp' / name).read_text(encoding='utf-8')
        assert 'filevers=(2, 5, 37, 0)' in resource
        assert "StringStruct('FileVersion', '2.5.37.0')" in resource
    for name in ('JableTV_Modern.spec', 'Jable_smalltool.spec'):
        spec = (root / 'build_tmp' / name).read_text(encoding='utf-8')
        assert "'numpy._core._exceptions'" in spec


def test_modern_defers_initial_workers_until_mainloop():
    init_source = inspect.getsource(gui_modern.ModernApp.__init__)
    assert 'self.after_idle(self._start_initial_background_tasks)' in init_source
    assert 'self._start_update_check(manual=False)' not in init_source

    app = gui_modern.ModernApp.__new__(gui_modern.ModernApp)
    calls = []
    app._is_closing = False
    app._start_update_check = lambda **kwargs: calls.append(('update', kwargs))
    app._load_categories = lambda: calls.append(('categories', {}))

    app._start_initial_background_tasks()

    assert calls == [('update', {'manual': False}), ('categories', {})]


def test_smalltool_balances_category_and_activity_regions():
    assert jable_smalltool.DEFAULT_WINDOW_WIDTH == 1180
    assert jable_smalltool.DEFAULT_WINDOW_HEIGHT == 780
    assert ui_theme.category_columns_for_width(
        jable_smalltool.DEFAULT_WINDOW_WIDTH) == 3

    source = inspect.getsource(jable_smalltool.SmallToolApp._build_ui)
    assert "main.pack(fill='both', expand=True" in source
    assert 'main.grid_columnconfigure(0, weight=1)' in source
    assert 'main.grid_rowconfigure(1, weight=1)' in source
    assert 'cfg_card.grid(row=0' in source
    assert 'selection.grid(row=1' in source
    assert 'ctrl.grid(row=2' in source
    assert 'prog_outer.grid(row=3' in source
    assert 'activity.grid(row=4' in source
    assert 'prog_outer.grid_remove()' in source
    assert 'activity.grid_remove()' in source

    collapse_source = inspect.getsource(
        jable_smalltool.SmallToolApp._set_categories_collapsed)
    assert '1, weight=0, minsize=0' in collapse_source
    assert '1, weight=1, minsize=0' in collapse_source

    start_source = inspect.getsource(
        jable_smalltool.SmallToolApp._start_worker)
    check_source = inspect.getsource(
        jable_smalltool.SmallToolApp._check_now)
    assert '_set_categories_collapsed(True)' not in start_source
    assert '_set_categories_collapsed(True)' not in check_source


def test_both_apps_expose_windows_proxy_mode_and_mode_aware_status():
    modern_ui = inspect.getsource(gui_modern.ModernApp._build_settings_tab)
    smalltool_ui = inspect.getsource(jable_smalltool.SmallToolApp._build_ui)
    for source in (modern_ui, smalltool_ui):
        assert "text=T('proxy_windows')" in source
        assert 'command=self._on_proxy_windows' in source

    for cls in (gui_modern.ModernApp, jable_smalltool.SmallToolApp):
        status_source = inspect.getsource(cls._refresh_proxy_status)
        assert "config.get_proxy_mode()" in status_source
        assert "config.refresh_system_proxy()" in status_source
        assert "T('proxy_windows_pac')" in status_source


def test_both_apps_expose_shared_recognition_quality_without_squeezing_copy():
    modern_ui = inspect.getsource(gui_modern.ModernApp._build_settings_tab)
    smalltool_ui = inspect.getsource(jable_smalltool.SmallToolApp._build_ui)

    assert 'self._recognition_quality_var = ctk.StringVar(' in modern_ui
    assert "wraplength=760" in modern_ui
    assert 'self._recognition_quality_var = tk.StringVar(' in smalltool_ui
    assert "wraplength=286" in smalltool_ui
    for source in (modern_ui, smalltool_ui):
        assert "T('recognition_quality_setting')" in source
        assert 'values=self._recognition_quality_values()' in source
        assert "T('recognition_quality_desc')" in source

    snapshot_source = inspect.getsource(
        jable_smalltool.SmallToolApp._snapshot_ui_state)
    restore_source = inspect.getsource(
        jable_smalltool.SmallToolApp._restore_ui_state)
    close_source = inspect.getsource(jable_smalltool.SmallToolApp._on_close)
    assert "'recognition_quality': config.get_recognition_quality()" in (
        snapshot_source)
    assert '_recognition_quality_label(' in restore_source
    assert "'recognition_quality'" not in close_source


def test_both_quality_selectors_persist_to_shared_config(monkeypatch):
    locales.set_lang('en')

    class _Var:
        def __init__(self):
            self.value = ''

        def set(self, value):
            self.value = value

    saved = []
    monkeypatch.setattr(
        gui_modern.config, 'set_recognition_quality',
        lambda value: saved.append(('modern', value)) or value)
    modern = gui_modern.ModernApp.__new__(gui_modern.ModernApp)
    modern._recognition_quality_var = _Var()
    modern._on_recognition_quality_change(
        locales.STRINGS['en']['recognition_quality_balanced'])

    monkeypatch.setattr(
        jable_smalltool.config, 'set_recognition_quality',
        lambda value: saved.append(('smalltool', value)) or value)
    smalltool = jable_smalltool.SmallToolApp.__new__(
        jable_smalltool.SmallToolApp)
    smalltool._recognition_quality_var = _Var()
    smalltool._on_recognition_quality_change(
        locales.STRINGS['en']['recognition_quality_fast'])

    assert saved == [('modern', 'balanced'), ('smalltool', 'fast')]
    assert modern._recognition_quality_var.value == 'Balanced'
    assert smalltool._recognition_quality_var.value == 'Fast'


def test_modern_concurrency_is_editable_persisted_and_clamped(monkeypatch):
    assert gui_modern.MAX_CONCURRENT == 32
    init_source = inspect.getsource(gui_modern.ModernApp.__init__)
    settings_source = inspect.getsource(
        gui_modern.ModernApp._build_settings_tab)
    footer_source = inspect.getsource(
        gui_modern.ModernApp._refresh_downloads)
    assert 'config.get_download_concurrency()' in init_source
    assert 'self._conc_entry = ctk.CTkEntry(' in settings_source
    assert "self._conc_entry.bind('<Return>'" in settings_source
    assert "'subtitle_queue_status'" in footer_source

    class _Var:
        def __init__(self, value):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    app = gui_modern.ModernApp.__new__(gui_modern.ModernApp)
    app._conc_var = _Var('99')
    app._dlmgr = types.SimpleNamespace(max_concurrent=2)
    saved = []

    def _save(value):
        saved.append(value)
        return max(1, min(int(value), 32))

    monkeypatch.setattr(gui_modern.config, 'set_download_concurrency', _save)
    app._on_conc_change()

    assert saved == [99]
    assert app._dlmgr.max_concurrent == 32
    assert app._conc_var.get() == '32'

    app._conc_var.set('invalid')
    app._on_conc_change()
    assert saved == [99]
    assert app._conc_var.get() == '32'


def test_global_version_selector_saves_internal_preference(monkeypatch):
    app = jable_smalltool.SmallToolApp.__new__(jable_smalltool.SmallToolApp)
    app._cfg = {}
    saved = []
    monkeypatch.setattr(
        jable_smalltool, 'update_config',
        lambda patch, **_kwargs: saved.append(dict(patch)))

    app._on_version_change(jable_smalltool.T('st_pref_uncensored'))

    assert app._cfg['version_preference'] == 'uncensored'
    assert saved[-1]['version_preference'] == 'uncensored'


def test_smalltool_selected_count_reflects_target_vars_only():
    app = jable_smalltool.SmallToolApp.__new__(jable_smalltool.SmallToolApp)
    captured = {}
    app._selected_count_lbl = types.SimpleNamespace(
        configure=lambda **kwargs: captured.update(kwargs))
    app._check_vars = {
        'JableTV|__group__|feeds': types.SimpleNamespace(get=lambda: True),
        'JableTV|feed:latest': types.SimpleNamespace(get=lambda: True),
        'MissAV|feed:latest': types.SimpleNamespace(get=lambda: False),
    }

    app._update_selected_count()

    assert captured['text'].startswith('1 ')
    assert captured['text_color'] is ui_theme.ACCENT
