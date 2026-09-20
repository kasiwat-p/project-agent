from core.config_manager import ConfigManager

TRANSLATIONS = {
    "th": {
        # Sidebar
        "chat_nav": "แชท & สั่งงาน",
        "plan_nav": "แผนงาน (Plan)",
        "settings_nav": "API Keys & ตั้งค่า",
        "active_key_prefix": "Active Key:",
        "no_active_key": "ไม่มี Key ที่พร้อมใช้",
        "brand_subtitle": "",
        # Chat View
        "idle_status": "พร้อมทำงาน",
        "input_placeholder": "ถามคำถาม หรือพิมพ์คำสั่งให้ Agent วางแผน...",
        "welcome_msg": "สวัสดีครับ! มีอะไรให้ผมช่วยวางแผนหรือเขียนโค้ดวันนี้ไหมครับ?",
        "listening_status": "กำลังฟังเสียงพูดของคุณ...",
        # Plan Card & Approval Card
        "plan_card_title": "Implementation Plan (แผนการดำเนินงาน)",
        "goal_prefix": "เป้าหมาย:",
        "summary_prefix": "สรุป:",
        "proceed_btn": "Proceed (เริ่มดำเนินการตาม Plan)",
        "refine_btn": "แก้ไข Plan",
        "refine_placeholder": "พิมพ์ข้อเสนอแนะเพื่อสั่ง AI แก้ไข Plan...",
        "approval_title": "ต้องการความยินยอมจากผู้ใช้: รัน `{tool_name}`",
        "params_label": "คำสั่ง / พารามิเตอร์:",
        "approve_btn": "Approve (อนุญาต)",
        "reject_btn": "Reject (ปฏิเสธ)",
        # Plan View
        "plan_inspector_title": "Implementation Plan & Execution Inspector",
        "no_plan_goal": "เป้าหมาย: ยังไม่มี Plan ในขณะนี้ (สามารถเริ่มสร้างได้จากหน้าแชท)",
        "no_plan_summary": "เมื่อผู้ใช้สั่งงานที่มีความซับซ้อน AI จะสร้าง Plan และขั้นตอนย่อยๆ มาแสดงที่นี่",
        # Settings View
        "settings_title": "API Key Pool & System Settings",
        "add_key_title": "เพิ่ม API Key ใหม่",
        "key_entry_ph": "กรอก API Key",
        "key_entry_ph_google": "กรอก Google Gemini API Key (AIzaSy...)",
        "key_entry_ph_openrouter": "กรอก OpenRouter API Key (sk-or-...)",
        "label_entry_ph": "ชื่อระบุคีย์ (เช่น คีย์หลัก, สำรอง 1)",
        "provider_label": "ผู้ให้บริการ:",
        "provider_google": "Google Gemini",
        "provider_openrouter": "OpenRouter",
        "save_key_btn": "บันทึกคีย์",
        "keys_pool_title": "รายการ API Keys ใน Pool (สลับอัตโนมัติเมื่อติด Rate Limit/429):",
        "no_keys_text": "ยังไม่มี API Key ในระบบ กรุณาเพิ่มคีย์ด้านบน",
        "preferences_title": "ตั้งค่าความปลอดภัยและโมเดล AI",
        "model_label": "โมเดลหลัก (Model):",
        "model_custom_ph": "เช่น openai/gpt-4o-mini หรือ anthropic/claude-sonnet-4",
        "model_custom_hint": "เฉพาะ OpenRouter: พิมพ์ชื่อโมเดลเองตามที่ OpenRouter รองรับ",
        "save_model_btn": "บันทึกโมเดล",
        "enter_model_err": "กรุณาใส่ชื่อโมเดลของ OpenRouter",
        "language_label": "ภาษาในโปรแกรม (Language):",
        "auto_approve_label": "อนุมัติการเขียนไฟล์และสร้างโฟลเดอร์อัตโนมัติ (ไม่รวมลบไฟล์/รันคำสั่ง)",
        "agent_busy": "Agent กำลังทำงานอยู่ กรุณารอสักครู่...",
        "plan_no_steps": "งานนี้ต้องมีแผนแต่ระบบสร้างขั้นตอนไม่ได้ กรุณาลองสั่งใหม่อีกครั้ง",
        "plan_already_ran": "แผนนี้ถูกรันไปแล้ว หากต้องการทำซ้ำ ให้สร้างแผนใหม่หรือแก้ไขแผนก่อน",
        "stale_plan": "การ์ดนี้ไม่ใช่แผนล่าสุด กรุณาใช้แผนปัจจุบัน",
        "proceed_done": "Executed",
        "workspace_label": "โฟลเดอร์ Workspace:",
        "workspace_browse": "Browse",
        "workspace_clear": "Clear",
        "workspace_default": "ค่าเริ่มต้น: {path}",
        "workspace_hint": "Agent สามารถสร้าง/แก้ไข/ลบไฟล์ได้เฉพาะในโฟลเดอร์นี้",
        "workspace_browse_title": "เลือกโฟลเดอร์ Workspace",
        "set_active_btn": "Set Active",
        "test_btn": "Test",
        "delete_btn": "Delete",
        "testing_key": "กำลังทดสอบการเชื่อมต่อ API Key...",
        "enter_key_err": "กรุณากรอก API Key",
    },
    "en": {
        # Sidebar
        "chat_nav": "Chat & Agent",
        "plan_nav": "Plan & Steps",
        "settings_nav": "API Keys & Settings",
        "active_key_prefix": "Active Key:",
        "no_active_key": "No Active Key Available",
        "brand_subtitle": "",
        # Chat View
        "idle_status": "Ready (Idle)",
        "input_placeholder": "Ask a question or type a command to create a plan...",
        "welcome_msg": "Hello! How can I help you plan or write code today?",
        "listening_status": "Listening to your voice...",
        # Plan Card & Approval Card
        "plan_card_title": "Implementation Plan",
        "goal_prefix": "Goal:",
        "summary_prefix": "Summary:",
        "proceed_btn": "Proceed (Execute Plan)",
        "refine_btn": "Modify Plan",
        "refine_placeholder": "Type feedback to modify plan...",
        "approval_title": "Approval Required: Run `{tool_name}`",
        "params_label": "Command / Parameters:",
        "approve_btn": "Approve",
        "reject_btn": "Reject",
        # Plan View
        "plan_inspector_title": "Implementation Plan & Execution Inspector",
        "no_plan_goal": "Goal: No active plan yet (Start by sending a request in Chat)",
        "no_plan_summary": "When you request a complex task, the AI will generate a plan and steps here.",
        # Settings View
        "settings_title": "API Key Pool & System Settings",
        "add_key_title": "Add New API Key",
        "key_entry_ph": "Enter API Key",
        "key_entry_ph_google": "Enter Google Gemini API Key (AIzaSy...)",
        "key_entry_ph_openrouter": "Enter OpenRouter API Key (sk-or-...)",
        "label_entry_ph": "Key Label (e.g., Primary, Backup 1)",
        "provider_label": "Provider:",
        "provider_google": "Google Gemini",
        "provider_openrouter": "OpenRouter",
        "save_key_btn": "Save Key",
        "keys_pool_title": "API Key Pool (Auto-rotates on Rate Limit / 429):",
        "no_keys_text": "No API Keys added yet. Please add a key above.",
        "preferences_title": "Security & Model Preferences",
        "model_label": "Primary Model:",
        "model_custom_ph": "e.g. openai/gpt-4o-mini or anthropic/claude-sonnet-4",
        "model_custom_hint": "OpenRouter only: type the model id yourself",
        "save_model_btn": "Save Model",
        "enter_model_err": "Please enter an OpenRouter model id",
        "language_label": "App Language:",
        "auto_approve_label": "Auto-approve writes & folders (not delete/terminal)",
        "agent_busy": "The agent is busy. Please wait...",
        "plan_no_steps": "This task needs a plan, but no steps were generated. Please try again.",
        "plan_already_ran": "This plan has already been executed. Create or modify a plan to run again.",
        "stale_plan": "This card is not the current plan. Use the latest plan.",
        "proceed_done": "Executed",
        "workspace_label": "Workspace Folder:",
        "workspace_browse": "Browse",
        "workspace_clear": "Clear",
        "workspace_default": "Default: {path}",
        "workspace_hint": "The agent can create, edit, and delete files only inside this folder",
        "workspace_browse_title": "Select Workspace Folder",
        "set_active_btn": "Set Active",
        "test_btn": "Test",
        "delete_btn": "Delete",
        "testing_key": "Testing API Key connection...",
        "enter_key_err": "Please enter an API Key",
    },
}


class I18n:
    @classmethod
    def get_lang(cls) -> str:
        mgr = ConfigManager()
        return mgr.config.get("language", "th")

    @classmethod
    def set_lang(cls, lang: str):
        if lang in TRANSLATIONS:
            mgr = ConfigManager()
            mgr.config["language"] = lang
            mgr.save_config()

    @classmethod
    def t(cls, key: str, **kwargs) -> str:
        lang = cls.get_lang()
        text = TRANSLATIONS.get(lang, TRANSLATIONS["th"]).get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text
