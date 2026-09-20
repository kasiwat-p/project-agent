import customtkinter as ctk
from datetime import datetime
import threading
from pathlib import Path

from ui.theme import Theme
from ui.components import ChatBubble, PlanCard, ApprovalCard
from core.i18n import I18n

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class ChatView(ctk.CTkFrame):
    def __init__(self, master, engine, on_switch_to_plan, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.engine = engine
        self.on_switch_to_plan = on_switch_to_plan
        self.is_listening = False
        self.plan_cards: list[PlanCard] = []

        # 1. Header Bar
        header = ctk.CTkFrame(self, fg_color="transparent", height=40)
        header.pack(fill="x", padx=20, pady=(15, 5))

        self.lbl_status = ctk.CTkLabel(
            header,
            text=f"⚡ {I18n.t('idle_status')}",
            font=(Theme.FONT_FAMILY, 13, "bold"),
            text_color=Theme.SUCCESS_COLOR,
        )
        self.lbl_status.pack(side="left")

        # 2. Chat Scrollable Frame — thin muted scrollbar
        self.chat_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_fg_color="transparent",
            scrollbar_button_color="#3a3a3a",
            scrollbar_button_hover_color="#555555",
        )
        self.chat_frame.pack(fill="both", expand=True, padx=(20, 8), pady=5)
        self._style_chat_scrollbar()
        self._bind_chat_mousewheel()

        # 3.Input Bar
        # input_container = ctk.CTkFrame(
        #     self,
        #     fg_color="#2f2f2f",
        #     border_color="#383838",
        #     border_width=1,
        #     corner_radius=24,
        # )
        # input_container.pack(fill="x", padx=40, pady=(10, 20))

        # Text Entry
        self.entry = ctk.CTkEntry(
            self,
            placeholder_text=I18n.t("input_placeholder"),
            font=(Theme.FONT_FAMILY, 15),
            # fg_color="transparent",
            fg_color="#2f2f2f",
            border_width=1,
            border_color="#383838",
            height=48,
            corner_radius=24,
        )
        self.entry.pack(
            side="left", fill="x", expand=True, padx=(16, 16), pady=(10, 20)
        )
        self.entry.bind("<Return>", lambda e: self.send_message())

        # # Send Button
        # self.btn_send = ctk.CTkButton(
        #     input_container,
        #     text="▲",
        #     font=(Theme.FONT_FAMILY, 14, "bold"),
        #     width=38,
        #     height=38,
        #     corner_radius=19,
        #     fg_color="#ffffff",
        #     text_color="#000000",
        #     hover_color="#e5e5e5",
        #     command=self.send_message,
        # )

        # self.btn_send.pack(side="right", padx=(0, 8))

        # Welcome message
        self.add_message(
            "Agent Mini",
            I18n.t("welcome_msg"),
            is_user=False,
        )

    def reload_text(self):
        self.set_status(I18n.t("idle_status"))
        self.entry.configure(placeholder_text=I18n.t("input_placeholder"))

    def set_status(self, text: str):
        is_ready = any(x in text.lower() for x in ["idle", "พร้อมทำงาน", "ready"])
        color = Theme.SUCCESS_COLOR if is_ready else Theme.DANGER_COLOR
        self.lbl_status.configure(text=f"⚡ {text}", text_color=color)

    def add_message(self, sender: str, text: str, is_user: bool = False):
        now = datetime.now().strftime("%H:%M")
        align = "e" if is_user else "w"
        bubble = ChatBubble(
            self.chat_frame, sender=sender, text=text, is_user=is_user, timestamp=now
        )
        bubble.pack(anchor=align, padx=10, pady=6, fill="x")
        self._scroll_to_bottom()

    def add_plan_card(self, plan):
        for card in self.plan_cards:
            card.set_inactive()
        card = PlanCard(
            self.chat_frame,
            plan=plan,
            on_proceed=self._on_plan_proceed,
            on_refine=self._on_plan_refine,
        )
        card.pack(fill="x", padx=10, pady=8)
        self.plan_cards.append(card)
        self._scroll_to_bottom()

    def add_approval_card(
        self, step_idx: int, tool_name: str, tool_args: dict, approve_fn, reject_fn
    ):
        card = ApprovalCard(
            self.chat_frame,
            step_idx=step_idx,
            tool_name=tool_name,
            tool_args=tool_args,
            on_approve=approve_fn,
            on_reject=reject_fn,
        )
        card.pack(fill="x", padx=10, pady=8)
        self._scroll_to_bottom()

    def send_message(self):
        txt = self.entry.get().strip()
        if not txt:
            return
        if self.engine.is_running:
            self.add_message("System", I18n.t("agent_busy"), is_user=False)
            return
        self.entry.delete(0, "end")
        self.add_message("You", txt, is_user=True)
        self.engine.handle_user_input(txt)

    def mark_plan_executed(self):
        if self.plan_cards:
            self.plan_cards[-1].set_inactive()

    def _on_plan_proceed(self, plan) -> bool:
        started = self.engine.start_execution(expected_plan=plan)
        if started and self.on_switch_to_plan:
            self.on_switch_to_plan()
        return started

    def _on_plan_refine(self, feedback: str):
        if self.engine.is_running:
            self.add_message("System", I18n.t("agent_busy"), is_user=False)
            return
        self.add_message("You", f"Modify Plan: {feedback}", is_user=True)
        self.engine.refine_plan(feedback)

    def _on_voice_done(self, text: str):
        self.is_listening = False
        self.btn_voice.configure(text="mic", fg_color="transparent")
        if not self.engine.is_running:
            self.set_status(I18n.t("idle_status"))

        if text and not text.startswith("Error"):
            self.entry.delete(0, "end")
            self.entry.insert(0, text)
            self.send_message()
        elif text and text.startswith("Error"):
            self.add_message("System", text, is_user=False)

    def _style_chat_scrollbar(self):
        bar = getattr(self.chat_frame, "_scrollbar", None)
        if bar is None:
            return
        try:
            bar.configure(
                width=8,
                corner_radius=8,
                fg_color="transparent",
                button_color="#3a3a3a",
                button_hover_color="#555555",
            )
        except Exception:
            pass

    def _bind_chat_mousewheel(self):
        canvas = getattr(self.chat_frame, "_parent_canvas", None)
        if canvas is None:
            return

        def _on_wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")
            return "break"

        def _bind(_event=None):
            self.bind("<MouseWheel>", _on_wheel)
            self.bind("<Button-4>", _on_wheel)
            self.bind("<Button-5>", _on_wheel)

        def _unbind(_event=None):
            self.unbind("<MouseWheel>")
            self.unbind("<Button-4>")
            self.unbind("<Button-5>")

        self.chat_frame.bind("<Enter>", _bind)
        self.chat_frame.bind("<Leave>", _unbind)

    def _scroll_to_bottom(self):
        self.chat_frame.update_idletasks()
        try:
            self.chat_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
