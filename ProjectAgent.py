import customtkinter as ctk
from pathlib import Path
import os
import sys
import ctypes

from core.config_manager import ConfigManager
from core.agent_engine import AgentEngine
from core.i18n import I18n
from ui.theme import Theme
from ui.views.chat_view import ChatView
from ui.views.plan_view import PlanView
from ui.views.settings_view import SettingsView

try:
    myappid = "projectagent.app.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass


def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).resolve().parent
    return os.path.join(base_path, relative_path)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Project Agent")
        icon_path = get_resource_path(os.path.join("icon", "star.ico"))
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.geometry("1100x780")

        self.minsize(900, 650)
        self.configure(fg_color=Theme.BG_DARK)

        # Center on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = (screen_w // 2) - (1100 // 2)
        pos_y = (screen_h // 2) - (780 // 2)
        self.geometry(f"1100x780+{pos_x}+{pos_y}")

        # Core Services
        self.config_mgr = ConfigManager()
        self.engine = AgentEngine()

        # Build UI Layout
        self._build_layout()
        self._setup_engine_callbacks()

        # Show ChatView by default
        self.switch_view("chat")

    def _build_layout(self):
        # 1. Sidebar (Left)
        self.sidebar = ctk.CTkFrame(
            self, fg_color=Theme.SIDEBAR_BG, width=220, corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # App Brand Title
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=16, pady=(20, 24))

        ctk.CTkLabel(
            brand_frame,
            text="⚡Project Agent",
            font=(Theme.FONT_FAMILY, 20, "bold"),
            text_color="#ffffff",
            anchor="w",
        ).pack(fill="x")

        self.lbl_subtitle = ctk.CTkLabel(
            brand_frame,
            text=I18n.t("brand_subtitle"),
            font=(Theme.FONT_FAMILY, 12),
            text_color=Theme.TEXT_MUTED,
            anchor="w",
        )
        self.lbl_subtitle.pack(fill="x")

        # Nav Buttons
        self.btn_nav_chat = self._create_nav_button(I18n.t("chat_nav"), "chat")
        self.btn_nav_plan = self._create_nav_button(I18n.t("plan_nav"), "plan")
        self.btn_nav_settings = self._create_nav_button(
            I18n.t("settings_nav"), "settings"
        )

        self._update_sidebar_info()

        # 2. Main Content Container (Right)
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(side="right", fill="both", expand=True)

        # Initialize Views
        self.view_chat = ChatView(
            self.content_frame,
            engine=self.engine,
            on_switch_to_plan=lambda: self.switch_view("plan"),
        )
        self.view_plan = PlanView(self.content_frame, engine=self.engine)
        self.view_settings = SettingsView(
            self.content_frame,
            on_key_changed=self._on_key_pool_updated,
            on_lang_changed=self._reload_all_languages,
        )

    def _create_nav_button(self, text: str, view_id: str):
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            font=(Theme.FONT_FAMILY, 14, "bold"),
            fg_color="transparent",
            text_color=Theme.TEXT_PRIMARY,
            hover_color=Theme.CARD_BG,
            anchor="w",
            height=44,
            corner_radius=8,
            command=lambda: self.switch_view(view_id),
        )
        btn.pack(fill="x", padx=12, pady=4)
        return btn

    def switch_view(self, view_id: str):
        # Hide all views
        self.view_chat.pack_forget()
        self.view_plan.pack_forget()
        self.view_settings.pack_forget()

        # Reset button styles
        for btn in [self.btn_nav_chat, self.btn_nav_plan, self.btn_nav_settings]:
            btn.configure(fg_color="transparent")

        if view_id == "chat":
            self.view_chat.pack(fill="both", expand=True)
            self.btn_nav_chat.configure(fg_color=Theme.CARD_BG)
        elif view_id == "plan":
            self.view_plan.pack(fill="both", expand=True)
            self.btn_nav_plan.configure(fg_color=Theme.CARD_BG)
        elif view_id == "settings":
            self.view_settings.pack(fill="both", expand=True)
            self.btn_nav_settings.configure(fg_color=Theme.CARD_BG)

    def _update_sidebar_info(self):
        pass

    def _reload_all_languages(self):
        self.btn_nav_chat.configure(text=I18n.t("chat_nav"))
        self.btn_nav_plan.configure(text=I18n.t("plan_nav"))
        self.btn_nav_settings.configure(text=I18n.t("settings_nav"))
        self.lbl_subtitle.configure(text=I18n.t("brand_subtitle"))
        self._update_sidebar_info()
        self.view_chat.reload_text()
        self.view_plan.reload_text()
        self.view_settings.reload_text()

    def _on_key_pool_updated(self):
        self._update_sidebar_info()

    def _setup_engine_callbacks(self):
        def on_msg(sender, text, is_user):
            self.after(0, self.view_chat.add_message, sender, text, is_user)

        def on_plan_ready(plan):
            self.after(0, self.view_plan.load_plan, plan)
            self.after(0, self.view_chat.add_plan_card, plan)

        def on_step_update(step_idx, status, result):
            self.after(0, self.view_plan.update_step, step_idx, status, result)

        def on_step_appended(step, step_idx):
            self.after(0, self.view_plan.append_step, step, step_idx)

        def on_approval_required(step_idx, tool_name, tool_args, approve_fn, reject_fn):
            def show_approval():
                self.switch_view("plan")
                self.view_plan.add_approval_card(
                    step_idx, tool_name, tool_args, approve_fn, reject_fn
                )

            self.after(0, show_approval)

        def on_status_change(status_text):
            self.after(0, self.view_chat.set_status, status_text)
            self.after(0, self.view_plan.set_status, status_text)
            if status_text == "Operation completed":
                self.after(0, self.view_chat.mark_plan_executed)

        def on_key_rotated(msg):
            self.after(0, self.view_chat.add_message, "System", f" {msg}", False)
            self.after(0, self._update_sidebar_info)

        self.engine.set_callbacks(
            on_message=on_msg,
            on_plan_ready=on_plan_ready,
            on_step_update=on_step_update,
            on_step_appended=on_step_appended,
            on_approval_required=on_approval_required,
            on_status_change=on_status_change,
            on_key_rotated=on_key_rotated,
        )


if __name__ == "__main__":
    app = App()
    app.mainloop()
