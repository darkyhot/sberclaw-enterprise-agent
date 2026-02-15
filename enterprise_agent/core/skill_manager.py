"""Directory-based Agent Skills discovery, loading, and activation."""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Dict, List

from core.tool_registry import ToolRegistry
from tools.script_execution_tool import ScriptExecutionTool


class SkillManager:
    """Loads skills from skills/<skill_name>/SKILL.md with lazy full-text loading."""

    def __init__(
        self,
        skills_dir: str,
        registry: ToolRegistry,
        script_tool: ScriptExecutionTool,
    ):
        self.skills_dir = os.path.abspath(skills_dir)
        self.registry = registry
        self.script_tool = script_tool
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.active_skill_names: List[str] = []
        os.makedirs(self.skills_dir, exist_ok=True)

    def _discover_skill_dirs(self) -> List[str]:
        entries = []
        if not os.path.exists(self.skills_dir):
            return entries
        for name in sorted(os.listdir(self.skills_dir)):
            path = os.path.join(self.skills_dir, name)
            if os.path.isdir(path):
                entries.append(path)
        return entries

    def _parse_scalar(self, value: str) -> Any:
        text = value.strip()
        if not text:
            return ""
        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]
        if text.startswith("'") and text.endswith("'"):
            return text[1:-1]
        if text.lower() == "true":
            return True
        if text.lower() == "false":
            return False
        if text.isdigit():
            return int(text)
        return text

    def _parse_block_value(self, block_lines: List[str]) -> Any:
        stripped = [line.rstrip() for line in block_lines if line.strip()]
        if not stripped:
            return {}

        if all(line.lstrip().startswith("- ") for line in stripped):
            return [self._parse_scalar(line.lstrip()[2:]) for line in stripped]

        parsed: Dict[str, Any] = {}
        for line in stripped:
            clean = line.strip()
            if ":" not in clean:
                continue
            key, value = clean.split(":", 1)
            parsed[key.strip()] = self._parse_scalar(value.strip())
        if parsed:
            return parsed
        return "\n".join(stripped)

    def _parse_frontmatter(self, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip() or line.strip().startswith("#"):
                i += 1
                continue
            if re.match(r"^\S[^:]*:\s*.*$", line):
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value:
                    data[key] = self._parse_scalar(value)
                    i += 1
                    continue

                block: List[str] = []
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if re.match(r"^\S[^:]*:\s*.*$", nxt):
                        break
                    block.append(nxt)
                    i += 1
                data[key] = self._parse_block_value(block)
                continue
            i += 1
        return data

    def _read_frontmatter_only(self, skill_md_path: str) -> Dict[str, Any]:
        frontmatter_lines: List[str] = []
        closed = False
        with open(skill_md_path, "r", encoding="utf-8") as f:
            first = f.readline()
            if first.strip() != "---":
                raise ValueError("SKILL.md must start with YAML frontmatter delimited by ---")
            for line in f:
                if line.strip() == "---":
                    closed = True
                    break
                frontmatter_lines.append(line.rstrip("\n"))
        if not closed:
            raise ValueError("SKILL.md frontmatter missing closing --- delimiter")
        data = self._parse_frontmatter("\n".join(frontmatter_lines))
        if "name" not in data or "description" not in data:
            raise ValueError("SKILL.md frontmatter requires name and description")
        return data

    def _discover_scripts(self, skill_dir: str) -> List[str]:
        scripts_root = os.path.join(skill_dir, "scripts")
        paths: List[str] = []
        if not os.path.isdir(scripts_root):
            return paths
        for base, _, files in os.walk(scripts_root):
            for file_name in files:
                if file_name.endswith(".py"):
                    full = os.path.join(base, file_name)
                    rel = os.path.relpath(full, self.skills_dir)
                    paths.append(rel.replace("\\", "/"))
        return sorted(paths)

    def _safe_tool_name(self, value: str) -> str:
        lowered = value.lower()
        cleaned = re.sub(r"[^a-z0-9_]+", "_", lowered)
        return cleaned.strip("_")

    def _make_script_runner(self, script_path: str) -> Callable:
        def _runner(script_input: str = "") -> str:
            return self.script_tool.run_script(script_path, script_input)

        return _runner

    def _register_skill_scripts(self) -> List[str]:
        self.registry.clear_skill_tools()
        registered: List[str] = []
        for skill in self.skills.values():
            skill_slug = skill["slug"]
            for script_path in skill["scripts"]:
                script_name = os.path.splitext(os.path.basename(script_path))[0]
                tool_name = f"skill_script_{self._safe_tool_name(skill_slug)}_{self._safe_tool_name(script_name)}"
                description = f"Run skill script {script_path}"
                self.registry.register_skill_script(
                    tool_name,
                    self._make_script_runner(script_path),
                    description=description,
                )
                registered.append(tool_name)
        return sorted(registered)

    def reload_skills(self) -> List[str]:
        discovered: Dict[str, Dict[str, Any]] = {}
        for skill_dir in self._discover_skill_dirs():
            skill_md_path = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isfile(skill_md_path):
                continue
            meta = self._read_frontmatter_only(skill_md_path)
            slug = os.path.basename(skill_dir)
            discovered[str(meta["name"])] = {
                "name": str(meta["name"]),
                "slug": slug,
                "description": str(meta["description"]),
                "frontmatter": meta,
                "skill_md_path": skill_md_path,
                "scripts": self._discover_scripts(skill_dir),
                "body_cache": None,
            }
        self.skills = discovered
        self.active_skill_names = [name for name in self.active_skill_names if name in self.skills]
        return self._register_skill_scripts()

    def list_skills(self) -> List[Dict[str, Any]]:
        result = []
        for name in sorted(self.skills.keys()):
            skill = self.skills[name]
            result.append(
                {
                    "name": skill["name"],
                    "slug": skill["slug"],
                    "description": skill["description"],
                    "metadata": skill["frontmatter"].get("metadata", {}),
                    "scripts": list(skill["scripts"]),
                }
            )
        return result

    def describe_skills(self) -> str:
        skills = self.list_skills()
        if not skills:
            return "(no skills discovered)"
        return "\n".join(f"- {skill['name']}: {skill['description']}" for skill in skills)

    def _resolve_name(self, skill_name_or_slug: str) -> str:
        lookup = skill_name_or_slug.strip().lower()
        for name, info in self.skills.items():
            if name.lower() == lookup or info["slug"].lower() == lookup:
                return name
        raise KeyError(f"Skill not found: {skill_name_or_slug}")

    def load_skill_markdown(self, skill_name_or_slug: str) -> str:
        name = self._resolve_name(skill_name_or_slug)
        skill = self.skills[name]
        if skill["body_cache"] is None:
            with open(skill["skill_md_path"], "r", encoding="utf-8") as f:
                skill["body_cache"] = f.read()
        return str(skill["body_cache"])

    def activate_skill(self, skill_name_or_slug: str) -> str:
        name = self._resolve_name(skill_name_or_slug)
        self.load_skill_markdown(name)
        if name not in self.active_skill_names:
            self.active_skill_names.append(name)
        return f"Skill activated: {name}"

    def get_active_skill_context(self) -> str:
        if not self.active_skill_names:
            return ""
        parts: List[str] = []
        for name in self.active_skill_names:
            skill_text = self.load_skill_markdown(name)
            parts.append(f"## Skill: {name}\n{skill_text}")
        return "\n\n".join(parts)

    def get_skill_info(self, skill_name_or_slug: str) -> str:
        return self.load_skill_markdown(skill_name_or_slug)
