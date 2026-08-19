#!/usr/bin/env python3
"""Build the reproducible UAV Downloader local-translation model archive.

The archive is intentionally assembled with Python's standard library so an
already-converted model tree can be packaged without installing the conversion
toolchain.  Pass ``--convert`` to first download the immutable Hugging Face
revisions and convert them with the pinned CTranslate2 toolchain.

The ZIP uses stored entries, a fixed timestamp, stable POSIX metadata, and
lexicographic member ordering.  This avoids zlib-version differences and makes
the final archive byte-for-byte reproducible from identical input files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path
from typing import Iterable, Mapping


PACK_VERSION = "1"
# Preserve the v1 on-disk schema identifier so previously converted model
# trees remain verifiable; the public archive name is UAV_local_translation_v1.zip.
PACK_FORMAT = "jable-local-translation-pack"
CTRANSLATE2_VERSION = "4.8.1"
QUANTIZATION = "int8"
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
CONVERSION_PYTHON_VERSION = "3.12.10"
CONVERSION_MACHINE = "AMD64"

PINNED_CONVERSION_PACKAGES = {
    "certifi": "2026.7.22",
    "charset-normalizer": "3.4.9",
    "click": "8.4.2",
    "colorama": "0.4.6",
    "ctranslate2": CTRANSLATE2_VERSION,
    "filelock": "3.32.0",
    "fsspec": "2026.6.0",
    "huggingface-hub": "0.36.0",
    "idna": "3.18",
    "Jinja2": "3.1.6",
    "joblib": "1.5.3",
    "MarkupSafe": "3.0.3",
    "mpmath": "1.3.0",
    "networkx": "3.6.1",
    "numpy": "2.5.1",
    "packaging": "26.2",
    "PyYAML": "6.0.3",
    "regex": "2026.7.19",
    "requests": "2.34.2",
    "sacremoses": "0.1.1",
    "safetensors": "0.8.0",
    "sentencepiece": "0.2.2",
    "setuptools": "83.0.0",
    "sympy": "1.14.0",
    "tokenizers": "0.22.2",
    "torch": "2.9.1",
    "tqdm": "4.69.0",
    "transformers": "4.57.3",
    "typing_extensions": "4.16.0",
    "urllib3": "2.7.0",
}

BASE_RUNTIME_FILES = (
    "config.json",
    "model.bin",
    "shared_vocabulary.json",
    "source.spm",
    "target.spm",
)


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repository: str
    revision: str
    directory: str
    source_language: str
    target_language: str
    license_spdx: str
    license_archive_path: str
    extra_runtime_files: tuple[str, ...] = ()

    @property
    def source_url(self) -> str:
        return f"https://huggingface.co/{self.repository}/tree/{self.revision}"

    @property
    def archive_path(self) -> str:
        return f"models/{self.directory}"

    @property
    def runtime_files(self) -> tuple[str, ...]:
        return BASE_RUNTIME_FILES + self.extra_runtime_files


MODELS = (
    ModelSpec(
        key="ja-en",
        repository="staka/fugumt-ja-en",
        revision="f7ce11286e1fb7a8e1f1692ff3ab68c0f9c3aecb",
        directory="fugumt-ja-en-int8",
        source_language="ja",
        target_language="en",
        license_spdx="CC-BY-SA-4.0",
        license_archive_path=(
            "licenses/FuguMT-CC-BY-SA-4.0-NOTICE.txt"),
        extra_runtime_files=("vocab.json",),
    ),
    ModelSpec(
        key="en-zh",
        repository="Helsinki-NLP/opus-mt-en-zh",
        revision="408d9bc410a388e1d9aef112a2daba955b945255",
        directory="opus-mt-en-zh-int8",
        source_language="en",
        target_language="zh",
        license_spdx="Apache-2.0",
        license_archive_path="licenses/Apache-2.0.txt",
    ),
)


class PackBuildError(RuntimeError):
    """Raised for an invalid source tree or archive."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        separators=(",", ": "),
    )
    return (text + "\n").encode("utf-8")


def _require_regular_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise PackBuildError(f"Missing {description}: {path}")
    if path.is_symlink():
        raise PackBuildError(f"Refusing symlink for {description}: {path}")


def _check_conversion_toolchain() -> None:
    mismatches: list[str] = []
    if platform.python_version() != CONVERSION_PYTHON_VERSION:
        mismatches.append(
            f"CPython=={CONVERSION_PYTHON_VERSION} "
            f"(found {platform.python_version()})"
        )
    if sys.implementation.name != "cpython":
        mismatches.append(
            f"implementation==cpython (found {sys.implementation.name})"
        )
    if platform.machine().upper() != CONVERSION_MACHINE:
        mismatches.append(
            f"machine=={CONVERSION_MACHINE} (found {platform.machine()})"
        )
    if sys.maxsize <= 2**32:
        mismatches.append("architecture==64-bit (found 32-bit)")
    for distribution, expected in PINNED_CONVERSION_PACKAGES.items():
        try:
            actual = package_version(distribution)
        except PackageNotFoundError:
            actual = "<not installed>"
        if actual != expected:
            mismatches.append(f"{distribution}=={expected} (found {actual})")

    if mismatches:
        details = "\n  - ".join(mismatches)
        raise PackBuildError(
            "The --convert toolchain is not reproducible. Install the exact "
            f"versions below:\n  - {details}"
        )


def convert_models(
    converted_root: Path,
    *,
    cache_dir: Path | None,
    force: bool,
) -> None:
    """Download and convert both immutable model revisions."""

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(cache_dir.resolve())

    _check_conversion_toolchain()

    # Import only for --convert so packaging an existing tree stays stdlib-only.
    from ctranslate2.converters import TransformersConverter

    converted_root.mkdir(parents=True, exist_ok=True)
    for spec in MODELS:
        output_dir = converted_root / spec.directory
        if output_dir.exists() and not force:
            raise PackBuildError(
                f"Conversion target already exists: {output_dir}. "
                "Use --force-convert only when replacing this exact target."
            )

        converter = TransformersConverter(
            spec.repository,
            copy_files=[
                "README.md",
                "source.spm",
                "target.spm",
                *spec.extra_runtime_files,
            ],
            low_cpu_mem_usage=True,
            revision=spec.revision,
            trust_remote_code=False,
        )
        converter.convert(
            str(output_dir),
            quantization=QUANTIZATION,
            force=force,
        )


def _collect_payload(
    converted_root: Path,
    apache_license_file: Path,
    fugu_license_notice_file: Path,
) -> tuple[dict[str, bytes], dict[str, object]]:
    license_files = {
        "licenses/Apache-2.0.txt": apache_license_file,
        "licenses/FuguMT-CC-BY-SA-4.0-NOTICE.txt":
            fugu_license_notice_file,
    }
    for archive_path, source_path in license_files.items():
        _require_regular_file(source_path, f"license file {archive_path}")

    payload: dict[str, bytes] = {}
    model_manifest: dict[str, object] = {}

    for spec in MODELS:
        source_dir = converted_root / spec.directory
        if not source_dir.is_dir():
            raise PackBuildError(f"Missing converted model directory: {source_dir}")

        runtime_archive_paths: list[str] = []
        for filename in spec.runtime_files:
            source_path = source_dir / filename
            _require_regular_file(
                source_path,
                f"{spec.key} runtime file {filename}",
            )
            archive_path = f"{spec.archive_path}/{filename}"
            payload[archive_path] = source_path.read_bytes()
            runtime_archive_paths.append(archive_path)

        source_card = source_dir / "README.md"
        _require_regular_file(source_card, f"{spec.key} upstream model card")
        card_path = f"{spec.archive_path}/MODEL_CARD.md"
        payload[card_path] = source_card.read_bytes()

        model_manifest[spec.key] = {
            "conversion": {
                "quantization": QUANTIZATION,
                "tool": "CTranslate2",
                "version": CTRANSLATE2_VERSION,
            },
            "license": spec.license_spdx,
            "license_path": spec.license_archive_path,
            "model_card": card_path,
            "path": spec.archive_path,
            "revision": spec.revision,
            "runtime_files": runtime_archive_paths,
            "source_language": spec.source_language,
            "source_repository": spec.repository,
            "source_url": spec.source_url,
            "target_language": spec.target_language,
        }

    for archive_path, source_path in license_files.items():
        payload[archive_path] = source_path.read_bytes()

    file_manifest = [
        {
            "path": path,
            "sha256": _sha256_bytes(payload[path]),
            "size": len(payload[path]),
        }
        for path in sorted(payload)
    ]

    manifest: dict[str, object] = {
        "files": file_manifest,
        "format": PACK_FORMAT,
        "licenses": [
            {
                "path": archive_path,
                "spdx": (
                    "Apache-2.0"
                    if archive_path.endswith("Apache-2.0.txt")
                    else "CC-BY-SA-4.0"
                ),
            }
            for archive_path in sorted(license_files)
        ],
        "models": model_manifest,
        "pack_version": PACK_VERSION,
        "provenance": {
            "conversion_environment": {
                "architecture": "64-bit",
                "implementation": "CPython",
                "machine": CONVERSION_MACHINE,
                "python": CONVERSION_PYTHON_VERSION,
            },
            "conversion_toolchain": dict(
                sorted(PINNED_CONVERSION_PACKAGES.items())
            ),
            "model_revisions_are_immutable": True,
            "modifications": [
                "Converted from the pinned Transformers checkpoints.",
                "Weights quantized to CTranslate2 int8; no fine-tuning applied.",
            ],
        },
        "schema_version": 2,
    }
    return payload, manifest


def _zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build_archive(
    converted_root: Path,
    output: Path,
    apache_license_file: Path,
    fugu_license_notice_file: Path,
) -> Mapping[str, object]:
    """Create and verify a deterministic archive."""

    payload, manifest = _collect_payload(
        converted_root,
        apache_license_file,
        fugu_license_notice_file,
    )
    entries = dict(payload)
    entries["manifest.json"] = _canonical_json(manifest)

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)

        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as archive:
            for archive_path in sorted(entries):
                archive.writestr(_zip_info(archive_path), entries[archive_path])

        # Never replace a known-good artifact until the complete candidate has
        # passed the same structural and per-file integrity checks.
        verify_archive(temporary)
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return {
        "archive": str(output),
        "sha256": _sha256_file(output),
        "size": output.stat().st_size,
    }


def _validate_manifest_paths(
    members: Iterable[str],
    manifest: Mapping[str, object],
) -> None:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise PackBuildError("manifest.json files must be an array")

    expected_members = {"manifest.json"}
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise PackBuildError("manifest.json contains an invalid file entry")
        path = entry["path"]
        _validate_archive_path(path)
        if path in expected_members:
            raise PackBuildError(f"Duplicate manifest file entry: {path}")
        size = entry.get("size")
        digest = entry.get("sha256")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise PackBuildError(f"Invalid manifest file size: {path}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise PackBuildError(f"Invalid manifest SHA-256: {path}")
        expected_members.add(path)

    actual_members = set(members)
    if actual_members != expected_members:
        missing = sorted(expected_members - actual_members)
        extra = sorted(actual_members - expected_members)
        raise PackBuildError(
            f"Archive member mismatch; missing={missing}, extra={extra}"
        )


def _validate_archive_path(path: str) -> None:
    if (
        not path
        or "\\" in path
        or path.startswith("/")
        or ":" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise PackBuildError(f"Unsafe archive member path: {path!r}")


def _validate_manifest_contract(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema_version") != 2:
        raise PackBuildError("Archive manifest has an unsupported schema")
    models = manifest.get("models")
    if not isinstance(models, dict):
        raise PackBuildError("Archive manifest models must be an object")
    expected_keys = {spec.key for spec in MODELS}
    if set(models) != expected_keys:
        raise PackBuildError("Archive manifest model set is invalid")

    for spec in MODELS:
        model = models.get(spec.key)
        if not isinstance(model, dict):
            raise PackBuildError(f"Archive model entry is invalid: {spec.key}")
        expected = {
            "conversion": {
                "quantization": QUANTIZATION,
                "tool": "CTranslate2",
                "version": CTRANSLATE2_VERSION,
            },
            "license": spec.license_spdx,
            "license_path": spec.license_archive_path,
            "model_card": f"{spec.archive_path}/MODEL_CARD.md",
            "path": spec.archive_path,
            "revision": spec.revision,
            "runtime_files": [
                f"{spec.archive_path}/{filename}"
                for filename in spec.runtime_files
            ],
            "source_language": spec.source_language,
            "source_repository": spec.repository,
            "source_url": spec.source_url,
            "target_language": spec.target_language,
        }
        if model != expected:
            raise PackBuildError(
                f"Archive model contract is invalid: {spec.key}")

    expected_licenses = [
        {"path": "licenses/Apache-2.0.txt", "spdx": "Apache-2.0"},
        {
            "path": "licenses/FuguMT-CC-BY-SA-4.0-NOTICE.txt",
            "spdx": "CC-BY-SA-4.0",
        },
    ]
    if manifest.get("licenses") != expected_licenses:
        raise PackBuildError("Archive manifest license inventory is invalid")


def _json_object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackBuildError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def verify_archive(path: Path) -> None:
    """Verify member order, metadata, and all manifest content hashes."""

    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if archive.comment:
            raise PackBuildError("Archive has a non-reproducible comment")
        if len(infos) > 4096:
            raise PackBuildError("Archive contains too many members")
        if sum(info.file_size for info in infos) > 300 * 1024 * 1024:
            raise PackBuildError("Archive payload is unexpectedly large")
        if names != sorted(names):
            raise PackBuildError("Archive entries are not lexicographically ordered")
        if len(names) != len(set(names)):
            raise PackBuildError("Archive contains duplicate member names")

        for info in infos:
            _validate_archive_path(info.filename)
            if info.date_time != FIXED_ZIP_TIMESTAMP:
                raise PackBuildError(
                    f"Archive member has a non-reproducible timestamp: {info.filename}"
                )
            if info.compress_type != zipfile.ZIP_STORED:
                raise PackBuildError(
                    f"Archive member is unexpectedly compressed: {info.filename}"
                )
            if (
                info.create_system != 3
                or (info.external_attr >> 16) != 0o100644
                or info.flag_bits != 0
                or info.extra
                or info.comment
            ):
                raise PackBuildError(
                    f"Archive member has non-reproducible metadata: {info.filename}"
                )

        try:
            manifest = json.loads(
                archive.read("manifest.json"),
                object_pairs_hook=_json_object_without_duplicates,
            )
        except KeyError as exc:
            raise PackBuildError("Archive is missing manifest.json") from exc
        except json.JSONDecodeError as exc:
            raise PackBuildError("Archive manifest.json is invalid JSON") from exc

        if not isinstance(manifest, dict):
            raise PackBuildError("Archive manifest.json must contain an object")
        if manifest.get("format") != PACK_FORMAT:
            raise PackBuildError("Archive manifest has an unsupported format")
        if manifest.get("pack_version") != PACK_VERSION:
            raise PackBuildError("Archive manifest has an unsupported pack version")
        _validate_manifest_contract(manifest)

        _validate_manifest_paths(names, manifest)
        for entry in manifest["files"]:
            data = archive.read(entry["path"])
            if len(data) != entry.get("size"):
                raise PackBuildError(
                    f"Size mismatch for archive member: {entry['path']}"
                )
            if _sha256_bytes(data) != entry.get("sha256"):
                raise PackBuildError(
                    f"SHA-256 mismatch for archive member: {entry['path']}"
                )

        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            raise PackBuildError(f"CRC check failed for: {corrupt_member}")


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--converted-root",
        type=Path,
        default=Path(r"C:\jable_build\translation_ct2_int8_v1"),
        help="Directory containing the two converted model directories.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(r"C:\jable_build\UAV_local_translation_v1.zip"),
        help="Destination ZIP archive.",
    )
    parser.add_argument(
        "--license-file",
        type=Path,
        default=_default_repo_root() / "LICENSE",
        help="Apache License 2.0 text to include in the archive.",
    )
    parser.add_argument(
        "--fugu-license-notice-file",
        type=Path,
        default=(
            _default_repo_root()
            / "third_party_licenses"
            / "FuguMT-CC-BY-SA-4.0-NOTICE.txt"
        ),
        help="FuguMT attribution and CC BY-SA 4.0 notice.",
    )
    parser.add_argument(
        "--convert",
        action="store_true",
        help="Download pinned revisions and run the CTranslate2 converter first.",
    )
    parser.add_argument(
        "--force-convert",
        action="store_true",
        help="Allow --convert to replace only the two exact model targets.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(r"C:\jable_build\hf_cache"),
        help="Hugging Face cache used only with --convert.",
    )
    parser.add_argument(
        "--verify-only",
        type=Path,
        help="Verify an existing archive instead of building one.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.verify_only is not None:
            archive = args.verify_only.resolve()
            verify_archive(archive)
            result = {
                "archive": str(archive),
                "sha256": _sha256_file(archive),
                "size": archive.stat().st_size,
                "verified": True,
            }
        else:
            if args.force_convert and not args.convert:
                raise PackBuildError("--force-convert requires --convert")
            if args.convert:
                convert_models(
                    args.converted_root.resolve(),
                    cache_dir=args.cache_dir.resolve(),
                    force=args.force_convert,
                )
            result = build_archive(
                args.converted_root.resolve(),
                args.output,
                args.license_file.resolve(),
                args.fugu_license_notice_file.resolve(),
            )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, PackBuildError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
