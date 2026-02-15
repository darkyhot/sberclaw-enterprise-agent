"""Autonomous multi-step coding agent."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain.schema import HumanMessage, SystemMessage

from core.memory import MemoryStore
from core.planner import Planner
from core.skill_manager import SkillManager
from core.tool_registry import ToolRegistry


SYSTEM_PROMPT = """You are an enterprise autonomous coding agent.
You must work step-by-step and always return valid JSON.

Available response formats:
1) {"action": "<tool_name>", "input": "<string_or_json_string>"}
2) {"final": "<final_response_for_user>"}

Rules:
- Use tools when you need filesystem changes or computation.
- You can activate a skill by calling action "activate_skill".
- Keep actions small and testable.
- If task is complete, return final.
- Never output anything outside JSON.
"""


class EnterpriseAgent:
    """Coordinates memory, planner, tools, and LLM reasoning loop."""

    def __init__(
        self,
        model,
        memory: MemoryStore,
        planner: Planner,
        registry: ToolRegistry,
        skill_manager: SkillManager,
        max_steps: int = 12,
    ):
        self.model = model
        self.memory = memory
        self.planner = planner
        self.registry = registry
        self.skill_manager = skill_manager
        self.max_steps = max_steps

    def _serialize_history(self) -> str:
        lines = []
        for item in self.memory.get_history():
            lines.append(f"{item['role']}: {item['content']}")
        return "\n".join(lines)

    def _build_prompt(self, user_input: str) -> List[Any]:
        tools_text = self.registry.describe_tools()
        history_text = self._serialize_history()
        plan_text = "\n".join(f"- {step}" for step in self.planner.get_plan())
        skills_text = self.skill_manager.describe_skills()
        active_skills_text = self.skill_manager.get_active_skill_context()
        prompt = (
            f"Current user request:\n{user_input}\n\n"
            f"Current plan:\n{plan_text}\n\n"
            f"Conversation history:\n{history_text}\n\n"
            f"Discovered skills:\n{skills_text}\n\n"
            f"Active skill instructions:\n{active_skills_text or '(none)'}\n\n"
            f"Available tools:\n{tools_text}\n\n"
            "Return only JSON."
        )
        return [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]

    def _invoke_model(self, user_input: str) -> Dict[str, Any]:
        messages = self._build_prompt(user_input)
        raw = self.model.invoke(messages)
        text = raw.content if hasattr(raw, "content") else str(raw)
        text = self._normalize_model_text(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"final": f"Model returned non-JSON output: {text}"}

    def _normalize_model_text(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 3:
                candidate = parts[1].strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate:
                    return candidate
        return cleaned

    def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        if not self.registry.has(tool_name):
            return f"Unknown tool: {tool_name}"
        tool = self.registry.get(tool_name)
        try:
            try:
                parsed = json.loads(tool_input)
            except Exception:  # pylint: disable=broad-except
                parsed = tool_input

            if isinstance(parsed, dict):
                result = tool(**parsed)
            else:
                result = tool(parsed)
            return str(result)
        except TypeError:
            try:
                result = tool(tool_input)
                return str(result)
            except Exception as exc:  # pylint: disable=broad-except
                return f"Tool execution error: {exc}"
        except Exception as exc:  # pylint: disable=broad-except
            return f"Tool execution error: {exc}"

    def run(self, user_input: str) -> str:
        self.memory.add_message("user", user_input)
        self.planner.create_initial_plan(user_input)

        relevant = self.planner.select_relevant_skills(
            user_input,
            self.skill_manager.list_skills(),
        )
        for skill_name in relevant:
            self.skill_manager.activate_skill(skill_name)
        if relevant:
            self.memory.add_message("system", f"Auto-activated skills: {', '.join(relevant)}")

        step_count = 0
        while step_count < self.max_steps:
            step_count += 1
            decision = self._invoke_model(user_input)

            if "final" in decision:
                final_text = str(decision["final"])
                self.memory.add_message("assistant", final_text)
                return final_text

            action = decision.get("action")
            tool_input = decision.get("input", "")
            if not action:
                message = f"Invalid model output at step {step_count}: {decision}"
                self.memory.add_message("assistant", message)
                return message

            result = self._execute_tool(str(action), str(tool_input))
            self.memory.add_tool_log(str(action), str(tool_input), result)
            self.memory.add_message("tool", f"{action}({tool_input}) => {result}")

        timeout_message = f"Stopped after reaching MAX_STEPS={self.max_steps}."
        self.memory.add_message("assistant", timeout_message)
        return timeout_message
