import json
import os
import threading
from pathlib import Path
from datetime import datetime
import sys

from google import genai
from google.genai import types
from google.genai.errors import APIError

from core.llm_client import (
    DEFAULT_OPENROUTER_MODEL,
    PROVIDER_GOOGLE,
    PROVIDER_OPENROUTER,
    create_llm_client,
    detect_provider,
    validate_openrouter_key,
)

if getattr(sys, "frozen", False):
    # .exe
    BASE_DIR = Path(sys.executable).parent
else:
    # Root Directory
    BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = BASE_DIR / "config.json"
ENV_FILE = BASE_DIR / ".env"
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class ConfigManager:
    """Singleton config manager with thread-safe access and API key rotation."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConfigManager, cls).__new__(cls)
                cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        self.config_lock = threading.Lock()
        self.config = {
            "model": DEFAULT_MODEL,
            "openrouter_model": DEFAULT_OPENROUTER_MODEL,
            "api_keys": [],
            "active_key_index": 0,
            "auto_approve_safe_tools": False,
            "max_retries_on_rate_limit": 6,
            "language": "th",
            "workspace_folder": "",
            "max_agent_turns": 20,
            "system_instruction": (
                "You are an expert AI Agent programming assistant with strong "
                "capabilities in planning, reasoning, coding, debugging, and "
                "tool execution.\n\n"
                "Your responsibilities are to:\n"
                "- Understand the user's goal, requirements, and constraints.\n"
                "- Break complex tasks into clear and manageable steps.\n"
                "- Create an effective execution plan before taking action.\n"
                "- Write clean, maintainable, efficient, and reliable code.\n"
                "- Use available tools when they are necessary to complete the task.\n"
                "- Execute actions carefully and verify their results.\n"
                "- Detect errors, diagnose their causes, and fix them when possible.\n"
                "- Test and validate implementations before considering a task complete.\n"
                "- Clearly communicate important decisions and final results.\n"
                "- Ask for clarification only when the task cannot be completed "
                "reliably without additional information.\n\n"
                "When working on a task, follow this workflow:\n"
                "1. Analyze the objective, requirements, and constraints.\n"
                "2. Create a clear execution plan.\n"
                "3. Execute the plan using the appropriate tools.\n"
                "4. Inspect and verify the results.\n"
                "5. Diagnose and fix problems if necessary.\n"
                "6. Test the final implementation when possible.\n"
                "7. Provide a concise summary of what was completed.\n\n"
                "Tool Usage Rules:\n"
                "- Choose the most appropriate tool for each task.\n"
                "- Do not use tools unnecessarily.\n"
                "- Verify important parameters before executing actions.\n"
                "- After using a tool, inspect its output before continuing.\n"
                "- If a tool fails, analyze the error and attempt a reasonable recovery.\n"
                "- Never assume that a tool succeeded without checking its result.\n\n"
                "Coding Rules:\n"
                "- Prefer simple, modular, maintainable, and efficient solutions.\n"
                "- Follow the conventions of the existing codebase.\n"
                "- Do not modify unrelated files or functionality.\n"
                "- Preserve existing functionality unless the user requests otherwise.\n"
                "- Test changes whenever possible.\n"
                "- Never claim that code works without verification.\n\n"
                "Prioritize correctness, reliability, security, and practical "
                "solutions over unnecessary complexity."
            ),
        }
        self.load_config()

    def load_config(self):
        with self.config_lock:
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.config.update(data)
                    for item in self.config.get("api_keys", []):
                        if not item.get("provider"):
                            item["provider"] = detect_provider(item.get("key", ""))
                    if "openrouter_model" not in self.config:
                        self.config["openrouter_model"] = DEFAULT_OPENROUTER_MODEL
                except Exception as e:
                    print(f"[ConfigManager] Error reading config.json: {e}")

            # Auto-import key from .env if no keys exist
            if not self.config.get("api_keys") and ENV_FILE.exists():
                try:
                    with open(ENV_FILE, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("API_KEY="):
                                key = line.split("=", 1)[1].strip()
                                if key:
                                    self.config["api_keys"].append(
                                        {
                                            "key": key,
                                            "label": "Imported from .env",
                                            "provider": detect_provider(key),
                                            "status": "active",
                                            "error_count": 0,
                                            "last_used": datetime.now().strftime(
                                                "%Y-%m-%d %H:%M:%S"
                                            ),
                                        }
                                    )
                                    self.config["active_key_index"] = 0
                                    self._save_config_unlocked()
                                    break
                except Exception as e:
                    print(f"[ConfigManager] Error reading .env: {e}")

    def save_config(self):
        with self.config_lock:
            self._save_config_unlocked()

    def _save_config_unlocked(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ConfigManager] Error saving config.json: {e}")

    def get_all_keys(self) -> list:
        with self.config_lock:
            return list(self.config.get("api_keys", []))

    def get_active_key_info(self) -> tuple[str, int]:
        with self.config_lock:
            keys = self.config.get("api_keys", [])
            idx = self.config.get("active_key_index", 0)
            if keys and 0 <= idx < len(keys):
                return keys[idx].get("key", ""), idx
            return "", -1

    def get_active_key(self) -> str:
        key, _ = self.get_active_key_info()
        return key

    def get_active_provider(self) -> str:
        with self.config_lock:
            keys = self.config.get("api_keys", [])
            idx = self.config.get("active_key_index", 0)
            if keys and 0 <= idx < len(keys):
                item = keys[idx]
                return item.get("provider") or detect_provider(item.get("key", ""))
            return PROVIDER_GOOGLE

    def is_openrouter_active(self) -> bool:
        return self.get_active_provider() == PROVIDER_OPENROUTER

    def get_model_for_provider(self, provider: str | None = None) -> str:
        provider = provider or self.get_active_provider()
        with self.config_lock:
            if provider == PROVIDER_OPENROUTER:
                return (self.config.get("openrouter_model") or "").strip()
            return self.config.get("model", DEFAULT_MODEL)

    def get_workspace_folder(self) -> Path:
        """Return the user-selected workspace folder, or BASE_DIR as fallback."""
        with self.config_lock:
            folder = self.config.get("workspace_folder", "")
        if folder and Path(folder).is_dir():
            return Path(folder).resolve()
        return BASE_DIR

    def set_workspace_folder(self, path: str) -> None:
        """Persist the workspace folder path to config. Empty string resets to default."""
        with self.config_lock:
            self.config["workspace_folder"] = (path or "").strip()
            self._save_config_unlocked()

    def add_key(
        self, key: str, label: str = "", provider: str = ""
    ) -> tuple[bool, str]:
        key = key.strip()
        if not key:
            return False, "Please enter an API Key"

        provider = (provider or detect_provider(key)).strip() or PROVIDER_GOOGLE
        if provider not in (PROVIDER_GOOGLE, PROVIDER_OPENROUTER):
            provider = detect_provider(key)

        with self.config_lock:
            keys = self.config.setdefault("api_keys", [])
            for item in keys:
                if item.get("key") == key:
                    return False, "This API Key already exists in the system"

            if not label:
                prefix = "OpenRouter" if provider == PROVIDER_OPENROUTER else "Gemini"
                label = f"{prefix} Key #{len(keys) + 1}"

            new_item = {
                "key": key,
                "label": label,
                "provider": provider,
                "status": "active",
                "error_count": 0,
                "last_used": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            keys.append(new_item)
            if len(keys) == 1:
                self.config["active_key_index"] = 0

            self._save_config_unlocked()
            return True, "API Key added successfully"

    def remove_key(self, index: int) -> bool:
        with self.config_lock:
            keys = self.config.get("api_keys", [])
            if 0 <= index < len(keys):
                keys.pop(index)
                active = self.config.get("active_key_index", 0)
                self.config["active_key_index"] = max(0, min(active, len(keys) - 1))
                self._save_config_unlocked()
                return True
            return False

    def set_active_key(self, index: int) -> bool:
        with self.config_lock:
            keys = self.config.get("api_keys", [])
            if 0 <= index < len(keys):
                self.config["active_key_index"] = index
                keys[index]["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._save_config_unlocked()
                return True
            return False

    def rotate_to_next_key(self, reason: str = "") -> tuple[str, bool]:
        with self.config_lock:
            keys = self.config.get("api_keys", [])
            if not keys:
                return "", False

            current_idx = self.config.get("active_key_index", 0)
            current = keys[current_idx] if 0 <= current_idx < len(keys) else {}
            current_provider = current.get("provider") or detect_provider(
                current.get("key", "")
            )

            next_idx = None
            for offset in range(1, len(keys)):
                candidate_idx = (current_idx + offset) % len(keys)
                item = keys[candidate_idx]
                provider = item.get("provider") or detect_provider(item.get("key", ""))
                if provider == current_provider:
                    next_idx = candidate_idx
                    break

            if next_idx is None or next_idx == current_idx:
                return "", False

            self.config["active_key_index"] = next_idx
            new_key = keys[next_idx]
            new_key["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_config_unlocked()

            label = new_key.get("label", f"Key #{next_idx + 1}")
            k = new_key.get("key", "")
            masked = f"{k[:5]}...{k[-3:]}" if len(k) > 8 else k
            msg = f"[ConfigManager] Rotated to {label} ({masked}) — Reason: {reason}"
            print(msg)
            return msg, True

    def test_key(self, key: str, provider: str = "") -> tuple[bool, str]:
        key = key.strip()
        if not key:
            return False, "Please enter an API Key"
        provider = (provider or detect_provider(key)).strip() or PROVIDER_GOOGLE
        if provider == PROVIDER_OPENROUTER:
            return validate_openrouter_key(key)
        try:
            client = genai.Client(api_key=key)
            model = self.config.get("model", DEFAULT_MODEL)
            response = client.models.generate_content(
                model=model,
                contents="Say 'OK' in one word.",
                config=types.GenerateContentConfig(temperature=0.0),
            )
            return True, f"Connection successful: {response.text.strip()}"
        except APIError as e:
            msg = e.message if hasattr(e, "message") else str(e)
            return False, f"API Error: {msg}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def execute_with_auto_rotation(self, call_fn, on_rotate_callback=None):
        """Execute call_fn(client, model) with automatic key rotation on rate limit."""
        keys = self.get_all_keys()
        if not keys:
            raise RuntimeError("No API Keys available. Please add a key in Settings.")

        provider = self.get_active_provider()
        same_provider = [
            k
            for k in keys
            if (k.get("provider") or detect_provider(k.get("key", ""))) == provider
        ]
        max_attempts = min(len(same_provider), 3)

        for attempt in range(max_attempts):
            active_key = self.get_active_key()
            if not active_key:
                raise RuntimeError("No active API Key found.")

            provider = self.get_active_provider()
            model = self.get_model_for_provider(provider)
            if provider == PROVIDER_OPENROUTER and not model:
                raise RuntimeError("Please enter an OpenRouter model name in Settings ")

            client = create_llm_client(active_key, provider)

            try:
                return call_fn(client, model)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = any(
                    x in err_str
                    for x in ["429", "rate limit", "quota", "resource_exhausted"]
                )
                if is_rate_limit and attempt < max_attempts - 1:
                    new_key, msg = self.rotate_to_next_key(
                        reason=f"Rate limit: {str(e)[:80]}"
                    )
                    if on_rotate_callback and new_key:
                        on_rotate_callback(new_key)
                    continue
                raise
