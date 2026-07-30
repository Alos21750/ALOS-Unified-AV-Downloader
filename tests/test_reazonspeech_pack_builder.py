import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts import build_reazonspeech_asr_pack as builder


def _expected(data):
    return len(data), hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _small_inputs(tmp_path, monkeypatch):
    runtime_dir = tmp_path / 'runtime'
    model_dir = tmp_path / 'model'
    license_dir = tmp_path / 'licenses'

    runtime = {
        'sherpa-onnx-offline.exe': b'pinned sherpa runtime',
        'onnxruntime.dll': b'pinned onnx runtime',
        'onnxruntime_providers_shared.dll': b'pinned providers runtime',
    }
    model = {
        'tokens.txt': b'<blk> 0\n',
        'encoder-epoch-99-avg-1.int8.onnx': b'pinned encoder',
        'decoder-epoch-99-avg-1.onnx': b'pinned decoder',
        'joiner-epoch-99-avg-1.int8.onnx': b'pinned joiner',
        'README.md': b'pinned model card',
    }
    licenses = {
        'licenses/Apache-2.0.txt':
            b'Apache License\nVersion 2.0\nfixture',
        'licenses/ONNXRuntime-MIT.txt': b'MIT License\nfixture',
        'licenses/ONNXRuntime-ThirdPartyNotices.txt':
            b'THIRD PARTY SOFTWARE NOTICES AND INFORMATION\nfixture',
    }

    for name, data in runtime.items():
        _write(runtime_dir / name, data)
    for name, data in model.items():
        _write(model_dir / name, data)
    license_sources = {
        'licenses/Apache-2.0.txt':
            _write(license_dir / 'Apache-2.0.txt', licenses[
                'licenses/Apache-2.0.txt']),
        'licenses/ONNXRuntime-MIT.txt':
            _write(license_dir / 'ONNXRuntime-MIT.txt', licenses[
                'licenses/ONNXRuntime-MIT.txt']),
        'licenses/ONNXRuntime-ThirdPartyNotices.txt':
            _write(license_dir / 'ONNXRuntime-ThirdPartyNotices.txt', licenses[
                'licenses/ONNXRuntime-ThirdPartyNotices.txt']),
    }

    monkeypatch.setattr(
        builder, 'RUNTIME_FILES',
        {name: _expected(data) for name, data in runtime.items()})
    monkeypatch.setattr(
        builder, 'MODEL_FILES',
        {name: _expected(data) for name, data in model.items()})
    monkeypatch.setattr(
        builder, 'LICENSE_FILES',
        {name: _expected(data) for name, data in licenses.items()})

    return (
        runtime_dir,
        model_dir,
        license_sources['licenses/Apache-2.0.txt'],
        license_sources['licenses/ONNXRuntime-MIT.txt'],
        license_sources[
            'licenses/ONNXRuntime-ThirdPartyNotices.txt'],
    )


def _build(inputs, output):
    return builder.build_pack(*inputs, output)


def test_pack_is_byte_reproducible_and_records_mixed_licenses(
        tmp_path, monkeypatch):
    inputs = _small_inputs(tmp_path, monkeypatch)
    first = tmp_path / 'first.zip'
    second = tmp_path / 'second.zip'

    first_result = _build(inputs, first)
    second_result = _build(inputs, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_result == second_result
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        manifest_bytes = archive.read('manifest.json')
        manifest = json.loads(manifest_bytes.decode('utf-8'))
        assert names == ['manifest.json', *sorted(names[1:])]
        assert all(
            info.date_time == builder.FIXED_ZIP_TIMESTAMP
            and info.compress_type == zipfile.ZIP_STORED
            for info in archive.infolist()
        )

    assert manifest['format'] == builder.PACK_FORMAT
    assert manifest['license'] == 'mixed'
    assert {item['license'] for item in manifest['licenses']} == {
        'Apache-2.0', 'MIT',
    }
    assert manifest['model']['license'] == 'Apache-2.0'
    assert manifest['runtime']['license'] == 'Apache-2.0'
    assert manifest['runtime']['onnx_runtime']['license'] == 'MIT'
    assert (
        manifest['runtime']['onnx_runtime']['third_party_notices_path']
        == 'licenses/ONNXRuntime-ThirdPartyNotices.txt'
    )
    assert first_result[2] == hashlib.sha256(manifest_bytes).hexdigest()


def test_pack_rejects_tampered_pinned_input(tmp_path, monkeypatch):
    inputs = _small_inputs(tmp_path, monkeypatch)
    (inputs[1] / 'tokens.txt').write_bytes(b'tampered')

    with pytest.raises(builder.PackBuildError, match='failed verification'):
        _build(inputs, tmp_path / 'pack.zip')


def test_pack_rejects_a_hash_pinned_but_invalid_license(
        tmp_path, monkeypatch):
    inputs = _small_inputs(tmp_path, monkeypatch)
    invalid = b'not a license'
    inputs[3].write_bytes(invalid)
    expected = dict(builder.LICENSE_FILES)
    expected['licenses/ONNXRuntime-MIT.txt'] = _expected(invalid)
    monkeypatch.setattr(builder, 'LICENSE_FILES', expected)

    with pytest.raises(builder.PackBuildError, match='MIT license text'):
        _build(inputs, tmp_path / 'pack.zip')


def test_pack_rejects_unsafe_archive_path(tmp_path, monkeypatch):
    inputs = _small_inputs(tmp_path, monkeypatch)
    data = b'escape'
    _write(tmp_path / 'escape.exe', data)
    monkeypatch.setattr(
        builder, 'RUNTIME_FILES', {'../escape.exe': _expected(data)})

    with pytest.raises(builder.PackBuildError, match='Unsafe archive path'):
        _build(inputs, tmp_path / 'pack.zip')


def test_pack_never_overwrites_a_pinned_input(tmp_path, monkeypatch):
    inputs = _small_inputs(tmp_path, monkeypatch)
    runtime = inputs[0] / 'sherpa-onnx-offline.exe'
    original = runtime.read_bytes()

    with pytest.raises(builder.PackBuildError, match='must not overwrite'):
        _build(inputs, runtime)

    assert runtime.read_bytes() == original
