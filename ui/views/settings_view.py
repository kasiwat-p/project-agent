import customtkinter as ctk
import threading
from tkinter import filedialog
from ui.theme import Theme
from ui.components import KeyItemWidget
from core.config_manager import ConfigManager
from core.i18n import I18n
from core.llm_client import PROVIDER_GOOGLE, PROVIDER_OPENROUTER

GEMINI_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, on_key_changed=None, on_lang_changed=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.config_mgr = ConfigManager()
        self.on_key_changed = on_key_changed
        self.on_lang_changed = on_lang_changed
        self.key_widgets: list[KeyItemWidget] = []

        # 1. Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 10))

        self.lbl_header = ctk.CTkLabel(
            header,
            text=I18n.t("settings_title"),
            font=(Theme.FONT_FAMILY, 17, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_header.pack(side="left")

        # Scrollable Container
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=5)
        if hasattr(self.container, "_scrollbar"):
            try:
                self.container._scrollbar.grid_remove()
            except Exception:
                pass

        # 2. Add Key Card
        self._build_add_key_card()

        # 3. Keys List Section
        self.lbl_pool_title = ctk.CTkLabel(
            self.container,
            text=I18n.t("keys_pool_title"),
            font=(Theme.FONT_FAMILY, 14, "bold"),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
        )
        self.lbl_pool_title.pack(fill="x", pady=(15, 6))

        self.keys_list_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        self.keys_list_frame.pack(fill="x", pady=5)

        # 4. Model & Preferences Card
        self._build_preferences_card()

        # Load initial keys
        self.refresh_keys_list()

    def _build_add_key_card(self):
        self.card_add = ctk.CTkFrame(
            self.container,
            fg_color="#2f2f2f",
            border_color="#383838",
            border_width=1,
            corner_radius=10,
        )
        self.card_add.pack(fill="x", pady=5)

        self.lbl_add_title = ctk.CTkLabel(
            self.card_add,
            text=I18n.t("add_key_title"),
            font=(Theme.FONT_FAMILY, 15, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_add_title.pack(anchor="w", padx=16, pady=(12, 8))

        row_provider = ctk.CTkFrame(self.card_add, fg_color="transparent")
        row_provider.pack(fill="x", padx=16, pady=(0, 4))

        self.lbl_provider = ctk.CTkLabel(
            row_provider,
            text=I18n.t("provider_label"),
            font=(Theme.FONT_FAMILY, 13),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_provider.pack(side="left", padx=(0, 10))

        self.opt_provider = ctk.CTkOptionMenu(
            row_provider,
            values=[I18n.t("provider_google"), I18n.t("provider_openrouter")],
            command=self._on_provider_selected,
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            button_color="#383838",
            button_hover_color="#424242",
            height=32,
            width=180,
        )
        self.opt_provider.set(I18n.t("provider_google"))
        self.opt_provider.pack(side="left")

        row1 = ctk.CTkFrame(self.card_add, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=4)

        self.entry_key = ctk.CTkEntry(
            row1,
            placeholder_text=I18n.t("key_entry_ph_google"),
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            border_color="#424242",
            show="•",
            height=38,
        )
        self.entry_key.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry_key.bind("<KeyRelease>", self._on_key_typed)

        self.entry_label = ctk.CTkEntry(
            row1,
            placeholder_text=I18n.t("label_entry_ph"),
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            border_color="#424242",
            width=190,
            height=38,
        )
        self.entry_label.pack(side="left", padx=(0, 8))

        self.btn_add = ctk.CTkButton(
            row1,
            text=I18n.t("save_key_btn"),
            font=(Theme.FONT_FAMILY, 13, "bold"),
            fg_color="#ffffff",
            text_color="#000000",
            hover_color="#e5e5e5",
            width=100,
            height=38,
            command=self._handle_add_key,
        )
        self.btn_add.pack(side="right")

        self.lbl_add_status = ctk.CTkLabel(
            self.card_add,
            text="",
            font=(Theme.FONT_FAMILY, 12),
            text_color=Theme.SUCCESS_COLOR,
        )
        self.lbl_add_status.pack(anchor="w", padx=16, pady=(0, 10))

    def _build_preferences_card(self):
        self.card_pref = ctk.CTkFrame(
            self.container,
            fg_color="#2f2f2f",
            border_color="#383838",
            border_width=1,
            corner_radius=10,
        )
        self.card_pref.pack(fill="x", pady=(15, 10))

        self.lbl_pref_title = ctk.CTkLabel(
            self.card_pref,
            text=I18n.t("preferences_title"),
            font=(Theme.FONT_FAMILY, 15, "bold"),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_pref_title.pack(anchor="w", padx=16, pady=(12, 8))

        # Model Selector
        self.row_model = ctk.CTkFrame(self.card_pref, fg_color="transparent")
        self.row_model.pack(fill="x", padx=16, pady=4)

        self.lbl_model = ctk.CTkLabel(
            self.row_model,
            text=I18n.t("model_label"),
            font=(Theme.FONT_FAMILY, 14),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_model.pack(side="left", padx=(0, 10))

        self.model_host = ctk.CTkFrame(self.row_model, fg_color="transparent")
        self.model_host.pack(side="left", fill="x", expand=True)

        current_model = self.config_mgr.config.get("model", "gemini-3.5-flash-lite")
        models = list(GEMINI_MODELS)
        if current_model not in models:
            models.insert(0, current_model)

        self.opt_model = ctk.CTkOptionMenu(
            self.model_host,
            values=models,
            command=self._on_model_selected,
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            button_color="#383838",
            button_hover_color="#424242",
            height=36,
            width=260,
        )
        self.opt_model.set(current_model)

        self.entry_model = ctk.CTkEntry(
            self.model_host,
            placeholder_text=I18n.t("model_custom_ph"),
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            border_color="#424242",
            height=36,
        )
        self.entry_model.bind("<Return>", lambda e: self._save_openrouter_model())

        self.btn_save_model = ctk.CTkButton(
            self.model_host,
            text=I18n.t("save_model_btn"),
            font=(Theme.FONT_FAMILY, 12),
            fg_color="#ffffff",
            text_color="#000000",
            hover_color="#e5e5e5",
            width=110,
            height=36,
            command=self._save_openrouter_model,
        )

        self.lbl_model_hint = ctk.CTkLabel(
            self.card_pref,
            text=I18n.t("model_custom_hint"),
            font=(Theme.FONT_FAMILY, 11),
            text_color=Theme.TEXT_MUTED,
            anchor="w",
        )

        self._refresh_model_controls()

        # Language Selector
        row_lang = ctk.CTkFrame(self.card_pref, fg_color="transparent")
        row_lang.pack(fill="x", padx=16, pady=8)

        self.lbl_lang = ctk.CTkLabel(
            row_lang,
            text=I18n.t("language_label"),
            font=(Theme.FONT_FAMILY, 14),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_lang.pack(side="left", padx=(0, 10))

        current_lang = I18n.get_lang()
        lang_display = "ไทย (Thai)" if current_lang == "th" else "English"

        self.opt_lang = ctk.CTkOptionMenu(
            row_lang,
            values=["ไทย (Thai)", "English"],
            command=self._on_language_selected,
            font=(Theme.FONT_FAMILY, 13),
            fg_color="#171717",
            button_color="#383838",
            button_hover_color="#424242",
            height=36,
        )
        self.opt_lang.set(lang_display)
        self.opt_lang.pack(side="left")

        # Workspace Folder
        row_ws_label = ctk.CTkFrame(self.card_pref, fg_color="transparent")
        row_ws_label.pack(fill="x", padx=16, pady=(8, 2))

        self.lbl_workspace = ctk.CTkLabel(
            row_ws_label,
            text=I18n.t("workspace_label"),
            font=(Theme.FONT_FAMILY, 14),
            text_color=Theme.TEXT_PRIMARY,
        )
        self.lbl_workspace.pack(side="left")

        self.lbl_ws_hint = ctk.CTkLabel(
            self.card_pref,
            text=I18n.t("workspace_hint"),
            font=(Theme.FONT_FAMILY, 11),
            text_color=Theme.TEXT_MUTED,
            anchor="w",
        )
        self.lbl_ws_hint.pack(fill="x", padx=16, pady=(0, 4))

        row_ws = ctk.CTkFrame(self.card_pref, fg_color="transparent")
        row_ws.pack(fill="x", padx=16, pady=(0, 4))

        self.lbl_ws_path = ctk.CTkLabel(
            row_ws,
            text="",
            font=(Theme.FONT_FAMILY, 12),
            text_color=Theme.TEXT_PRIMARY,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self.lbl_ws_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_ws_clear = ctk.CTkButton(
            row_ws,
            text=I18n.t("workspace_clear"),
            font=(Theme.FONT_FAMILY, 12),
            fg_color="#171717",
            text_color=Theme.TEXT_PRIMARY,
            hover_color="#383838",
            border_color="#424242",
            border_width=1,
            width=80,
            height=32,
            command=self._clear_workspace,
        )
        self.btn_ws_clear.pack(side="right")

        self.btn_ws_browse = ctk.CTkButton(
            row_ws,
            text=I18n.t("workspace_browse"),
            font=(Theme.FONT_FAMILY, 12),
            fg_color="#171717",
            text_color=Theme.TEXT_PRIMARY,
            hover_color="#383838",
            border_color="#424242",
            border_width=1,
            width=90,
            height=32,
            command=self._browse_workspace,
        )
        self.btn_ws_browse.pack(side="right", padx=(0, 4))

        self._refresh_workspace_label()

        # Auto Approve Switch
        self.switch_auto_approve = ctk.CTkSwitch(
            self.card_pref,
            text=I18n.t("auto_approve_label"),
            font=(Theme.FONT_FAMILY, 13),
            command=self._on_auto_approve_toggled,
            progress_color="#ffffff",
        )
        if self.config_mgr.config.get("auto_approve_safe_tools", False):
            self.switch_auto_approve.select()
        self.switch_auto_approve.pack(anchor="w", padx=16, pady=(12, 16))

    def reload_text(self):
        self.lbl_header.configure(text=I18n.t("settings_title"))
        self.lbl_add_title.configure(text=I18n.t("add_key_title"))
        self.lbl_provider.configure(text=I18n.t("provider_label"))
        current_provider = self._selected_provider()
        self.opt_provider.configure(
            values=[I18n.t("provider_google"), I18n.t("provider_openrouter")]
        )
        self.opt_provider.set(
            I18n.t("provider_openrouter")
            if current_provider == PROVIDER_OPENROUTER
            else I18n.t("provider_google")
        )
        self._update_key_placeholder()
        self.entry_label.configure(placeholder_text=I18n.t("label_entry_ph"))
        self.btn_add.configure(text=I18n.t("save_key_btn"))
        self.lbl_pool_title.configure(text=I18n.t("keys_pool_title"))
        self.lbl_pref_title.configure(text=I18n.t("preferences_title"))
        self.lbl_model.configure(text=I18n.t("model_label"))
        self.entry_model.configure(placeholder_text=I18n.t("model_custom_ph"))
        self.btn_save_model.configure(text=I18n.t("save_model_btn"))
        self.lbl_model_hint.configure(text=I18n.t("model_custom_hint"))
        self.lbl_lang.configure(text=I18n.t("language_label"))
        self.switch_auto_approve.configure(text=I18n.t("auto_approve_label"))
        self.lbl_workspace.configure(text=I18n.t("workspace_label"))
        self.lbl_ws_hint.configure(text=I18n.t("workspace_hint"))
        self.btn_ws_browse.configure(text=I18n.t("workspace_browse"))
        self.btn_ws_clear.configure(text=I18n.t("workspace_clear"))
        self._refresh_workspace_label()
        self.refresh_keys_list()

    def refresh_keys_list(self):
        for w in self.key_widgets:
            w.destroy()
        self.key_widgets.clear()

        keys = self.config_mgr.get_all_keys()
        active_idx = self.config_mgr.config.get("active_key_index", 0)

        if not keys:
            ctk.CTkLabel(
                self.keys_list_frame,
                text=I18n.t("no_keys_text"),
                font=(Theme.FONT_FAMILY, 13),
                text_color=Theme.TEXT_MUTED,
            ).pack(pady=10)
            return

        for idx, k in enumerate(keys):
            w = KeyItemWidget(
                self.keys_list_frame,
                key_data=k,
                index=idx,
                is_active=(idx == active_idx),
                on_set_active=self._on_set_active_key,
                on_test=self._on_test_key,
                on_delete=self._on_delete_key,
            )
            w.pack(fill="x", pady=4)
            self.key_widgets.append(w)

    def _handle_add_key(self):
        key = self.entry_key.get().strip()
        label = self.entry_label.get().strip()

        if not key:
            self.lbl_add_status.configure(
                text=I18n.t("enter_key_err"), text_color=Theme.DANGER_COLOR
            )
            return

        provider = self._selected_provider()
        self.btn_add.configure(state="disabled", text="...")
        self.lbl_add_status.configure(
            text=I18n.t("testing_key"), text_color=Theme.TEXT_PRIMARY
        )

        def test_and_add():
            valid, msg = self.config_mgr.test_key(key, provider)
            self.after(0, self._on_add_key_done, valid, key, label, provider, msg)

        threading.Thread(target=test_and_add, daemon=True).start()

    def _on_add_key_done(
        self, valid: bool, key: str, label: str, provider: str, msg: str
    ):
        self.btn_add.configure(state="normal", text=I18n.t("save_key_btn"))
        if valid:
            ok, res_msg = self.config_mgr.add_key(key, label, provider)
            self.lbl_add_status.configure(
                text=f"{res_msg}", text_color=Theme.SUCCESS_COLOR
            )
            self.entry_key.delete(0, "end")
            self.entry_label.delete(0, "end")
            self.refresh_keys_list()
            self._refresh_model_controls()
            if self.on_key_changed:
                self.on_key_changed()
        else:
            self.lbl_add_status.configure(text=f"{msg}", text_color=Theme.DANGER_COLOR)

    def _on_set_active_key(self, index: int):
        self.config_mgr.set_active_key(index)
        self.refresh_keys_list()
        self._refresh_model_controls()
        if self.on_key_changed:
            self.on_key_changed()

    def _on_test_key(self, key: str, provider: str = ""):
        def test_worker():
            valid, msg = self.config_mgr.test_key(key, provider)
            self.after(
                0,
                lambda: self.lbl_add_status.configure(
                    text=f"{'OK' if valid else ' ' + msg}",
                    text_color=Theme.SUCCESS_COLOR if valid else Theme.DANGER_COLOR,
                ),
            )

        threading.Thread(target=test_worker, daemon=True).start()

    def _on_delete_key(self, index: int):
        self.config_mgr.remove_key(index)
        self.refresh_keys_list()
        self._refresh_model_controls()
        if self.on_key_changed:
            self.on_key_changed()

    def _selected_provider(self) -> str:
        value = self.opt_provider.get()
        if value == I18n.t("provider_openrouter") or value == "OpenRouter":
            return PROVIDER_OPENROUTER
        return PROVIDER_GOOGLE

    def _on_provider_selected(self, _value: str):
        self._update_key_placeholder()

    def _on_key_typed(self, _event=None):
        key = self.entry_key.get().strip()
        if key.startswith("sk-or-"):
            wanted = I18n.t("provider_openrouter")
        elif key.startswith("AIza"):
            wanted = I18n.t("provider_google")
        else:
            return
        if self.opt_provider.get() != wanted:
            self.opt_provider.set(wanted)
            self._update_key_placeholder()

    def _update_key_placeholder(self):
        if self._selected_provider() == PROVIDER_OPENROUTER:
            self.entry_key.configure(placeholder_text=I18n.t("key_entry_ph_openrouter"))
        else:
            self.entry_key.configure(placeholder_text=I18n.t("key_entry_ph_google"))

    def _refresh_model_controls(self):
        self.opt_model.pack_forget()
        self.entry_model.pack_forget()
        self.btn_save_model.pack_forget()
        self.lbl_model_hint.pack_forget()

        if self.config_mgr.is_openrouter_active():
            current = self.config_mgr.config.get("openrouter_model", "")
            if self.entry_model.get() != current:
                self.entry_model.delete(0, "end")
                if current:
                    self.entry_model.insert(0, current)
            self.entry_model.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.btn_save_model.pack(side="left")
            self.lbl_model_hint.pack(
                fill="x", padx=16, pady=(0, 4), after=self.row_model
            )
        else:
            current_model = self.config_mgr.config.get("model", GEMINI_MODELS[0])
            values = list(GEMINI_MODELS)
            if current_model not in values:
                current_model = GEMINI_MODELS[0]
            self.opt_model.configure(values=values)
            self.opt_model.set(current_model)
            self.opt_model.pack(side="left")

    def _save_openrouter_model(self):
        model_name = self.entry_model.get().strip()
        if not model_name:
            self.lbl_add_status.configure(
                text=I18n.t("enter_model_err"), text_color=Theme.DANGER_COLOR
            )
            return
        self.config_mgr.config["openrouter_model"] = model_name
        self.config_mgr.save_config()
        self.lbl_add_status.configure(
            text=f"{model_name}",
            text_color=Theme.SUCCESS_COLOR,
        )

    def _on_model_selected(self, model_name: str):
        self.config_mgr.config["model"] = model_name
        self.config_mgr.save_config()

    def _on_language_selected(self, lang_display: str):
        selected_code = (
            "th" if "ไทย" in lang_display or "Thai" in lang_display else "en"
        )
        I18n.set_lang(selected_code)
        self.reload_text()
        if self.on_lang_changed:
            self.on_lang_changed()

    def _on_auto_approve_toggled(self):
        self.config_mgr.config["auto_approve_safe_tools"] = bool(
            self.switch_auto_approve.get()
        )
        self.config_mgr.save_config()

    def _workspace_display_text(self) -> str:
        configured = (self.config_mgr.config.get("workspace_folder") or "").strip()
        if configured:
            return configured
        return I18n.t(
            "workspace_default", path=str(self.config_mgr.get_workspace_folder())
        )

    def _refresh_workspace_label(self):
        self.lbl_ws_path.configure(text=self._workspace_display_text())

    def _browse_workspace(self):
        initial = str(self.config_mgr.get_workspace_folder())
        path = filedialog.askdirectory(
            title=I18n.t("workspace_browse_title"), initialdir=initial
        )
        if path:
            self.config_mgr.set_workspace_folder(path)
            self._refresh_workspace_label()

    def _clear_workspace(self):
        self.config_mgr.set_workspace_folder("")
        self._refresh_workspace_label()
