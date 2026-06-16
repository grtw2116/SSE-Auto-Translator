"""
Copyright (c) Cutleast

Wrapper around scripts/build.py that keeps Nuitka's intermediate C build folder
between runs. This lets MSVC and Nuitka reuse unchanged compilation output, which
is the expensive part of repeated standalone builds.

Set SSE_AT_CLEAN_NUITKA_CACHE=1 to force a clean Nuitka build.
"""

import logging
import os
import runpy
import shutil
from pathlib import Path

from cutleast_core_lib.builder.backends.nuitka_backend import NuitkaBackend

_LEGACY_CACHE_DIR = Path(".nuitka_build_cache")
_log = logging.getLogger("BuildCache")

_original_build = NuitkaBackend.build


def _remove_nuitka_remove_output_arg() -> None:
    """
    Prevent Nuitka from deleting main.build before it can reuse cached objects.
    """

    NuitkaBackend.BASE_ARGS = [
        arg for arg in NuitkaBackend.BASE_ARGS if arg != "--remove-output"
    ]


def _restore_legacy_cache(build_folder: Path) -> None:
    """
    Restores the old .nuitka_build_cache/main.build cache once, if it exists.
    """

    legacy_cache = _LEGACY_CACHE_DIR / build_folder.name
    if not build_folder.is_dir() and legacy_cache.is_dir():
        _log.info("[cache] Restoring legacy cache '%s'...", legacy_cache)
        shutil.copytree(legacy_cache, build_folder)


def _patched_build(self, main_module: Path, exe_stem, icon_path, metadata):
    build_folder = Path(main_module.stem + ".build")

    if os.environ.get("SSE_AT_CLEAN_NUITKA_CACHE") == "1":
        _log.info("[cache] Removing cached Nuitka build folder '%s'...", build_folder)
        shutil.rmtree(build_folder, ignore_errors=True)
    else:
        _restore_legacy_cache(build_folder)
        if build_folder.is_dir():
            _log.info("[cache] Reusing Nuitka build folder '%s'.", build_folder)
        else:
            _log.info("[cache] No Nuitka build folder found; full build required.")

    return _original_build(self, main_module, exe_stem, icon_path, metadata)


def _patched_clean(self, main_module: Path, exe_stem: str) -> None:
    build_folder = Path(main_module.stem + ".build")
    dist_folder = Path(main_module.stem + ".dist")

    shutil.rmtree(dist_folder, ignore_errors=True)

    if os.environ.get("SSE_AT_CLEAN_NUITKA_CACHE") == "1":
        shutil.rmtree(build_folder, ignore_errors=True)
        _log.info("[cache] Cleaned Nuitka build cache.")
    elif build_folder.is_dir():
        (build_folder / ".gitignore").write_text("*")
        _log.info("[cache] Preserved Nuitka build cache '%s'.", build_folder)


_remove_nuitka_remove_output_arg()
NuitkaBackend.build = _patched_build  # type: ignore[method-assign]
NuitkaBackend.clean = _patched_clean  # type: ignore[method-assign]

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    runpy.run_path("scripts/build.py", run_name="__main__")
