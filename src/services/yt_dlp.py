from __future__ import annotations

import os
from pathlib import Path
from shutil import which

if os.name == "nt":
    import winreg


def get_preferred_js_runtime() -> str | None:
    """Return the preferred yt-dlp JS runtime available on the machine."""
    for runtime in ("deno", "node"):
        if find_executable(runtime) is not None:
            return runtime
    return None


def get_remote_component_args() -> list[str]:
    """Return remote component arguments used as a fallback for EJS scripts."""
    return ["--remote-components", "ejs:github"]


def get_ffmpeg_location() -> str | None:
    """Return the ffmpeg bin directory when ffmpeg is available."""
    ffmpeg_path = find_executable("ffmpeg")
    if ffmpeg_path is None:
        return None
    return str(Path(ffmpeg_path).parent)


def build_subprocess_env() -> dict[str, str]:
    """Return an environment with PATH merged from current, user, and machine scopes."""
    env = os.environ.copy()
    env["PATH"] = _build_merged_path(env.get("PATH", ""))
    return env


def find_executable(name: str) -> str | None:
    """Locate an executable using both the current PATH and persisted Windows PATH values."""
    merged_path = _build_merged_path(os.environ.get("PATH", ""))
    return which(name, path=merged_path)


def _build_merged_path(current_path: str) -> str:
    path_entries = _split_path_entries(current_path)
    path_entries.extend(_split_path_entries(_get_windows_path("User")))
    path_entries.extend(_split_path_entries(_get_windows_path("Machine")))

    unique_entries: list[str] = []
    seen_entries: set[str] = set()

    for entry in path_entries:
        normalized_entry = entry.strip()
        if not normalized_entry:
            continue
        key = normalized_entry.lower()
        if key in seen_entries:
            continue
        seen_entries.add(key)
        unique_entries.append(normalized_entry)

    return os.pathsep.join(unique_entries)


def _split_path_entries(path_value: str | None) -> list[str]:
    if not path_value:
        return []
    return path_value.split(os.pathsep)


def _get_windows_path(scope: str) -> str:
    if os.name != "nt":
        return ""

    registry_hive, registry_key = _get_registry_target(scope)

    try:
        with winreg.OpenKey(registry_hive, registry_key) as key:
            path_value, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        return ""

    return str(path_value)


def _get_registry_target(scope: str) -> tuple[int, str]:
    if scope == "User":
        return (winreg.HKEY_CURRENT_USER, r"Environment")
    return (
        winreg.HKEY_LOCAL_MACHINE,
        r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
    )
