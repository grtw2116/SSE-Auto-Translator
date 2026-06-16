"""
Copyright (c) Cutleast

Smoke-test for the build cache mechanism in build_cached.py.
Replaces NuitkaBackend with a lightweight simulation so no actual
compilation is required.

Usage (from the project root):
    python scripts/test_build_cache.py
"""

import importlib.util
import shutil
from pathlib import Path

from cutleast_core_lib.builder.backends.nuitka_backend import NuitkaBackend

# --Mock: replace Nuitka with a simulation ────────────────────────────────────

_build_folder_existed_before_build = False
"""Set by the mock to record whether app.build/ was already present when Nuitka started."""


def _mock_build(self, main_module, exe_stem, icon_path, metadata):
    global _build_folder_existed_before_build
    build_folder = Path(main_module.stem + ".build")
    _build_folder_existed_before_build = build_folder.is_dir()
    build_folder.mkdir(exist_ok=True)
    (build_folder / "module.obj").write_text("compiled object")
    return Path(main_module.stem + ".dist")


def _mock_clean(self, main_module, exe_stem):
    shutil.rmtree(Path(main_module.stem + ".build"), ignore_errors=True)
    shutil.rmtree(Path(main_module.stem + ".dist"), ignore_errors=True)


NuitkaBackend.build = _mock_build  # type: ignore[method-assign]
NuitkaBackend.clean = _mock_clean  # type: ignore[method-assign]

# --Load build_cached (wraps our mocks; __main__ guard skips actual build) ────

spec = importlib.util.spec_from_file_location(
    "build_cached", Path(__file__).parent / "build_cached.py"
)
mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(mod)  # type: ignore[union-attr]

# --Test fixtures ─────────────────────────────────────────────────────────────

backend = NuitkaBackend()
fake_main = Path("app.py")
cache_dir = Path(".nuitka_build_cache")
build_folder = Path("app.build")

PASS = "✓"
FAIL = "✗"


def assert_eq(label: str, actual: bool, expected: bool) -> None:
    mark = PASS if actual == expected else FAIL
    print(f"  {mark} {label}: {actual}")
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


# --Run tests ─────────────────────────────────────────────────────────────────

try:
    fake_main.touch()

    # -- Run 1: no cache yet --------------------------------------------------
    print("Run 1 (cold - no cache):")

    backend.build(fake_main, "SSE-AT", None, None)
    assert_eq("app.build/ created by build", build_folder.is_dir(), True)
    assert_eq("app.build/ was NOT pre-existing (no cache restored)", _build_folder_existed_before_build, False)

    backend.clean(fake_main, "SSE-AT")
    assert_eq("cache saved to .nuitka_build_cache/", (cache_dir / "app.build").is_dir(), True)
    assert_eq("app.build/ removed after clean", build_folder.is_dir(), False)

    # -- Run 2: cache present -------------------------------------------------
    print("Run 2 (warm - cache restored):")

    backend.build(fake_main, "SSE-AT", None, None)
    assert_eq("app.build/ was pre-existing (cache restored)", _build_folder_existed_before_build, True)
    assert_eq("cached file present in restored build folder", (build_folder / "module.obj").exists(), True)

    backend.clean(fake_main, "SSE-AT")
    assert_eq("cache updated after second clean", (cache_dir / "app.build").is_dir(), True)
    assert_eq("app.build/ removed after second clean", build_folder.is_dir(), False)

    print("\nAll tests passed.")

finally:
    fake_main.unlink(missing_ok=True)
    shutil.rmtree(build_folder, ignore_errors=True)
    shutil.rmtree(cache_dir, ignore_errors=True)
