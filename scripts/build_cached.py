"""
Copyright (c) Cutleast

Wrapper around scripts/build.py that preserves Nuitka's intermediate build
folder (.nuitka_build_cache/) between runs to speed up incremental compilation.

On the first run the cache is empty and build time is identical to build.py.
On subsequent runs, unchanged modules skip C recompilation — typically 50–80%
faster when only source files changed.

Usage (from the project root):
    python scripts/build_cached.py
"""

import logging
import runpy
import shutil
from pathlib import Path

from cutleast_core_lib.builder.backends.nuitka_backend import NuitkaBackend

_CACHE_DIR = Path(".nuitka_build_cache")
_log = logging.getLogger("BuildCache")

_original_build = NuitkaBackend.build
_original_clean = NuitkaBackend.clean


def _patched_build(self, main_module: Path, exe_stem, icon_path, metadata):
    # Restore app.build/ from cache before Nuitka starts so MSVC can reuse .obj files.
    build_folder = Path(main_module.stem + ".build")
    cached = _CACHE_DIR / build_folder.name
    if cached.is_dir() and not build_folder.is_dir():
        _log.info(f"[cache] Restoring '{build_folder}' from '{cached}'...")
        shutil.copytree(cached, build_folder)
    else:
        _log.info("[cache] No cached build folder found — performing full build.")
    return _original_build(self, main_module, exe_stem, icon_path, metadata)


def _patched_clean(self, main_module: Path, exe_stem: str) -> None:
    # Save app.build/ to cache before the library deletes it.
    build_folder = Path(main_module.stem + ".build")
    if build_folder.is_dir():
        cached = _CACHE_DIR / build_folder.name
        _CACHE_DIR.mkdir(exist_ok=True)
        if cached.is_dir():
            shutil.rmtree(cached)
        _log.info(f"[cache] Saving '{build_folder}' to '{cached}'...")
        shutil.copytree(build_folder, cached)
    _original_clean(self, main_module, exe_stem)


NuitkaBackend.build = _patched_build  # type: ignore[method-assign]
NuitkaBackend.clean = _patched_clean  # type: ignore[method-assign]

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    runpy.run_path("scripts/build.py", run_name="__main__")
