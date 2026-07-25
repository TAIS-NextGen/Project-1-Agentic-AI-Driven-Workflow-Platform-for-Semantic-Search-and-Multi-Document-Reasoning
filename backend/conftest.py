from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_system_binaries_in_path():
    candidates = [
        r"C:\Program Files\Tesseract-OCR",
    ]
    base = Path(os.environ.get("LOCALAPPDATA", ""))
    winget_pkgs = base / "Microsoft" / "WinGet" / "Packages"
    if winget_pkgs.exists():
        for d in winget_pkgs.iterdir():
            if d.is_dir() and d.name.startswith("oschwartz10612.Poppler_"):
                for sub in d.iterdir():
                    bin_dir = sub / "Library" / "bin"
                    if bin_dir.is_dir():
                        candidates.append(str(bin_dir))
                        break
    current = os.environ.get("PATH", "")
    for c in candidates:
        if os.path.isdir(c) and c not in current:
            os.environ["PATH"] = c + os.pathsep + current
            current = os.environ["PATH"]


_ensure_system_binaries_in_path()
