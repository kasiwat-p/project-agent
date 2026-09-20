import customtkinter as ctk
from ui.theme import Theme
from ui.components import StepItemWidget, ApprovalCard
from core.i18n import I18n


class PlanView(ctk.CTkFrame):
    def __init__(self, master, engine, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.engine = engine
        self.step_widgets: list[StepItemWidget] = []
        self._approval_card = None

        # 1. Header & Controls
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 10))

        self.lbl_title = ctk.CTkLabel(
            header,
            text=I18n.t("plan_inspector_title"),
            font=(Theme.FONT_FAMILY, 17, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_title.pack(side="left")

        self.btn_proceed = ctk.CTkButton(
            header,
            text=I18n.t("proceed_btn"),
            font=(Theme.FONT_FAMILY, 13, "bold"),
            fg_color="#ffffff",
            text_color="#000000",
            hover_color="#e5e5e5",
            height=34,
            command=self._on_proceed,
        )
        self.btn_proceed.pack(side="right", padx=(6, 0))

        self.lbl_exec_status = ctk.CTkLabel(
            header,
            text="",
            font=(Theme.FONT_FAMILY, 12),
            text_color=Theme.TEXT_SECONDARY,
        )
        self.lbl_exec_status.pack(side="right", padx=(0, 10))

        # 2. Plan Info Card
        self.info_card = ctk.CTkFrame(
            self,
            fg_color="#2f2f2f",
            border_color="#383838",
            border_width=1,
            corner_radius=10,
        )
        self.info_card.pack(fill="x", padx=20, pady=5)

        self.lbl_goal = ctk.CTkLabel(
            self.info_card,
            text=I18n.t("no_plan_goal"),
            font=(Theme.FONT_FAMILY, 15, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
            wraplength=650,
            justify="left",
        )
        self.lbl_goal.pack(fill="x", padx=16, pady=(12, 4))

        self.lbl_summary = ctk.CTkLabel(
            self.info_card,
            text=I18n.t("no_plan_summary"),
            font=(Theme.FONT_FAMILY, 14),
            text_color=Theme.TEXT_SECONDARY,
            anchor="w",
            wraplength=650,
            justify="left",
        )
        self.lbl_summary.pack(fill="x", padx=16, pady=(0, 12))

        self.approval_host = ctk.CTkFrame(self, fg_color="transparent")

        # 3. Steps Scrollable Frame
        self.steps_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.steps_frame.pack(fill="both", expand=True, padx=20, pady=10)
        if hasattr(self.steps_frame, "_scrollbar"):
            try:
                self.steps_frame._scrollbar.grid_remove()
            except Exception:
                pass

    def reload_text(self):
        self.lbl_title.configure(text=I18n.t("plan_inspector_title"))
        if self.engine.current_plan and self.engine.current_plan.is_executed:
            self.btn_proceed.configure(text=I18n.t("proceed_done"))
        else:
            self.btn_proceed.configure(text=I18n.t("proceed_btn"))
        if not self.engine.current_plan:
            self.lbl_goal.configure(text=I18n.t("no_plan_goal"))
            self.lbl_summary.configure(text=I18n.t("no_plan_summary"))

    def load_plan(self, plan):
        self.clear_approval()
        self.btn_proceed.configure(state="normal", text=I18n.t("proceed_btn"))
        self.lbl_goal.configure(text=f"{I18n.t('goal_prefix')} {plan.goal}")
        self.lbl_summary.configure(text=f"{I18n.t('summary_prefix')} {plan.summary}")

        # Clear existing step widgets
        for w in self.step_widgets:
            w.destroy()
        self.step_widgets.clear()

        # Render step items
        for step in plan.steps:
            widget = StepItemWidget(self.steps_frame, step=step)
            widget.pack(fill="x", pady=5)
            self.step_widgets.append(widget)

    def update_step(self, step_idx: int, status: str, result: str):
        if 0 <= step_idx < len(self.step_widgets):
            self.step_widgets[step_idx].update_status(status, result)

    def append_step(self, step, step_idx: int):
        widget = StepItemWidget(self.steps_frame, step=step)
        widget.pack(fill="x", pady=5)
        if step_idx < len(self.step_widgets):
            self.step_widgets.insert(step_idx, widget)
        else:
            self.step_widgets.append(widget)
        self.steps_frame.update_idletasks()
        try:
            self.steps_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def set_status(self, text: str):
        self.lbl_exec_status.configure(text=text)
        running_tokens = (
            "executing",
            "agent_loop",
            "agent_thinking",
            "analyzing",
            "scouting",
            "waiting_for_user_approval",
            "running",
            "in_progress",
            "updating",
            "summarizing",
        )
        if any(token in text.lower() for token in running_tokens):
            self.btn_proceed.configure(state="disabled")
        if text == "Operation completed":
            self.mark_finished()

    def mark_finished(self):
        self.btn_proceed.configure(state="disabled", text=I18n.t("proceed_done"))

    def add_approval_card(
        self, step_idx: int, tool_name: str, tool_args: dict, approve_fn, reject_fn
    ):
        self.clear_approval()
        self.approval_host.pack(fill="x", padx=20, pady=8, after=self.info_card)

        def wrapped_approve():
            approve_fn()

        def wrapped_reject():
            reject_fn()

        self._approval_card = ApprovalCard(
            self.approval_host,
            step_idx=step_idx,
            tool_name=tool_name,
            tool_args=tool_args,
            on_approve=wrapped_approve,
            on_reject=wrapped_reject,
        )
        self._approval_card.pack(fill="x")

    def clear_approval(self):
        for child in self.approval_host.winfo_children():
            child.destroy()
        self._approval_card = None
        self.approval_host.pack_forget()

    def _on_proceed(self):
        if self.engine.start_execution():
            self.btn_proceed.configure(state="disabled")
