from dataclasses import dataclass, field, asdict
from typing import Callable, Any, Optional, Literal
from datetime import datetime
import threading
import json

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from core.config_manager import ConfigManager
from core.i18n import I18n
from core.tools import tools_registry, scout_workspace, RiskLevel

ToolName = Literal[
    "read_file",
    "write_file",
    "delete_file",
    "create_folder",
    "list_directory",
    "run_terminal_command",
    "read_pdf",
    "open_browser",
    "duckduckgo_search",
    "none",
]


@dataclass
class PlanStep:
    step_id: int
    title: str
    description: str
    tool_name: str
    tool_args: dict
    status: str = "PENDING"  # PENDING, GUIDANCE, RUNNING, SUCCESS, FAILED, SKIPPED
    result: str = ""


@dataclass
class Plan:
    goal: str
    summary: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    is_approved: bool = False
    is_executed: bool = False
    workspace_snapshot: str = ""


# ── Planning schema (intent-only steps for human review) ─────────────────────


class StepSchema(BaseModel):
    title: str = Field(description="Short, clear sub-step title")
    description: str = Field(
        description="What this step accomplishes. Do NOT paste full file contents here."
    )
    tool_name: ToolName = Field(
        description=(
            "Expected tool: read_file, write_file, delete_file, create_folder, "
            "list_directory, run_terminal_command, read_pdf, open_browser, or none"
        )
    )
    file_path: Optional[str] = Field(
        default=None, description="Target file path hint (relative to workspace)"
    )
    command: Optional[str] = Field(
        default=None, description="Command hint for run_terminal_command"
    )
    url: Optional[str] = Field(default=None, description="URL hint for open_browser")
    dir_path: Optional[str] = Field(default=None, description="Directory path hint")


class PlanSchema(BaseModel):
    goal: str = Field(description="User's primary objective")
    summary: str = Field(description="High-level overview of the approach")
    requires_plan: bool = Field(
        description="True if the task needs tools or multiple steps; false for simple Q&A"
    )
    direct_response: Optional[str] = Field(
        default=None,
        description="Direct answer when requires_plan is false",
    )
    steps: list[StepSchema] = Field(
        default_factory=list,
        description="Ordered intent steps (max 8). Use real paths from workspace snapshot.",
    )


# ── Agent loop schema (one tool per turn after Proceed) ──────────────────────


class ActionSchema(BaseModel):
    thought: str = Field(description="Brief reasoning for this action")
    done: bool = Field(description="True when the goal is fully achieved")
    final_response: Optional[str] = Field(
        default=None,
        description="User-facing summary when done=true",
    )
    tool_name: Optional[ToolName] = Field(
        default=None,
        description="Tool to run this turn. Null when done=true.",
    )
    file_path: Optional[str] = Field(default=None)
    file_content: Optional[str] = Field(
        default=None,
        description="Full content for write_file — generate at execution time, not in the plan",
    )
    command: Optional[str] = Field(default=None)
    url: Optional[str] = Field(default=None)
    dir_path: Optional[str] = Field(default=None)

    query: Optional[str] = Field(
        default=None, description="The search keywords for duckduckgo_search"
    )
    max_results: Optional[int] = Field(
        default=5, description="Max results for duckduckgo_search"
    )


_FAIL_RESULT_PREFIXES = (
    "error",
    "security error",
    "security rejected",
    "execution error",
    "access denied",
)

ALWAYS_REQUIRE_APPROVAL = {"delete_file", "run_terminal_command"}
AUTO_APPROVABLE_TOOLS = {"write_file", "create_folder", "open_browser"}
MAX_PLAN_STEPS = 8
MAX_SCRATCHPAD_TURNS = 12


class AgentEngine:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.current_plan: Optional[Plan] = None
        self.history = []
        self.is_running = False
        self.stop_requested = False
        self.approval_event = threading.Event()
        self.approval_granted = False
        self._run_lock = threading.Lock()

        self.on_message = None
        self.on_plan_ready = None
        self.on_step_update = None
        self.on_step_appended = None
        self.on_approval_required = None
        self.on_status_change = None
        self.on_key_rotated = None

    def set_callbacks(
        self,
        on_message=None,
        on_plan_ready=None,
        on_step_update=None,
        on_step_appended=None,
        on_approval_required=None,
        on_status_change=None,
        on_key_rotated=None,
    ):
        self.on_message = on_message
        self.on_plan_ready = on_plan_ready
        self.on_step_update = on_step_update
        self.on_step_appended = on_step_appended
        self.on_approval_required = on_approval_required
        self.on_status_change = on_status_change
        self.on_key_rotated = on_key_rotated

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _emit_status(self, text: str):
        if self.on_status_change:
            self.on_status_change(text)

    def _emit_message(self, sender: str, text: str, is_user: bool = False):
        if self.on_message:
            self.on_message(sender, text, is_user)

    def _try_begin_run(self) -> bool:
        with self._run_lock:
            if self.is_running:
                return False
            self.is_running = True
            return True

    def _end_run(self):
        with self._run_lock:
            self.is_running = False

    @staticmethod
    def _tool_result_failed(result: str) -> bool:
        if not result:
            return False
        lower = result.strip().lower()
        return any(lower.startswith(prefix) for prefix in _FAIL_RESULT_PREFIXES)

    def _needs_user_approval(self, tool_def) -> bool:
        if tool_def.risk_level == RiskLevel.SAFE:
            return False
        if tool_def.risk_level == RiskLevel.HIGH_RISK:
            return True
        if tool_def.name in ALWAYS_REQUIRE_APPROVAL:
            return True
        auto_approve = self.config_mgr.config.get("auto_approve_safe_tools", False)
        if auto_approve and tool_def.name in AUTO_APPROVABLE_TOOLS:
            return False
        return tool_def.risk_level == RiskLevel.REQUIRES_APPROVAL

    def _lang_str(self) -> str:
        lang = self.config_mgr.config.get("language", "th")
        return "ตอบกลับเป็นภาษาไทย" if lang == "th" else "Respond in English"

    def _base_identity(self) -> str:
        custom = self.config_mgr.config.get("system_instruction", "").strip()

        # ใช้ Multi-line string (""") เพื่อจัดฟอร์แมต Prompt ให้เป็นระเบียบและแก้ไขง่ายในอนาคต
        base = """You are a senior expert in software development, programming, and code architecture.

            Your Core Objectives:
            - Provide clean, efficient, scalable, and well-documented code.
            - Design robust architectures following industry best practices (e.g., SOLID principles, Design Patterns).

            Your Operating Rules:
            1. Think Step-by-Step: Analyze the problem thoroughly before generating code. Outline your logic first.
            2. Prioritize Quality & Security: Always consider edge cases, performance bottlenecks, and security vulnerabilities.
            3. Be Concise but Clear: Explain the 'Why' behind your architectural decisions without unnecessary fluff.
            4. Ask for Clarification: If the user's request is ambiguous or lacks constraints, ask clarifying questions before proceeding.

            Output Format:
            Use markdown for explanations and format all code inside appropriate code blocks with comments."""

        if custom:
            # เพิ่ม \n\n เพื่อให้มีบรรทัดว่างคั่นระหว่าง Base Prompt กับ Custom Prompt
            return f"{base}\n\n{custom}"

        return base

    def _build_plan_system_prompt(
        self, workspace, scout: str, tool_catalog: str
    ) -> str:
        return (
            f"{self._base_identity()}\n"
            f"Output Language Requirement: {self._lang_str()}\n"
            f"Workspace Folder: {workspace}\n\n"
            f"=== Workspace Snapshot ===\n{scout}\n\n"
            f"=== Available Tools ===\n{tool_catalog}\n\n"
            "Planning rules:\n"
            "- Use ONLY paths that exist in the snapshot or new relative paths under workspace.\n"
            "- First step should list or read when editing existing code.\n"
            "- Do NOT put full file contents in the plan — content is generated during execution.\n"
            "- Coding tasks should end with a verify step (read_file or run_terminal_command).\n"
            f"- Maximum {MAX_PLAN_STEPS} steps.\n"
            "- tool_name must be one of the listed tools or none.\n\n"
            "Decide:\n"
            "- Simple Q&A / chat → requires_plan=false, answer in direct_response.\n"
            "- Actionable task → requires_plan=true, intent steps with tool hints and paths.\n\n"
            "When writing direct_response, use Markdown: # / ## headings, short paragraphs, "
            "and fenced code blocks (```python ... ```) for any code."
        )

    def _build_actor_system_prompt(
        self, workspace, scout: str, tool_catalog: str
    ) -> str:
        return (
            f"{self._base_identity()}\n"
            f"Output Language Requirement:  {self._lang_str()}\n"
            f"Workspace Folder: {workspace}\n\n"
            f"=== Workspace Snapshot ===\n{scout}\n\n"
            f"=== Available Tools ===\n{tool_catalog}\n\n"
            "You are executing an approved plan in an agent loop.\n"
            "Rules:\n"
            "- One tool per turn. Set done=true with final_response when finished.\n"
            "- Read/list before write when unsure. Use tool results in scratchpad.\n"
            "- For duckduckgo_search, you MUST provide the search keywords in the 'query' field.\n"
            "- Generate full write_file content in this turn, not from the plan.\n"
            "- If a tool fails twice in a row, set done=true and explain the failure.\n"
            "- All paths must stay inside the workspace.\n"
            "- final_response must be Markdown with # / ## headings and ```language fenced code."
        )

    def _history_context(self) -> str:
        if len(self.history) <= 1:
            return ""
        turns = []
        for item in self.history[-11:-1]:
            role_label = "User" if item["role"] == "user" else "Assistant"
            turns.append(f"{role_label}: {item['text']}")
        return "Prior Conversation History:\n" + "\n".join(turns) + "\n\n"

    def _parse_step_args(self, s: StepSchema) -> dict:
        """Intent hints only — execution uses the agent loop."""
        args = {}
        if s.file_path:
            args["file_path"] = s.file_path
        if s.dir_path:
            args["dir_path"] = s.dir_path
        if s.command:
            args["command"] = s.command
        if s.url:
            args["url"] = s.url
        return args

    def _parse_action_args(self, action: ActionSchema) -> dict:
        t_name = action.tool_name or "none"
        if t_name == "duckduckgo_search":
            return {
                "query": action.query or "",
                "max_results": (
                    action.max_results if action.max_results is not None else 5
                ),
            }

        if t_name == "write_file":
            return {
                "file_path": action.file_path or "",
                "content": action.file_content or "",
            }
        if t_name == "read_file":
            return {"file_path": action.file_path or ""}
        if t_name == "delete_file":
            return {"file_path": action.file_path or ""}
        if t_name == "create_folder":
            return {"dir_path": action.dir_path or action.file_path or ""}
        if t_name == "run_terminal_command":
            return {"command": action.command or ""}
        if t_name == "open_browser":
            return {"url": action.url or ""}
        if t_name == "list_directory":
            return {"dir_path": action.dir_path or "."}
        if t_name == "read_pdf":
            return {"file_path": action.file_path or ""}
        return {}

    def _steps_from_schema(self, steps_data: list) -> list[PlanStep]:
        steps = []
        for idx, s_data in enumerate(steps_data[:MAX_PLAN_STEPS]):
            s = StepSchema(**s_data)
            steps.append(
                PlanStep(
                    step_id=idx + 1,
                    title=s.title,
                    description=s.description,
                    tool_name=s.tool_name,
                    tool_args=self._parse_step_args(s),
                    status="GUIDANCE",
                )
            )
        return steps

    def _format_scratchpad(self, scratchpad: list[dict]) -> str:
        if not scratchpad:
            return "(no actions yet)"
        lines = []
        for i, entry in enumerate(scratchpad[-MAX_SCRATCHPAD_TURNS:], 1):
            lines.append(
                f"Turn {i} [{entry.get('status', '?')}] thought: {entry.get('thought', '')}\n"
                f"  tool: {entry.get('tool')} args: {json.dumps(entry.get('args', {}), ensure_ascii=False)}\n"
                f"  result: {entry.get('result', '')[:2000]}"
            )
        return "\n\n".join(lines)

    def _format_guidance_steps(self, plan: Plan) -> str:
        lines = []
        for s in plan.steps:
            if s.status != "GUIDANCE":
                continue
            hint = json.dumps(s.tool_args, ensure_ascii=False) if s.tool_args else ""
            lines.append(
                f"{s.step_id}. {s.title} [{s.tool_name}] {hint}\n   {s.description}"
            )
        return "\n".join(lines) if lines else "(no guidance steps)"

    def _call_llm_json(
        self, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> dict:
        def llm_call(client, model):
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return response.text

        json_text = self.config_mgr.execute_with_auto_rotation(
            llm_call, on_rotate_callback=self.on_key_rotated
        )
        return json.loads(json_text)

    def _request_action(
        self, plan: Plan, scout: str, scratchpad: list[dict], turn: int
    ) -> ActionSchema:
        workspace = self.config_mgr.get_workspace_folder()
        tool_catalog = tools_registry.format_tool_catalog()
        system_prompt = self._build_actor_system_prompt(workspace, scout, tool_catalog)
        user_prompt = (
            f"Goal: {plan.goal}\n"
            f"Approved plan summary: {plan.summary}\n\n"
            f"Guidance steps:\n{self._format_guidance_steps(plan)}\n\n"
            f"Scratchpad (previous actions):\n{self._format_scratchpad(scratchpad)}\n\n"
            f"Turn {turn + 1}. Choose the next single tool action or set done=true."
        )
        data = self._call_llm_json(system_prompt, user_prompt, ActionSchema)
        return ActionSchema(**data)

    def _execute_tool_with_approval(
        self, idx: int, tool_name: str, tool_args: dict
    ) -> tuple[str, str]:
        """Returns (status, result_str). status is SUCCESS, FAILED, or SKIPPED."""
        tool_def = tools_registry.get_tool(tool_name)
        if not tool_def:
            return "FAILED", f"Tool not found: {tool_name}"

        if tool_name == "write_file" and not (tool_args.get("content") or "").strip():
            return "FAILED", "Error: write_file requires non-empty content"

        if self._needs_user_approval(tool_def):
            if not self.on_approval_required:
                return "FAILED", "Error: approval UI is not available"
            self.approval_event.clear()
            self.approval_granted = False
            self._emit_status(f"Waiting for user approval: {tool_name}")
            self.on_approval_required(
                idx,
                tool_name,
                tool_args,
                lambda: self.submit_approval(True),
                lambda: self.submit_approval(False),
            )
            self.approval_event.wait()
            if not self.approval_granted:
                return "SKIPPED", "Rejected by User"

        try:
            result_str = tool_def.func(**tool_args)
            failed = self._tool_result_failed(result_str)
            return ("FAILED" if failed else "SUCCESS"), result_str
        except Exception as e:
            return "FAILED", f"Error: {str(e)}"

    def clear_history(self):
        self.history.clear()

    # ── Planning (Layer A) ───────────────────────────────────────────────────

    def handle_user_input(self, prompt: str):
        if not self._try_begin_run():
            self._emit_message("System", I18n.t("agent_busy"), False)
            return
        self.history.append({"role": "user", "text": prompt})
        threading.Thread(
            target=self._process_prompt_worker, args=(prompt,), daemon=True
        ).start()

    def _process_prompt_worker(self, prompt: str):
        self._emit_status("Scouting workspace...")
        try:
            scout = scout_workspace(prompt)
            self._emit_status("Analyzing request and planning...")

            history_context = self._history_context()
            full_prompt = f"{history_context}Current User Request: {prompt}"
            workspace = self.config_mgr.get_workspace_folder()
            tool_catalog = tools_registry.format_tool_catalog()
            system_prompt = self._build_plan_system_prompt(
                workspace, scout, tool_catalog
            )

            data = self._call_llm_json(system_prompt, full_prompt, PlanSchema)

            if not data.get("requires_plan"):
                reply = data.get("direct_response") or "All done."
                self.history.append({"role": "assistant", "text": reply})
                self._emit_message("Draco", reply, False)
                self._emit_status("Ready")
                return

            if not data.get("steps"):
                self._emit_message("System", I18n.t("plan_no_steps"), False)
                self._emit_status("Ready")
                return

            steps = self._steps_from_schema(data.get("steps", []))
            plan = Plan(
                goal=data.get("goal", prompt),
                summary=data.get("summary", ""),
                steps=steps,
                workspace_snapshot=scout,
            )
            self.current_plan = plan

            step_titles = ", ".join(s.title for s in steps)
            self.history.append(
                {
                    "role": "assistant",
                    "text": f"Plan: {plan.summary} | Steps: {step_titles}",
                }
            )

            if self.on_plan_ready:
                self.on_plan_ready(plan)

            self._emit_message(
                "Draco",
                f"**Plan creation complete:**\n\n**Goal:** {plan.goal}\n**Approach:** {plan.summary}\n\n"
                f"*Review the plan in the Plan tab. After Proceed, the agent will act step-by-step using tool results.*",
                False,
            )
            self._emit_status("Waiting for user to review the plan (Plan Review)")

        except Exception as e:
            self._emit_message(
                "System", f"An error occurred during analysis: {str(e)}", False
            )
            self._emit_status("error")
        finally:
            self._end_run()

    def refine_plan(self, feedback: str):
        if not self.current_plan:
            self._emit_message("System", "Plan to edit not found", False)
            return
        if not self._try_begin_run():
            self._emit_message("System", I18n.t("agent_busy"), False)
            return
        threading.Thread(
            target=self._refine_plan_worker, args=(feedback,), daemon=True
        ).start()

    def _refine_plan_worker(self, feedback: str):
        self._emit_status(
            "Currently revising the work plan based on the recommendations.."
        )
        try:
            scout = self.current_plan.workspace_snapshot or scout_workspace(
                self.current_plan.goal
            )
            current_plan_dict = {
                "goal": self.current_plan.goal,
                "summary": self.current_plan.summary,
                "steps": [
                    asdict(s) for s in self.current_plan.steps if s.status == "GUIDANCE"
                ],
            }
            workspace = self.config_mgr.get_workspace_folder()
            tool_catalog = tools_registry.format_tool_catalog()
            system_prompt = self._build_plan_system_prompt(
                workspace, scout, tool_catalog
            )
            user_prompt = (
                f"Current Plan:\n{json.dumps(current_plan_dict, ensure_ascii=False, indent=2)}\n\n"
                f"User Feedback: {feedback}"
            )
            data = self._call_llm_json(system_prompt, user_prompt, PlanSchema)

            if not data.get("steps"):
                self._emit_message("System", I18n.t("plan_no_steps"), False)
                self._emit_status("Waiting for user confirmation of the plan")
                return

            plan = Plan(
                goal=data.get("goal", self.current_plan.goal),
                summary=data.get("summary", self.current_plan.summary),
                steps=self._steps_from_schema(data.get("steps", [])),
                workspace_snapshot=scout,
            )
            self.current_plan = plan
            if self.on_plan_ready:
                self.on_plan_ready(plan)
            self._emit_message(
                "Draco",
                f"The work plan has been revised in accordance with the recommendations:\n\n{plan.summary}",
                False,
            )
            self._emit_status("Waiting for user confirmation of the plan")
        except Exception as e:
            self._emit_message(
                "System", f"The plan cannot be modified: {str(e)}", False
            )
            self._emit_status("error")
        finally:
            self._end_run()

    # ── Execution (Layer B — agent loop) ─────────────────────────────────────

    def start_execution(self, expected_plan: Optional[Plan] = None) -> bool:
        if not self.current_plan or not self.current_plan.steps:
            self._emit_message(
                "System", "There is no plan ready for implementation", False
            )
            return False
        if expected_plan is not None and expected_plan is not self.current_plan:
            self._emit_message("System", I18n.t("stale_plan"), False)
            return False
        if self.current_plan.is_executed:
            self._emit_message("System", I18n.t("plan_already_ran"), False)
            return False
        if not self._try_begin_run():
            self._emit_message("System", I18n.t("agent_busy"), False)
            return False
        self.current_plan.is_approved = True
        threading.Thread(target=self._execution_worker, daemon=True).start()
        return True

    def submit_approval(self, approved: bool):
        self.approval_granted = approved
        self.approval_event.set()

    def _execution_worker(self):
        try:
            self._run_agent_loop()
        finally:
            self._end_run()

    def _run_agent_loop(self):
        self.stop_requested = False
        plan = self.current_plan
        if not plan:
            return

        scout = plan.workspace_snapshot or scout_workspace(plan.goal)
        max_turns = int(self.config_mgr.config.get("max_agent_turns", 20))
        scratchpad: list[dict] = []
        consecutive_failures = 0
        final_response: Optional[str] = None

        self._emit_status("Executing plan (agent loop)...")
        self._emit_message(
            "Draco",
            "Starting agent loop — each action uses the latest tool results.",
            False,
        )

        for turn in range(max_turns):
            if self.stop_requested:
                self._emit_message("System", "Execution stopped by user.", False)
                break

            self._emit_status(f"Agent thinking (turn {turn + 1}/{max_turns})...")

            try:
                action = self._request_action(plan, scout, scratchpad, turn)
            except Exception as e:
                self._emit_message("System", f"Agent loop error: {str(e)}", False)
                break

            if action.done:
                final_response = action.final_response or "Done."
                break

            tool_name = action.tool_name
            if not tool_name or tool_name == "none":
                scratchpad.append(
                    {
                        "thought": action.thought,
                        "tool": "none",
                        "args": {},
                        "result": "(no tool called)",
                        "status": "SUCCESS",
                    }
                )
                continue

            tool_args = self._parse_action_args(action)
            live_step = PlanStep(
                step_id=len(plan.steps) + 1,
                title=(
                    (action.thought[:80] + "...")
                    if len(action.thought) > 80
                    else action.thought
                ),
                description=action.thought,
                tool_name=tool_name,
                tool_args=tool_args,
                status="RUNNING",
            )
            plan.steps.append(live_step)
            idx = len(plan.steps) - 1

            if self.on_step_appended:
                self.on_step_appended(live_step, idx)

            self._emit_status(f"Running {tool_name} (turn {turn + 1})")
            status, result_str = self._execute_tool_with_approval(
                idx, tool_name, tool_args
            )
            live_step.status = status
            live_step.result = result_str

            if self.on_step_update:
                self.on_step_update(idx, status, result_str)

            scratchpad.append(
                {
                    "thought": action.thought,
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result_str,
                    "status": status,
                }
            )

            if status == "FAILED":
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    final_response = f"Stopped after repeated failures.\nLast error: {result_str[:500]}"
                    break
            elif status == "SKIPPED":
                consecutive_failures += 1
            else:
                consecutive_failures = 0

        else:
            final_response = (
                final_response or "Reached maximum agent turns without finishing."
            )

        plan.is_executed = True

        if final_response:
            self.history.append({"role": "assistant", "text": final_response})
            self._emit_message("Draco", final_response, False)
        else:
            self._emit_status("Summarizing results...")
            try:
                summary_text = self._summarize_results()
                if summary_text:
                    self.history.append({"role": "assistant", "text": summary_text})
                    self._emit_message("Draco", summary_text, False)
                else:
                    self._emit_message("Draco", "Agent loop completed.", False)
            except Exception:
                self._emit_message("Draco", "Agent loop completed.", False)

        self._emit_status("Operation completed")

    def _summarize_results(self) -> str | None:
        if not self.current_plan:
            return None

        results_parts = []
        for step in self.current_plan.steps:
            if step.status == "GUIDANCE":
                continue
            truncated = step.result[:2000] if step.result else "(no output)"
            results_parts.append(
                f"Step {step.step_id} - {step.title} [{step.tool_name}] ({step.status}):\n{truncated}"
            )
        if not results_parts:
            return None

        all_results = "\n\n".join(results_parts)

        def summarize_call(client, model):
            system_prompt = (
                f"{self._base_identity()}\n"
                f"Required language: {self._lang_str()}\n"
                "Summarize the agent loop results for the user in readable Markdown: "
                "use # / ## headings, short sections, and fenced code blocks for any code."
            )
            prompt = (
                f"Goal: {self.current_plan.goal}\n"
                f"Plan: {self.current_plan.summary}\n\n"
                f"Actions:\n{all_results}"
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                ),
            )
            return response.text

        result = self.config_mgr.execute_with_auto_rotation(
            summarize_call, on_rotate_callback=self.on_key_rotated
        )
        return result if result and result.strip() else None
