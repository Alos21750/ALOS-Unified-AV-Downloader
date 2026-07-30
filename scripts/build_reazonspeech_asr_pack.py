#!/usr/bin/env python3
"""Build the reproducible CPU-only ReazonSpeech ASR runtime pack.

The source runtime and model archives are official upstream release assets.
This script intentionally repackages only the three Windows runtime files and
the hybrid INT8/FP32 Japanese model files used by Jable. It never downloads
mutable files at application runtime and never includes the much larger
all-FP32 model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACK_VERSION = "1"
PACK_FORMAT = "jable-reazonspeech-asr-pack"
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

SHERPA_VERSION = "v1.13.4"
SHERPA_COMMIT = "142807252687d81b40d6315f23470a1512a00de3"
SHERPA_RELEASE_ARCHIVE = (
    "sherpa-onnx-v1.13.4-win-x64-shared-MT-MinSizeRel-no-tts.tar.bz2"
)
SHERPA_RELEASE_ARCHIVE_SIZE = 19_828_790
SHERPA_RELEASE_ARCHIVE_SHA256 = (
    "a2a0e9e8e69446f59620a4837fdfff7041bc5d745b2a4260f41083b9f563ea59"
)
SHERPA_RELEASE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"{SHERPA_VERSION}/{SHERPA_RELEASE_ARCHIVE}"
)

REAZON_MODEL_REVISION = "291488c8151be24d7da4bf7af26e533fad96e407"
REAZON_MODEL_SOURCE_URL = (
    "https://huggingface.co/reazon-research/reazonspeech-k2-v2/tree/"
    f"{REAZON_MODEL_REVISION}"
)
REAZON_MODEL_FILE_URL_PREFIX = (
    "https://huggingface.co/reazon-research/reazonspeech-k2-v2/resolve/"
    f"{REAZON_MODEL_REVISION}/"
)
REAZON_MODEL_CARD_URL = REAZON_MODEL_FILE_URL_PREFIX + "README.md"
ONNX_RUNTIME_VERSION = "1.27.0"
ONNX_RUNTIME_COMMIT = "8f0278c77bf44b0cc83c098c6c722b92a36ac4b5"

RUNTIME_FILES = {
    "sherpa-onnx-offline.exe": (
        2_117_120,
        "5ea3f02ee15e1af3fbf786568dd3f5ed85e67b302883e4cb763cf8ec2c93bb5a",
    ),
    "onnxruntime.dll": (
        14_438_400,
        "7813cfb15cbcd05c567776a055806920924f2543cfbe1f38850e3bb1410e62bd",
    ),
    "onnxruntime_providers_shared.dll": (
        104_960,
        "cf52b931b9a76cde2290f654dbad81f037b5de19f75c0a34ec82ebdaf4a555d8",
    ),
}

MODEL_FILES = {
    "tokens.txt": (
        45_754,
        "2c3ac659818a48a0c04010e0593bbc4d7c8a24a054340b01131499c05fd52def",
    ),
    "encoder-epoch-99-avg-1.int8.onnx": (
        154_670_139,
        "2c7bd08a8a99f9ddd0d9e458456577b1f6279214e51426f114f9eced44c54e1d",
    ),
    "decoder-epoch-99-avg-1.onnx": (
        11_767_836,
        "58b18211ae06265466bfa17172dab574df94f76c8bcb61a3640c28ba860e4124",
    ),
    "joiner-epoch-99-avg-1.int8.onnx": (
        2_696_970,
        "49cc7ea1d3d35a40a27442db5e89996da64bf0e683a903dce76e99e57a12e4de",
    ),
    "README.md": (
        1_188,
        "7debad4c9430f3310ad6d119fce385787c1c19f3ebc0cabe685a48dbe72a4de0",
    ),
}

LICENSE_FILES = {
    "licenses/Apache-2.0.txt": (
        11_358,
        "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    ),
    "licenses/ONNXRuntime-MIT.txt": (
        1_073,
        "2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c",
    ),
    "licenses/ONNXRuntime-ThirdPartyNotices.txt": (
        325_054,
        "0e07b95f3a8d6230037707c5c4a2b554d12c4cb67369669ac255635528ffcee2",
    ),
}


class PackBuildError(RuntimeError):
    """Raised when an input cannot reproduce the pinned pack."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_verified(path: Path, expected: tuple[int, str]) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise PackBuildError(f"Missing regular input file: {path}")
    data = path.read_bytes()
    size, sha256 = expected
    if len(data) != size or _sha256_bytes(data) != sha256:
        raise PackBuildError(f"Pinned input failed verification: {path}")
    return data


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            separators=(",", ": "),
        )
        + "\n"
    ).encode("utf-8")


def _validate_archive_path(value: str) -> None:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PackBuildError(f"Unsafe archive path: {value!r}")


def build_pack(
    runtime_dir: Path,
    model_dir: Path,
    apache_license: Path,
    onnx_license: Path,
    onnx_third_party_notices: Path,
    output: Path,
) -> tuple[int, str, str]:
    output_arg = output
    if output_arg.is_symlink():
        raise PackBuildError(f"Output must not be a symbolic link: {output_arg}")

    license_sources = {
        "licenses/Apache-2.0.txt": apache_license,
        "licenses/ONNXRuntime-MIT.txt": onnx_license,
        "licenses/ONNXRuntime-ThirdPartyNotices.txt":
            onnx_third_party_notices,
    }
    source_paths = [
        *(runtime_dir / name for name in RUNTIME_FILES),
        *(model_dir / name for name in MODEL_FILES),
        *license_sources.values(),
    ]
    resolved_output = output_arg.resolve()
    if resolved_output in {path.resolve() for path in source_paths}:
        raise PackBuildError("Output must not overwrite a pinned input file")

    payload: dict[str, bytes] = {}
    for name, expected in RUNTIME_FILES.items():
        archive_path = f"runtime/{name}"
        _validate_archive_path(archive_path)
        payload[archive_path] = _read_verified(
            runtime_dir / name, expected
        )
    for name, expected in MODEL_FILES.items():
        archive_name = "MODEL_CARD.md" if name == "README.md" else name
        archive_path = f"model/{archive_name}"
        _validate_archive_path(archive_path)
        payload[archive_path] = _read_verified(
            model_dir / name, expected
        )

    for archive_path, expected in LICENSE_FILES.items():
        _validate_archive_path(archive_path)
        payload[archive_path] = _read_verified(
            license_sources[archive_path], expected
        )
    if (
        b"Apache License" not in payload["licenses/Apache-2.0.txt"]
        or b"Version 2.0" not in payload["licenses/Apache-2.0.txt"]
    ):
        raise PackBuildError("Apache-2.0 license text is invalid")
    if b"MIT License" not in payload["licenses/ONNXRuntime-MIT.txt"]:
        raise PackBuildError("ONNX Runtime MIT license text is invalid")
    if (
        b"THIRD PARTY SOFTWARE NOTICES AND INFORMATION"
        not in payload["licenses/ONNXRuntime-ThirdPartyNotices.txt"]
    ):
        raise PackBuildError("ONNX Runtime third-party notices are invalid")

    files = [
        {
            "path": path,
            "sha256": _sha256_bytes(payload[path]),
            "size": len(payload[path]),
        }
        for path in sorted(payload)
    ]
    manifest = {
        "files": files,
        "format": PACK_FORMAT,
        "license": "mixed",
        "licenses": [
            {
                "applies_to": [
                    "model/**",
                    "runtime/sherpa-onnx-offline.exe",
                ],
                "license": "Apache-2.0",
                "path": "licenses/Apache-2.0.txt",
            },
            {
                "applies_to": [
                    "runtime/onnxruntime.dll",
                    "runtime/onnxruntime_providers_shared.dll",
                ],
                "license": "MIT",
                "path": "licenses/ONNXRuntime-MIT.txt",
                "third_party_notices_path":
                    "licenses/ONNXRuntime-ThirdPartyNotices.txt",
            },
        ],
        "model": {
            "architecture": "Zipformer RNN-T",
            "files": {
                ("MODEL_CARD.md" if name == "README.md" else name):
                    REAZON_MODEL_FILE_URL_PREFIX + name
                for name in MODEL_FILES
            },
            "model_card_url": REAZON_MODEL_CARD_URL,
            "path": "model",
            "quantization": "INT8 encoder/joiner with FP32 decoder",
            "repository": "reazon-research/reazonspeech-k2-v2",
            "revision": REAZON_MODEL_REVISION,
            "source_url": REAZON_MODEL_SOURCE_URL,
            "license": "Apache-2.0",
            "license_path": "licenses/Apache-2.0.txt",
        },
        "pack_version": PACK_VERSION,
        "runtime": {
            "archive": SHERPA_RELEASE_ARCHIVE,
            "archive_sha256": SHERPA_RELEASE_ARCHIVE_SHA256,
            "archive_size": SHERPA_RELEASE_ARCHIVE_SIZE,
            "archive_url": SHERPA_RELEASE_URL,
            "commit": SHERPA_COMMIT,
            "onnx_runtime": {
                "commit": ONNX_RUNTIME_COMMIT,
                "license": "MIT",
                "license_path": "licenses/ONNXRuntime-MIT.txt",
                "third_party_notices_path":
                    "licenses/ONNXRuntime-ThirdPartyNotices.txt",
                "version": ONNX_RUNTIME_VERSION,
            },
            "path": "runtime",
            "repository": "k2-fsa/sherpa-onnx",
            "version": SHERPA_VERSION,
            "license": "Apache-2.0",
            "license_path": "licenses/Apache-2.0.txt",
        },
    }
    manifest_bytes = _canonical_json(manifest)

    output = resolved_output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.is_symlink():
        raise PackBuildError(
            f"Temporary output must not be a symbolic link: {temporary}"
        )
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as archive:
            for name, data in [
                ("manifest.json", manifest_bytes),
                *sorted(payload.items()),
            ]:
                info = zipfile.ZipInfo(name, FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = (
                    stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR
                    | stat.S_IRGRP | stat.S_IROTH
                ) << 16
                archive.writestr(info, data)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()

    archive_bytes = output.read_bytes()
    return (
        len(archive_bytes),
        _sha256_bytes(archive_bytes),
        _sha256_bytes(manifest_bytes),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--apache-license", type=Path, required=True)
    parser.add_argument("--onnx-license", type=Path, required=True)
    parser.add_argument(
        "--onnx-third-party-notices", type=Path, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    size, archive_sha256, manifest_sha256 = build_pack(
        args.runtime_dir,
        args.model_dir,
        args.apache_license,
        args.onnx_license,
        args.onnx_third_party_notices,
        args.output,
    )
    print(
        json.dumps(
            {
                "archive_sha256": archive_sha256,
                "archive_size": size,
                "manifest_sha256": manifest_sha256,
                "output": str(args.output.resolve()),
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
