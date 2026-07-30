from pathlib import Path

from scripts import build_reazonspeech_asr_pack as builder


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github' / 'workflows' / 'windows-build.yml'

PACK_NAME = 'Jable_reazonspeech_asr_v1.zip'
PACK_SIZE = 186_185_998
PACK_SHA256 = (
    '64ed98f3779ba9aca5c271e4b03e4bed6ac74cfaadb3a8d69854dc4f234a729e'
)
MANIFEST_SHA256 = (
    'f7e7c4675a4186786d8490e9881796e61ab611a953398605de88fd26a5082181'
)


def test_windows_ci_builds_only_the_pinned_reazonspeech_inputs():
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert builder.SHERPA_COMMIT in workflow
    assert builder.REAZON_MODEL_REVISION in workflow
    assert builder.ONNX_RUNTIME_COMMIT in workflow
    assert builder.SHERPA_RELEASE_ARCHIVE_SHA256 in workflow
    assert str(builder.SHERPA_RELEASE_ARCHIVE_SIZE) in workflow

    for size, sha256 in (
        *builder.RUNTIME_FILES.values(),
        *builder.MODEL_FILES.values(),
        *builder.LICENSE_FILES.values(),
    ):
        assert str(size) in workflow
        assert sha256 in workflow

    lowered = workflow.lower()
    for mutable_source in (
        '/latest/',
        '/resolve/main/',
        '/resolve/master/',
        'raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/',
        'raw.githubusercontent.com/microsoft/onnxruntime/main/',
    ):
        assert mutable_source not in lowered
    assert 'Assert-PinnedFile' in workflow
    assert 'scripts/build_reazonspeech_asr_pack.py' in workflow


def test_windows_ci_gates_attests_and_uploads_the_exact_pack():
    workflow = WORKFLOW.read_text(encoding='utf-8')

    assert str(PACK_SIZE) in workflow
    assert PACK_SHA256 in workflow
    assert MANIFEST_SHA256 in workflow
    assert workflow.count(PACK_NAME) >= 5
    assert '"Jable_reazonspeech_asr_v1.zip"' in workflow
    assert 'dist/Jable_reazonspeech_asr_v1.zip' in workflow
    assert 'actions/attest@v4' in workflow
    assert 'compression-level: 0' in workflow


def test_reazonspeech_notices_pin_sources_and_explain_mixed_licensing():
    notices = (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
    security = (ROOT / 'WINDOWS_SECURITY.md').read_text(encoding='utf-8')

    assert PACK_NAME in notices
    assert 'mixed-license' in notices
    assert builder.REAZON_MODEL_REVISION in notices
    assert builder.SHERPA_COMMIT in notices
    assert builder.ONNX_RUNTIME_COMMIT in notices
    assert 'licenses/Apache-2.0.txt' in notices
    assert 'licenses/ONNXRuntime-MIT.txt' in notices
    assert 'licenses/ONNXRuntime-ThirdPartyNotices.txt' in notices
    assert PACK_NAME in security
    assert f'gh attestation verify .\\{PACK_NAME}' in security
