# author: ALOS (Alos21750)
#!/usr/bin/env python
# coding: utf-8

import ctypes
import sys

# --- issue #23: on some Windows machines the OpenSSL/cert default path contains
# non-UTF-8 bytes, so ssl.get_default_verify_paths() raises (UnicodeDecodeError ->
# SystemError) and crashes curl_cffi at import time. Point SSL/curl_cffi at certifi's
# ASCII-safe bundle BEFORE anything imports curl_cffi, and harden the function. ---
import os as _os, ssl as _ssl
try:
    import certifi as _certifi
    _ca = _certifi.where()
    if _ca and _os.path.exists(_ca):
        _os.environ.setdefault('SSL_CERT_FILE', _ca)
        _os.environ.setdefault('SSL_CERT_DIR', _os.path.dirname(_ca))
        try:
            _ssl.get_default_verify_paths()
        except (UnicodeDecodeError, SystemError):
            _dvp = _ssl.DefaultVerifyPaths(_ca, _os.path.dirname(_ca),
                                           'SSL_CERT_FILE', _ca,
                                           'SSL_CERT_DIR', _os.path.dirname(_ca))
            _ssl.get_default_verify_paths = lambda: _dvp
except Exception:
    pass

# --- issue #24: install a global crash logger so an uncaught exception (which
# otherwise just makes the pythonw window vanish silently) is written to
# crash_log.txt next to the exe + shown in a copyable dialog, so users can report it. ---
try:
    import crashlog
    crashlog.install()
except Exception:
    pass


def _run_translation_diagnostic_if_requested():
    whisper_input = _os.environ.get(
        'JABLE_WHISPER_DIAGNOSTIC_INPUT')
    whisper_output = _os.environ.get(
        'JABLE_WHISPER_DIAGNOSTIC_OUTPUT')
    if whisper_input is not None or whisper_output is not None:
        if not (whisper_input and whisper_input.strip()
                and whisper_output and whisper_output.strip()):
            raise SystemExit(2)
        try:
            input_path = _os.path.abspath(whisper_input)
            output_path = _os.path.abspath(whisper_output)
            if _os.path.normcase(input_path) == _os.path.normcase(output_path):
                raise ValueError('diagnostic input and output must differ')
            if not _os.path.isfile(input_path):
                raise FileNotFoundError('diagnostic input is not a file')
            if (_os.path.isdir(output_path)
                    or not _os.path.isdir(_os.path.dirname(output_path))):
                raise FileNotFoundError(
                    'diagnostic output directory is unavailable')
            try:
                _os.remove(output_path)
            except FileNotFoundError:
                pass
            from subtitle_engine import run_whisper_diagnostic
            run_whisper_diagnostic(input_path, output_path)
            if not _os.path.isfile(output_path):
                raise RuntimeError('diagnostic did not produce its report')
        except (Exception, SystemExit):
            # Frozen verification is machine-consumed.  Keep failures
            # deterministic and never echo media paths, transcripts, or keys.
            raise SystemExit(2) from None
        raise SystemExit(0)

    local_output = _os.environ.get(
        'JABLE_LOCAL_TRANSLATION_DIAGNOSTIC_OUTPUT', '')
    if local_output:
        try:
            output_path = _os.path.abspath(local_output.strip())
            if (_os.path.isdir(output_path)
                    or not _os.path.isdir(_os.path.dirname(output_path))):
                raise FileNotFoundError(
                    'diagnostic output directory is unavailable')
            try:
                _os.remove(output_path)
            except FileNotFoundError:
                pass
            from subtitle_engine import run_local_translation_diagnostic
            run_local_translation_diagnostic(output_path)
            if not _os.path.isfile(output_path):
                raise RuntimeError('diagnostic did not produce its report')
        except (Exception, SystemExit):
            raise SystemExit(2) from None
        raise SystemExit(0)

    llm_output = _os.environ.get(
        'JABLE_LLM_TRANSLATION_DIAGNOSTIC_OUTPUT', '')
    if llm_output:
        try:
            output_path = _os.path.abspath(llm_output.strip())
            if (_os.path.isdir(output_path)
                    or not _os.path.isdir(_os.path.dirname(output_path))):
                raise FileNotFoundError(
                    'diagnostic output directory is unavailable')
            try:
                _os.remove(output_path)
            except FileNotFoundError:
                pass
            from subtitle_engine import run_llm_translation_diagnostic
            run_llm_translation_diagnostic(output_path)
            if not _os.path.isfile(output_path):
                raise RuntimeError('diagnostic did not produce its report')
        except (Exception, SystemExit):
            raise SystemExit(2) from None
        raise SystemExit(0)


if __name__ == '__main__':
    _run_translation_diagnostic_if_requested()

# Enable DPI awareness BEFORE any Tk/GUI imports
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-monitor V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from args import *

# Use modern CustomTkinter GUI by default; fall back to basic tkinter if unavailable
try:
    from gui_modern import gui_modern_main as _gui_main
    _USE_MODERN = True
except ImportError:
    from gui import gui_main as _gui_main
    _USE_MODERN = False

''' Default folder to save the download files
    "" or None : same as the url's last stem,  ie:  "abc-001" for url = "https://jable.tv/videos/abc-001/"
    others : relative to the current folder, or an absolute path  
    '''
save_folder = "download"


if __name__ == "__main__":
    url_arg = ""
    parser = get_parser()
    args = parser.parse_args()

    if len(args.url) != 0:
        url_arg = args.url
    elif args.random:
        url_arg = av_recommand() or ""   # None (site changed/blocked) -> empty, not a crash

    if args.nogui:
        M3U8Sites.consoles_main(url_arg, save_folder)
    elif _USE_MODERN:
        _gui_main(url_arg, save_folder)
    else:
        from gui import gui_main
        gui_main(url_arg, save_folder)

    sys.exit(0)
