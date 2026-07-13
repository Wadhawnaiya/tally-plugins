from __future__ import annotations

import os
import shutil
from pathlib import Path

DEFAULT_INSTALL_DIR = Path(r"C:\Program Files\TallyPrime")
DEFAULT_PORT = 9000


def normalize_install_dir(path: str | os.PathLike[str] | None = None) -> Path:
    """Resolve a TallyPrime install directory without requiring it to exist."""
    candidate = path or os.environ.get("TALLYPRIME_HOME") or os.environ.get("TALLY_HOME")
    if candidate:
        return Path(candidate).expanduser()
    exe = shutil.which("tally.exe") or shutil.which("tally")
    if exe:
        return Path(exe).resolve().parent
    return DEFAULT_INSTALL_DIR


def parse_tally_ini(path: str | os.PathLike[str]) -> dict[str, str]:
    """Parse Tally's loose INI format while preserving keys containing spaces."""
    ini_path = Path(path)
    settings: dict[str, str] = {}
    if not ini_path.exists():
        return settings
    for raw_line in ini_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


def read_settings(install_dir: str | os.PathLike[str] | None = None) -> dict[str, str]:
    return parse_tally_ini(normalize_install_dir(install_dir) / "tally.ini")


def server_port(settings: dict[str, str] | None = None, default: int = DEFAULT_PORT) -> int:
    value = (settings or {}).get("ServerPort", "").strip()
    if not value:
        return default
    try:
        port = int(value)
    except ValueError:
        return default
    if 1 <= port <= 65535:
        return port
    return default
