"""Simple transparent planner."""

from __future__ import annotations

import re
from typing import Dict, List


class Planner:
    """Stores and updates plan steps for visibility and control."""

    def __init__(self):
        self.plan_steps: List[str] = []

    def create_initial_plan(self, user_request: str) -> List[str]:
        self.plan_steps = [
            f"Understand request: {user_request}",
            "Create or update project files as needed",
            "Validate outputs and prepare final response",
        ]
        return list(self.plan_steps)

    def get_plan(self) -> List[str]:
        return list(self.plan_steps)

    def update_plan(self, steps: List[str]) -> None:
        self.plan_steps = list(steps)

    def select_relevant_skills(
        self,
        user_request: str,
        skill_summaries: List[Dict[str, object]],
    ) -> List[str]:
        """Return skill names that are likely relevant to the user request."""
        request = user_request.lower()
        request_tokens = {t for t in re.findall(r"[a-z0-9_]+", request) if len(t) > 2}
        selected: List[str] = []

        for skill in skill_summaries:
            name = str(skill.get("name", ""))
            description = str(skill.get("description", ""))
            metadata = skill.get("metadata", {})
            skill_text = f"{name} {description} {metadata}".lower()
            score = 0
            for token in request_tokens:
                if token in skill_text:
                    score += 1
            if score > 0:
                selected.append(name)

        return selected
