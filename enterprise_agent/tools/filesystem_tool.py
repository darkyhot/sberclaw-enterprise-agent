"""Filesystem tool with strict path controls."""

from __future__ import annotations

import os
from typing import List


class FileSystemTool:
    """Read/write operations restricted to projects/ and skills/."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.allowed_roots = [
            os.path.abspath(os.path.join(self.root_dir, "projects")),
            os.path.abspath(os.path.join(self.root_dir, "skills")),
        ]
        for allowed in self.allowed_roots:
            os.makedirs(allowed, exist_ok=True)

    def _resolve_path(self, path: str) -> str:
        full = os.path.abspath(os.path.join(self.root_dir, path))
        for allowed in self.allowed_roots:
            if full == allowed or full.startswith(allowed + os.sep):
                return full
        raise ValueError("Access denied. Allowed roots: projects/ and skills/")

    def create_directory(self, name: str) -> str:
        full = self._resolve_path(name)
        os.makedirs(full, exist_ok=True)
        return f"Directory created: {name}"

    def write_file(self, path: str, content: str) -> str:
        full = self._resolve_path(path)
        parent = os.path.dirname(full)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"File written: {path}"

    def read_file(self, path: str) -> str:
        full = self._resolve_path(path)
        with open(full, "r", encoding="utf-8") as f:
            return f.read()

    def list_directory(self, path: str) -> List[str]:
        full = self._resolve_path(path)
        if not os.path.exists(full):
            return []
        return sorted(os.listdir(full))
