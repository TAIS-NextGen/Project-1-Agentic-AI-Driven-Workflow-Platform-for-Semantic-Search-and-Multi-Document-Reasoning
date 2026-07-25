from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "data/storage"))


class StorageService:
    def __init__(self, base_dir: str | Path = STORAGE_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, key: str, data: bytes) -> str:
        file_path = self.base_dir / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        return str(file_path)

    async def read(self, key: str) -> bytes:
        file_path = self.base_dir / key
        if not file_path.exists():
            raise FileNotFoundError(f"File '{key}' not found in storage")
        return file_path.read_bytes()

    async def delete(self, key: str) -> bool:
        file_path = self.base_dir / key
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        if not self.base_dir.exists():
            return []
        keys = []
        for f in self.base_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(self.base_dir).as_posix()
                if rel.startswith(prefix):
                    keys.append(rel)
        return keys

    async def exists(self, key: str) -> bool:
        return (self.base_dir / key).exists()
