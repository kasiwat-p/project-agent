import customtkinter as ctk
from ui.theme import Theme
from core.i18n import I18n
import json
import re


def _make_readonly_textbox(
    parent, text: str, *, font, fg_color, text_color, height, wrap="word"
):
    """Selectable, copyable text that cannot be edited."""
    box = ctk.CTkTextbox(
        parent,
        font=font,
        fg_color=fg_color,
        text_color=text_color,
        border_width=0,
        height=height,
        wrap=wrap,
        activate_scrollbars=False,
        corner_radius=6,
    )
    box.insert("1.0", text)
    box.configure(state="disabled")

    def _keys(event):
        ctrl = bool(event.state & 0x4)
        if ctrl and event.keysym.lower() in ("c", "a"):
            return None
        return "break"

    box.bind("<Key>", _keys)
    return box


def _line_height(font_size: int, lines: int, extra: int = 16) -> int:
    return max(28, lines * (font_size + 8) + extra)


class CodeBlock(ctk.CTkFrame):
    """Chat-style code fence: language header, copy, readonly code."""

    def __init__(self, master, language: str, code: str, **kwargs):
        super().__init__(
            master,
            fg_color="#1e1e1e",
            border_color="#333333",
            border_width=1,
            corner_radius=10,
            **kwargs,
        )
        self._code = code
        lang = (language or "text").strip() or "text"

        header = ctk.CTkFrame(self, fg_color="#2a2a2a", corner_radius=0, height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=lang,
            font=(Theme.FONT_FAMILY, 12, "bold"),
            text_color=Theme.TEXT_SECONDARY,
        ).pack(side="left", padx=12)

        self.btn_copy = ctk.CTkButton(
            header,
            text="Copy",
            width=56,
            height=22,
            font=(Theme.FONT_FAMILY, 11),
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            text_color=Theme.TEXT_PRIMARY,
            command=self._copy,
        )
        self.btn_copy.pack(side="right", padx=8, pady=4)

        lines = max(1, code.count("\n") + 1)
        box = _make_readonly_textbox(
            self,
            code,
            font=("Consolas", 13),
            fg_color="#1e1e1e",
            text_color="#d4d4d4",
            height=min(_line_height(13, lines, 20), 420),
            wrap="none",
        )
        box.pack(fill="x", padx=8, pady=(4, 10))

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self._code)
        self.btn_copy.configure(text="Copied")
        self.after(1600, lambda: self.btn_copy.configure(text="Copy"))


class ChatBubble(ctk.CTkFrame):
    def __init__(
        self, master, sender: str, text: str, is_user: bool, timestamp: str, **kwargs
    ):
        bg_color = "#2f2f2f" if is_user else "transparent"
        border_color = "#383838" if is_user else "#212121"
        border_w = 1 if is_user else 0
        super().__init__(
            master,
            fg_color=bg_color,
            border_color=border_color,
            border_width=border_w,
            corner_radius=12,
            **kwargs,
        )
        self.full_text = text

        prefix = "You" if is_user else "Agent"
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text=f"{prefix}  •  {timestamp}",
            font=(Theme.FONT_FAMILY, 12, "bold"),
            text_color="#ffffff" if is_user else Theme.TEXT_MUTED,
        ).pack(side="left")

        self.btn_copy = ctk.CTkButton(
            header,
            text="Copy",
            width=56,
            height=22,
            font=(Theme.FONT_FAMILY, 11),
            fg_color="#383838",
            hover_color="#4f4f4f",
            text_color="#d0d0d0",
            command=self._copy_all,
        )
        self.btn_copy.pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 12))
        self._render(body, text, is_user)

    def _copy_all(self):
        self.clipboard_clear()
        self.clipboard_append(self.full_text)
        self.btn_copy.configure(text="Copied")
        self.after(1600, lambda: self.btn_copy.configure(text="Copy"))

    def _render(self, parent, text: str, is_user: bool):
        if is_user:
            lines = max(1, text.count("\n") + 1)
            box = _make_readonly_textbox(
                parent,
                text,
                font=(Theme.FONT_FAMILY, 15),
                fg_color="#2f2f2f",
                text_color=Theme.TEXT_PRIMARY,
                height=_line_height(15, min(lines, 12)),
            )
            box.pack(fill="x", anchor="w")
            return

        parts = re.split(r"(```[\s\S]*?```)", text)
        for part in parts:
            if not part:
                continue
            if part.startswith("```"):
                inner = part[3:]
                if inner.endswith("```"):
                    inner = inner[:-3]
                inner = inner.strip("\n")
                lang = "code"
                if inner:
                    first, _, rest = inner.partition("\n")
                    token = first.strip()
                    if token and " " not in token and len(token) < 24:
                        lang = token
                        inner = rest
                CodeBlock(parent, lang, inner.rstrip()).pack(
                    fill="x", pady=8, anchor="w"
                )
            else:
                self._render_markdown_text(parent, part)

    def _render_markdown_text(self, parent, text: str):
        buffer = []

        def flush():
            if not buffer:
                return
            body = "\n".join(buffer).strip("\n")
            buffer.clear()
            if not body.strip():
                return
            lines = max(1, body.count("\n") + 1)
            box = _make_readonly_textbox(
                parent,
                body,
                font=(Theme.FONT_FAMILY, 15),
                fg_color="transparent",
                text_color=Theme.TEXT_PRIMARY,
                height=_line_height(15, min(lines, 24), 12),
            )
            box.pack(fill="x", anchor="w", pady=2)

        for raw in text.split("\n"):
            line = raw.rstrip()
            heading = None
            if line.startswith("### "):
                heading = (line[4:].strip(), 15)
            elif line.startswith("## "):
                heading = (line[3:].strip(), 17)
            elif line.startswith("# "):
                heading = (line[2:].strip(), 20)
            elif re.match(r"^\*\*.+\*\*$", line.strip()):
                heading = (line.strip().strip("*").strip(), 17)

            if heading:
                flush()
                title, size = heading
                box = _make_readonly_textbox(
                    parent,
                    title,
                    font=(Theme.FONT_FAMILY, size, "bold"),
                    fg_color="transparent",
                    text_color="#ffffff",
                    height=_line_height(size, 1, 8),
                )
                box.pack(fill="x", anchor="w", pady=(10, 2))
            else:
                buffer.append(raw)

        flush()


class PlanCard(ctk.CTkFrame):
    def __init__(self, master, plan, on_proceed, on_refine, **kwargs):
        super().__init__(
            master,
            fg_color="#2f2f2f",
            border_color="#424242",
            border_width=1,
            corner_radius=12,
            **kwargs,
        )
        self.plan = plan
        self.on_proceed = on_proceed
        self.on_refine = on_refine

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            header_frame,
            text=I18n.t("plan_card_title"),
            font=(Theme.FONT_FAMILY, 16, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            self,
            text=f"{I18n.t('goal_prefix')} {plan.goal}",
            font=(Theme.FONT_FAMILY, 14, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            wraplength=650,
            justify="left",
        ).pack(anchor="w", padx=16, pady=3)

        ctk.CTkLabel(
            self,
            text=f"{I18n.t('summary_prefix')} {plan.summary}",
            font=(Theme.FONT_FAMILY, 14),
            text_color=Theme.TEXT_SECONDARY,
            wraplength=650,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        steps_frame = ctk.CTkFrame(self, fg_color="#171717", corner_radius=8)
        steps_frame.pack(fill="x", padx=16, pady=6)

        for step in plan.steps:
            row = ctk.CTkFrame(steps_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=6)
            tool_badge = f"[{step.tool_name}]" if step.tool_name != "none" else ""
            ctk.CTkLabel(
                row,
                text=f"{step.step_id}. {step.title} {tool_badge}",
                font=(Theme.FONT_FAMILY, 14),
                text_color=Theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=16, pady=(14, 12))

        self.btn_proceed = ctk.CTkButton(
            action_frame,
            text=I18n.t("proceed_btn"),
            font=(Theme.FONT_FAMILY, 13, "bold"),
            fg_color="#ffffff",
            text_color="#000000",
            hover_color="#e5e5e5",
            height=38,
            command=self._handle_proceed,
        )
        self.btn_proceed.pack(side="left", padx=(0, 10))

        self.entry_refine = ctk.CTkEntry(
            action_frame,
            placeholder_text=I18n.t("refine_placeholder"),
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            border_color="#424242",
            height=38,
        )
        self.entry_refine.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_refine.bind("<Return>", lambda e: self._handle_refine())

        self.btn_refine = ctk.CTkButton(
            action_frame,
            text=I18n.t("refine_btn"),
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#383838",
            hover_color="#424242",
            width=100,
            height=38,
            command=self._handle_refine,
        )
        self.btn_refine.pack(side="right")

    def _handle_proceed(self):
        started = False
        if self.on_proceed:
            started = bool(self.on_proceed(self.plan))
        if started:
            self.btn_proceed.configure(state="disabled", text="...")

    def _handle_refine(self):
        txt = self.entry_refine.get().strip()
        if txt and self.on_refine:
            self.entry_refine.delete(0, "end")
            self.on_refine(txt)

    def set_inactive(self):
        self.btn_proceed.configure(state="disabled")
        self.btn_refine.configure(state="disabled")
        self.entry_refine.configure(state="disabled")


class ApprovalCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        step_idx: int,
        tool_name: str,
        tool_args: dict,
        on_approve,
        on_reject,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="#2f2f2f",
            border_color="#f59e0b",
            border_width=1,
            corner_radius=12,
            **kwargs,
        )
        self.on_approve = on_approve
        self.on_reject = on_reject

        ctk.CTkLabel(
            self,
            text=I18n.t("approval_title", tool_name=tool_name),
            font=(Theme.FONT_FAMILY, 15, "bold"),
            text_color=Theme.WARNING_COLOR,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        args_text = json.dumps(tool_args, ensure_ascii=False, indent=2)
        args_box = _make_readonly_textbox(
            self,
            f"{I18n.t('params_label')}\n{args_text}",
            font=("Consolas", 12),
            fg_color="#171717",
            text_color=Theme.TEXT_PRIMARY,
            height=min(_line_height(12, args_text.count("\n") + 2, 24), 220),
            wrap="none",
        )
        args_box.pack(fill="x", padx=16, pady=6)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(10, 14))

        self.btn_ok = ctk.CTkButton(
            btn_frame,
            text=I18n.t("approve_btn"),
            font=(Theme.FONT_FAMILY, 13, "bold"),
            fg_color="#ffffff",
            text_color="#000000",
            hover_color="#e5e5e5",
            height=36,
            command=self._approve,
        )
        self.btn_ok.pack(side="left", padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            btn_frame,
            text=I18n.t("reject_btn"),
            font=(Theme.FONT_FAMILY, 13, "bold"),
            fg_color="#383838",
            text_color="#ffffff",
            hover_color="#424242",
            height=36,
            command=self._reject,
        )
        self.btn_cancel.pack(side="left")

    def _approve(self):
        self.btn_ok.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        if self.on_approve:
            self.on_approve()

    def _reject(self):
        self.btn_ok.configure(state="disabled")
        self.btn_cancel.configure(state="disabled")
        if self.on_reject:
            self.on_reject()


class StepItemWidget(ctk.CTkFrame):
    STATUS_COLORS = {
        "PENDING": ("#ffffff", "Pending"),
        "GUIDANCE": ("#737373", "Guidance"),
        "RUNNING": ("#ffffff", "Running"),
        "SUCCESS": ("#ffffff", "Success"),
        "FAILED": ("#ffffff", "Failed"),
        "SKIPPED": ("#ffffff", "Skipped"),
    }

    def __init__(self, master, step, **kwargs):
        super().__init__(
            master,
            fg_color="#2f2f2f",
            border_color="#383838",
            border_width=1,
            corner_radius=10,
            **kwargs,
        )
        self.step = step

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(12, 6))

        tool_badge = f"[{step.tool_name}]" if step.tool_name != "none" else ""
        self.lbl_title = ctk.CTkLabel(
            row,
            text=f"Step {step.step_id}: {step.title} {tool_badge}",
            font=(Theme.FONT_FAMILY, 15, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_title.pack(side="left", fill="x", expand=True)

        color, label = self.STATUS_COLORS.get(step.status, ("#737373", step.status))
        self.lbl_status = ctk.CTkLabel(
            row,
            text=label,
            font=(Theme.FONT_FAMILY, 13, "bold"),
            text_color=color,
        )
        self.lbl_status.pack(side="right")

        if step.description:
            ctk.CTkLabel(
                self,
                text=step.description,
                font=(Theme.FONT_FAMILY, 14),
                text_color=Theme.TEXT_SECONDARY,
                anchor="w",
                wraplength=600,
                justify="left",
            ).pack(anchor="w", padx=14, pady=(0, 8))

        self.result_frame = ctk.CTkFrame(self, fg_color="#171717", corner_radius=6)
        self.lbl_result = ctk.CTkLabel(
            self.result_frame,
            text="",
            font=("Consolas", 12),
            text_color="#ececec",
            justify="left",
            wraplength=580,
            anchor="w",
        )
        self.lbl_result.pack(fill="x", padx=10, pady=8)

        if step.result:
            self.update_status(step.status, step.result)

    def update_status(self, status: str, result: str = ""):
        self.step.status = status
        self.step.result = result
        color, label = self.STATUS_COLORS.get(status, ("#737373", status))
        self.lbl_status.configure(text=label, text_color=color)

        if result:
            self.result_frame.pack(fill="x", padx=14, pady=(0, 12))
            self.lbl_result.configure(text=result[:4000])
        else:
            self.result_frame.pack_forget()


class KeyItemWidget(ctk.CTkFrame):
    def __init__(
        self,
        master,
        key_data: dict,
        index: int,
        is_active: bool,
        on_set_active,
        on_test,
        on_delete,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color="#2f2f2f",
            border_color="#383838",
            border_width=1,
            corner_radius=10,
            **kwargs,
        )
        self.key_data = key_data
        self.index = index

        key_str = key_data.get("key", "")
        masked_key = f"{key_str[:6]}...{key_str[-4:]}" if len(key_str) > 10 else key_str
        label_text = key_data.get("label", f"Key #{index + 1}")

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        title_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        title_row.pack(fill="x", anchor="w")

        ctk.CTkLabel(
            title_row,
            text=label_text,
            font=(Theme.FONT_FAMILY, 15, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        if is_active:
            ctk.CTkLabel(
                title_row,
                text="  ACTIVE KEY",
                font=(Theme.FONT_FAMILY, 12, "bold"),
                text_color="#ffffff",
            ).pack(side="left")

        provider = key_data.get("provider") or ""
        provider_name = "OpenRouter" if provider == "openrouter" else "Google Gemini"
        ctk.CTkLabel(
            info_frame,
            text=f"{provider_name} | Key: {masked_key} | Status: {key_data.get('status', 'active')}",
            font=(Theme.FONT_FAMILY, 13),
            text_color=Theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(4, 0))

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(side="right", padx=14, pady=12)

        if not is_active:
            ctk.CTkButton(
                action_frame,
                text=I18n.t("set_active_btn"),
                font=(Theme.FONT_FAMILY, 12),
                width=85,
                height=34,
                fg_color="#ffffff",
                text_color="#000000",
                hover_color="#e5e5e5",
                command=lambda: on_set_active(index),
            ).pack(side="left", padx=4)

        ctk.CTkButton(
            action_frame,
            text=I18n.t("test_btn"),
            font=(Theme.FONT_FAMILY, 12),
            width=65,
            height=34,
            fg_color="#383838",
            hover_color="#424242",
            command=lambda: on_test(key_str, key_data.get("provider", "")),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            action_frame,
            text=I18n.t("delete_btn"),
            font=(Theme.FONT_FAMILY, 12),
            width=65,
            height=34,
            fg_color=Theme.DANGER_BG,
            hover_color=Theme.DANGER_COLOR,
            command=lambda: on_delete(index),
        ).pack(side="left", padx=4)
