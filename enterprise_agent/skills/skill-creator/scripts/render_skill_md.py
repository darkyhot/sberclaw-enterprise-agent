"""Render a strict Agent Skills SKILL.md document.

Input:
- Uses global INPUT string.
- Expected JSON string:
  {"name":"skill-name","description":"...","title":"Optional Title"}

Output:
- Prints fully formatted SKILL.md content.
"""

from __future__ import annotations

import json
import re


def to_title(value: str) -> str:
    parts = [p for p in re.split(r"[-_\\s]+", value.strip()) if p]
    return " ".join(word.capitalize() for word in parts) or "Skill"


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]+", "-", value.lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned or "new-skill"


def build_skill_md(name: str, description: str, title: str) -> str:
    return f"""---
name: {name}
description: {description}
---

# {title}

## Goal

{description}

## Workflow

1. Identify the target task.
2. Choose the minimal required actions.
3. Execute steps deterministically when possible.
4. Return concise results.

## Resources

- `scripts/` for executable helpers.
- `references/` for docs loaded when needed.
- `assets/` for templates and files used in outputs.
"""


def main() -> None:
    raw = globals().get("INPUT", "")
    payload = {}
    if isinstance(raw, str) and raw.strip():
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"description": raw.strip()}

    name = normalize_name(str(payload.get("name", "new-skill")))
    description = str(payload.get("description", "")).strip() or "Fill skill description."
    title = str(payload.get("title", "")).strip() or to_title(name)
    print(build_skill_md(name=name, description=description, title=title))


if __name__ == "__main__":
    main()
