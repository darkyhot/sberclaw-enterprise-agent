"""Tool registry for built-in tools and skill script tools."""

from __future__ import annotations

import inspect
from typing import Callable, Dict, List, Optional


class ToolRegistry:
    """Stores tools by name and exposes metadata for prompting."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._sources: Dict[str, str] = {}
        self._descriptions: Dict[str, str] = {}

    def register(
        self,
        name: str,
        func: Callable,
        source: str = "core",
        description: Optional[str] = None,
    ) -> None:
        self._tools[name] = func
        self._sources[name] = source
        if description:
            self._descriptions[name] = description
        elif name in self._descriptions:
            del self._descriptions[name]

    def register_skill_script(self, name: str, func: Callable, description: str) -> None:
        self.register(name, func, source="skill_script", description=description)

    def unregister(self, name: str) -> None:
        if name in self._tools:
            del self._tools[name]
        if name in self._sources:
            del self._sources[name]
        if name in self._descriptions:
            del self._descriptions[name]

    def clear_skill_tools(self) -> None:
        for name in list(self._tools.keys()):
            if self._sources.get(name) == "skill_script":
                del self._tools[name]
                if name in self._sources:
                    del self._sources[name]
                if name in self._descriptions:
                    del self._descriptions[name]

    def get(self, name: str) -> Callable:
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_names(self) -> List[str]:
        return sorted(self._tools.keys())

    def describe_tools(self) -> str:
        lines = []
        for name in self.list_names():
            func = self._tools[name]
            sig = str(inspect.signature(func))
            doc = self._descriptions.get(name) or inspect.getdoc(func) or "No description"
            source = self._sources.get(name, "core")
            lines.append(f"- {name}{sig}: {doc.splitlines()[0]} [source={source}]")
        return "\n".join(lines)
