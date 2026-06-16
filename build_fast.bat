@echo off
rem Fast development build. Reuses generated Qt files and Nuitka's C build cache.
rem Run build.bat when translations, resources, or qt_lupdate.json need regeneration.

uv run scripts\build_cached.py
