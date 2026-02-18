"""Autonomous multi-step coding agent with robust decision handling."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain.schema import HumanMessage, SystemMessage

from core.memory import MemoryStore
from core.planner import Planner
from core.skill_manager import SkillManager
from core.tool_registry import ToolRegistry


SYSTEM_PROMPT = """You are an enterprise autonomous coding agent.
You MUST operate in strict JSON decision mode.
Never explain outside JSON.
Never return Python dicts.
Never use single quotes.
Only double-quoted valid JSON.

Allowed outputs:
1) {"action": "tool_name", "input": "..."}
2) {"final": "..."}

If unsure, choose the safest next tool step.
Work step-by-step."""

CORRECTION_PROMPT = """Your previous output was invalid.
You MUST respond ONLY in this JSON format:
{"action": "<tool_name>", "input": "<string_or_json_string>"}
OR
{"final": "<text>"}
Do not add explanations."""

REFLECTION_TEMPLATE = """You executed tool {tool_name}.
Result was:
{result}

Is the task complete?
If yes -> return final.
If not -> choose next action."""

UNKNOWN_TOOL_TEMPLATE = """Tool {tool_name} does not exist.
Available tools are:
{available_tools}
Choose a valid next action."""

LOOP_WARNING_TEMPLATE = """Potential tool loop detected:
tool={tool_name}, input={tool_input}
This action was repeated 3 times.
Reconsider and choose a different next step or return final."""

WRITE_BLOCK_TEMPLATE = """Write action blocked: tool={tool_name}.
The user did not explicitly request creating or writing files.
Do not use write tools unless user explicitly asks for file/folder creation.
Choose a non-write tool or return final."""


class EnterpriseAgent:
    """Coordinates memory, planner, tools, and resilient LLM reasoning loop."""

    MAX_RETRIES = 3
    HISTORY_LIMIT = 10
    TOOL_LOG_LIMIT = 10

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

    def _strip_markdown_fences(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _extract_first_json_block(self, text: str) -> Optional[str]:
        start = text.find("{")
        if start < 0:
            return None
        depth = 0
        for i in range(start, len(text)):
            char = text[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    def _repair_jsonish_text(self, text: str) -> str:
        candidate = text.strip()
        candidate = re.sub(r"'", '"', candidate)
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        candidate = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_-]*)\s*:', r'\1"\2":', candidate)
        return candidate

    def _coerce_decision(self, parsed: Any) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            return {}

        if "final" in parsed and isinstance(parsed["final"], str):
            return {"final": parsed["final"]}

        if "action" in parsed and isinstance(parsed["action"], str):
            return {"action": parsed["action"], "input": parsed.get("input", "")}

        if len(parsed) == 1:
            key = list(parsed.keys())[0]
            value = parsed[key]
            if key == "tool_name" and isinstance(value, str):
                return {"action": value, "input": ""}
            if key in self.registry.list_names():
                return {"action": key, "input": value}
            if isinstance(key, str):
                return {"action": key, "input": value}

        return parsed

    def _normalize_decision(self, text: str) -> Dict[str, Any]:
        normalized_text = self._strip_markdown_fences(text)
        parsed: Optional[Any] = None

        attempts: List[str] = [normalized_text]
        extracted = self._extract_first_json_block(normalized_text)
        if extracted:
            attempts.append(extracted)

        for attempt in attempts:
            try:
                parsed = json.loads(attempt)
                break
            except json.JSONDecodeError:
                repaired = self._repair_jsonish_text(attempt)
                extracted_repaired = self._extract_first_json_block(repaired) or repaired
                try:
                    parsed = json.loads(extracted_repaired)
                    break
                except json.JSONDecodeError:
                    continue

        if parsed is None:
            return {}
        return self._coerce_decision(parsed)

    def _is_valid_decision(self, decision: Dict[str, Any]) -> bool:
        if "final" in decision and isinstance(decision["final"], str):
            return True
        if "action" in decision and isinstance(decision["action"], str):
            return True
        return False

    def _serialize_history(self) -> str:
        lines = []
        for item in self.memory.get_history(limit=self.HISTORY_LIMIT):
            lines.append(f"{item['role']}: {item['content']}")
        return "\n".join(lines)

    def _serialize_tool_logs(self) -> str:
        logs = self.memory.get_tool_logs(limit=self.TOOL_LOG_LIMIT)
        if not logs:
            return "(none)"
        lines = []
        for log in logs:
            lines.append(
                f"- tool={log['tool_name']} input={log['input']} output={log['output']}"
            )
        return "\n".join(lines)

    def _build_prompt(self, user_input: str) -> str:
        tools_text = self.registry.describe_tools()
        history_text = self._serialize_history()
        tool_logs_text = self._serialize_tool_logs()
        plan_text = "\n".join(f"- {step}" for step in self.planner.get_plan())
        skills_text = self.skill_manager.describe_skills()
        active_skills_text = self.skill_manager.get_active_skill_context()
        return (
            f"Current user request:\n{user_input}\n\n"
            f"Current plan:\n{plan_text}\n\n"
            f"Conversation history (last {self.HISTORY_LIMIT}):\n{history_text}\n\n"
            f"Recent tool logs (last {self.TOOL_LOG_LIMIT}):\n{tool_logs_text}\n\n"
            f"Discovered skills:\n{skills_text}\n\n"
            f"Active skill instructions:\n{active_skills_text or '(none)'}\n\n"
            f"Available tools:\n{tools_text}\n\n"
            "Return only JSON."
        )

    def _invoke_raw_model(self, messages: List[Any]) -> str:
        try:
            raw = self.model.invoke(messages, temperature=0.1)
        except TypeError:
            raw = self.model.invoke(messages)
        text = raw.content if hasattr(raw, "content") else str(raw)
        print("===== RAW MODEL OUTPUT =====")
        print(text)
        return text

    def _decide(
        self,
        user_input: str,
        extra_system_messages: Optional[List[str]] = None,
        extra_human_message: str = "",
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        correction_needed = False
        for _ in range(self.MAX_RETRIES):
            messages: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
            if extra_system_messages:
                for content in extra_system_messages:
                    if content:
                        messages.append(SystemMessage(content=content))
            if correction_needed:
                messages.append(SystemMessage(content=CORRECTION_PROMPT))

            prompt = self._build_prompt(user_input)
            if extra_human_message:
                prompt = f"{prompt}\n\nAdditional instruction:\n{extra_human_message}"
            messages.append(HumanMessage(content=prompt))

            text = self._invoke_raw_model(messages)
            decision = self._normalize_decision(text)
            print("===== NORMALIZED DECISION =====")
            print(decision)
            if self._is_valid_decision(decision):
                return decision, None
            correction_needed = True
        return None, "Failed to produce valid decision after retries."

    def _execute_tool(self, tool_name: str, tool_input: Any) -> str:
        tool = self.registry.get(tool_name)
        parsed = tool_input
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:  # pylint: disable=broad-except
                parsed = tool_input

        try:
            if isinstance(parsed, dict):
                result = tool(**parsed)
            elif parsed == "":
                result = tool("")
            else:
                result = tool(parsed)
            return str(result)
        except TypeError:
            try:
                result = tool(str(tool_input))
                return str(result)
            except Exception as exc:  # pylint: disable=broad-except
                return f"Tool execution error: {exc}"
        except Exception as exc:  # pylint: disable=broad-except
            return f"Tool execution error: {exc}"

    def _format_tool_feedback(self, tool_name: str, tool_input: Any, result: str) -> str:
        return (
            "Tool execution result:\n"
            f"- tool: {tool_name}\n"
            f"- input: {tool_input}\n"
            f"- output: {result}"
        )

    def _is_action_loop(self, recent_actions: List[Tuple[str, str]]) -> bool:
        if len(recent_actions) < 3:
            return False
        last_three = recent_actions[-3:]
        return all(item == last_three[0] for item in last_three)

    def _has_explicit_write_intent(self, user_input: str) -> bool:
        text = user_input.lower()
        write_hints = [
            "write file",
            "create file",
            "save file",
            "generate file",
            "make file",
            "create folder",
            "create directory",
            "scaffold",
            "project structure",
            "создай файл",
            "создать файл",
            "запиши в файл",
            "сохрани в файл",
            "сгенерируй файл",
            "создай папку",
            "создай директорию",
            "создать папку",
            "создать директорию",
            "создай проект",
            "сгенерируй проект",
        ]
        return any(hint in text for hint in write_hints)

    def _is_write_tool(self, tool_name: str) -> bool:
        return tool_name in {"write_file", "create_directory"}

    def run(self, user_input: str) -> str:
        if user_input.strip() == "/reset":
            self.memory.reset_all()
            self.planner.reset()
            self.skill_manager.clear_active_skills()
            return "Context reset complete."

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

        recent_actions: List[Tuple[str, str]] = []
        follow_up_instruction = ""
        allow_write = self._has_explicit_write_intent(user_input)

        step_count = 0
        while step_count < self.max_steps:
            step_count += 1
            decision, error = self._decide(
                user_input,
                extra_system_messages=[],
                extra_human_message=follow_up_instruction,
            )
            follow_up_instruction = ""
            if decision is None:
                failure = error or "Model decision failed."
                self.memory.add_message("assistant", failure)
                return failure

            if "final" in decision:
                final_text = str(decision["final"])
                self.memory.add_message("assistant", final_text)
                return final_text

            tool_name = str(decision.get("action", "")).strip()
            tool_input = decision.get("input", "")
            tool_input_text = tool_input if isinstance(tool_input, str) else json.dumps(tool_input)

            if not self.registry.has(tool_name):
                unknown_message = UNKNOWN_TOOL_TEMPLATE.format(
                    tool_name=tool_name,
                    available_tools="\n".join(f"- {n}" for n in self.registry.list_names()),
                )
                self.memory.add_message("system", unknown_message)
                follow_up_instruction = unknown_message
                continue

            if self._is_write_tool(tool_name) and not allow_write:
                blocked_message = WRITE_BLOCK_TEMPLATE.format(tool_name=tool_name)
                self.memory.add_message("system", blocked_message)
                follow_up_instruction = blocked_message
                continue

            result = self._execute_tool(tool_name, tool_input)
            self.memory.add_tool_log(tool_name, tool_input_text, result)

            feedback = self._format_tool_feedback(tool_name, tool_input, result)
            self.memory.add_message("tool", feedback)

            recent_actions.append((tool_name, tool_input_text))
            if len(recent_actions) > 6:
                recent_actions = recent_actions[-6:]

            if self._is_action_loop(recent_actions):
                loop_message = LOOP_WARNING_TEMPLATE.format(
                    tool_name=tool_name,
                    tool_input=tool_input_text,
                )
                self.memory.add_message("system", loop_message)
                follow_up_instruction = loop_message
            else:
                follow_up_instruction = REFLECTION_TEMPLATE.format(
                    tool_name=tool_name,
                    result=result,
                )

        timeout_message = f"Stopped after reaching MAX_STEPS={self.max_steps}."
        self.memory.add_message("assistant", timeout_message)
        return timeout_message
