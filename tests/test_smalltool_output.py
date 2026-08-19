import json

from alos_downloader.apps import watch as jable_smalltool


def test_blank_saved_folder_falls_back_to_tmp_beside_app(monkeypatch, tmp_path):
    app_dir = tmp_path / 'portable'
    state_dir = tmp_path / 'state'
    state_dir.mkdir()
    config_path = state_dir / 'config.json'
    config_path.write_text(json.dumps({
        'output_folder': '',
        'selected_targets': [],
    }), encoding='utf-8')

    monkeypatch.setattr(jable_smalltool, 'APP_DIR', str(app_dir))
    monkeypatch.setattr(jable_smalltool, 'STATE_DIR', str(state_dir))
    monkeypatch.setattr(jable_smalltool, 'CONFIG_PATH', str(config_path))

    cfg = jable_smalltool.load_config()

    assert cfg['output_folder'] == str(app_dir / 'tmp')
    assert cfg['version_preference'] == 'chinese-subtitle'
    assert 'missav_version_preference' not in cfg


def test_missing_config_uses_tmp_beside_app(monkeypatch, tmp_path):
    app_dir = tmp_path / 'portable'
    state_dir = tmp_path / 'state'
    monkeypatch.setattr(jable_smalltool, 'APP_DIR', str(app_dir))
    monkeypatch.setattr(jable_smalltool, 'STATE_DIR', str(state_dir))
    monkeypatch.setattr(
        jable_smalltool, 'CONFIG_PATH', str(state_dir / 'missing.json'))

    cfg = jable_smalltool.load_config()

    assert cfg['output_folder'] == str(app_dir / 'tmp')
    assert cfg['version_preference'] == 'chinese-subtitle'


def test_old_missav_preference_is_migrated_to_global_setting(
        monkeypatch, tmp_path):
    state_dir = tmp_path / 'state'
    state_dir.mkdir()
    config_path = state_dir / 'config.json'
    config_path.write_text(json.dumps({
        'output_folder': str(tmp_path),
        'missav_version_preference': 'uncensored-leak',
    }), encoding='utf-8')
    monkeypatch.setattr(jable_smalltool, 'STATE_DIR', str(state_dir))
    monkeypatch.setattr(jable_smalltool, 'CONFIG_PATH', str(config_path))

    cfg = jable_smalltool.load_config()

    assert cfg['version_preference'] == 'uncensored'
    assert 'missav_version_preference' not in cfg
