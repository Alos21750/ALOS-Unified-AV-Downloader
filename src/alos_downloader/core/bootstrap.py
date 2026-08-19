"""Early frozen-runtime guards shared by both Windows entry points."""

from __future__ import annotations

import os
import ssl


_ENV_ALIASES = {
    "whisper_input": (
        "ALOS_WHISPER_DIAGNOSTIC_INPUT",
        "JABLE_WHISPER_DIAGNOSTIC_INPUT",
    ),
    "whisper_output": (
        "ALOS_WHISPER_DIAGNOSTIC_OUTPUT",
        "JABLE_WHISPER_DIAGNOSTIC_OUTPUT",
    ),
    "local_output": (
        "ALOS_LOCAL_TRANSLATION_DIAGNOSTIC_OUTPUT",
        "JABLE_LOCAL_TRANSLATION_DIAGNOSTIC_OUTPUT",
    ),
    "local_soak_output": (
        "ALOS_LOCAL_TRANSLATION_SOAK_DIAGNOSTIC_OUTPUT",
        "JABLE_LOCAL_TRANSLATION_SOAK_DIAGNOSTIC_OUTPUT",
    ),
    "llm_output": (
        "ALOS_LLM_TRANSLATION_DIAGNOSTIC_OUTPUT",
        "JABLE_LLM_TRANSLATION_DIAGNOSTIC_OUTPUT",
    ),
}


def _environment_value(key: str):
    for name in _ENV_ALIASES[key]:
        if name in os.environ:
            return os.environ.get(name)
    return None


def install_ssl_guard() -> None:
    """Install the ASCII-safe certifi path before curl_cffi is imported."""
    try:
        import certifi

        ca_path = certifi.where()
        if not ca_path or not os.path.exists(ca_path):
            return
        os.environ.setdefault("SSL_CERT_FILE", ca_path)
        os.environ.setdefault("SSL_CERT_DIR", os.path.dirname(ca_path))
        try:
            ssl.get_default_verify_paths()
        except (UnicodeDecodeError, SystemError):
            defaults = ssl.DefaultVerifyPaths(
                ca_path,
                os.path.dirname(ca_path),
                "SSL_CERT_FILE",
                ca_path,
                "SSL_CERT_DIR",
                os.path.dirname(ca_path),
            )
            ssl.get_default_verify_paths = lambda: defaults
    except Exception:
        pass


def install_crash_logger() -> None:
    try:
        from alos_downloader.core import crashlog

        crashlog.install()
    except Exception:
        pass


def install_runtime_guards() -> None:
    install_ssl_guard()
    install_crash_logger()


def _checked_output_path(value: str, *, remove_stale: bool = True) -> str:
    output_path = os.path.abspath(value.strip())
    if (
        os.path.isdir(output_path)
        or not os.path.isdir(os.path.dirname(output_path))
    ):
        raise FileNotFoundError("diagnostic output directory is unavailable")
    if remove_stale:
        try:
            os.remove(output_path)
        except FileNotFoundError:
            pass
    return output_path


def _run_output_diagnostic(value: str, function_name: str) -> None:
    try:
        output_path = _checked_output_path(value)
        from alos_downloader.subtitles import engine

        getattr(engine, function_name)(output_path)
        if not os.path.isfile(output_path):
            raise RuntimeError("diagnostic did not produce its report")
    except (Exception, SystemExit):
        raise SystemExit(2) from None
    raise SystemExit(0)


def run_translation_diagnostic_if_requested() -> None:
    """Run a machine-consumed diagnostic before any GUI imports.

    ALOS-prefixed environment names are canonical.  Every JABLE-prefixed name
    remains accepted so existing frozen acceptance tooling keeps working.
    """
    whisper_input = _environment_value("whisper_input")
    whisper_output = _environment_value("whisper_output")
    if whisper_input is not None or whisper_output is not None:
        if not (
            whisper_input
            and whisper_input.strip()
            and whisper_output
            and whisper_output.strip()
        ):
            raise SystemExit(2)
        try:
            input_path = os.path.abspath(whisper_input)
            output_path = _checked_output_path(
                whisper_output,
                remove_stale=False,
            )
            if os.path.normcase(input_path) == os.path.normcase(output_path):
                raise ValueError("diagnostic input and output must differ")
            if not os.path.isfile(input_path):
                raise FileNotFoundError("diagnostic input is not a file")
            try:
                os.remove(output_path)
            except FileNotFoundError:
                pass
            from alos_downloader.subtitles.engine import run_whisper_diagnostic

            run_whisper_diagnostic(input_path, output_path)
            if not os.path.isfile(output_path):
                raise RuntimeError("diagnostic did not produce its report")
        except (Exception, SystemExit):
            raise SystemExit(2) from None
        raise SystemExit(0)

    local_output = _environment_value("local_output")
    if local_output:
        _run_output_diagnostic(
            local_output,
            "run_local_translation_diagnostic",
        )

    local_soak_output = _environment_value("local_soak_output")
    if local_soak_output:
        _run_output_diagnostic(
            local_soak_output,
            "run_local_translation_worker_soak_diagnostic",
        )

    llm_output = _environment_value("llm_output")
    if llm_output:
        _run_output_diagnostic(llm_output, "run_llm_translation_diagnostic")
