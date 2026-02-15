"""CSV utility tool using pandas."""

from __future__ import annotations

import os

import pandas as pd


class CSVTool:
    """Read basic CSV metadata and previews."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.projects_root = os.path.abspath(os.path.join(self.root_dir, "projects"))
        os.makedirs(self.projects_root, exist_ok=True)

    def _resolve_project_file(self, path: str) -> str:
        full = os.path.abspath(os.path.join(self.root_dir, path))
        if full == self.projects_root or full.startswith(self.projects_root + os.sep):
            return full
        raise ValueError("CSVTool can access files only under projects/")

    def csv_preview(self, path: str, rows: int = 5) -> str:
        full = self._resolve_project_file(path)
        frame = pd.read_csv(full)
        return frame.head(rows).to_string(index=False)

    def csv_columns(self, path: str) -> str:
        full = self._resolve_project_file(path)
        frame = pd.read_csv(full)
        return ", ".join(frame.columns.tolist())
