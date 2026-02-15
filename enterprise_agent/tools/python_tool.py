"""Python execution tool for controlled code evaluation."""

from __future__ import annotations

import io
from contextlib import redirect_stdout


class PythonTool:
    """Execute Python snippets and return stdout or errors."""

    def run_python(self, code: str) -> str:
        local_scope = {}
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                exec(code, {}, local_scope)
            output = buffer.getvalue().strip()
            if output:
                return output
            return "Python code executed successfully."
        except Exception as exc:  # pylint: disable=broad-except
            return f"Python execution error: {exc}"
