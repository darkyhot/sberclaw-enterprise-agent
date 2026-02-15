"""Execute Python scripts that belong to skills directories."""

from __future__ import annotations

import io
import os
from contextlib import redirect_stdout


class ScriptExecutionTool:
    """Runs Python scripts from skills/*/scripts/ with optional input text."""

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.skills_root = os.path.abspath(os.path.join(self.root_dir, "skills"))
        os.makedirs(self.skills_root, exist_ok=True)

    def _resolve_skill_script(self, script_path: str) -> str:
        full = os.path.abspath(os.path.join(self.root_dir, script_path))
        if full.startswith(self.skills_root + os.sep) and full.endswith(".py"):
            return full
        raise ValueError("Script path must be a Python file under skills/")

    def run_script(self, script_path: str, script_input: str = "") -> str:
        """Execute a skill Python script and capture stdout."""
        full = self._resolve_skill_script(script_path)
        with open(full, "r", encoding="utf-8") as f:
            code = f.read()

        namespace = {"__name__": "__main__", "INPUT": script_input}
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                exec(compile(code, full, "exec"), namespace, namespace)
            text = output.getvalue().strip()
            return text or "Script executed successfully."
        except Exception as exc:  # pylint: disable=broad-except
            return f"Script execution error: {exc}"
