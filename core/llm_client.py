import json
import re
import urllib.error
import urllib.request

PROVIDER_GOOGLE = "google"
PROVIDER_OPENROUTER = "openrouter"

OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
DEFAULT_OPENROUTER_MODEL = "openrouter/auto"


def detect_provider(key: str) -> str:
    raw = (key or "").strip()
    if raw.startswith("sk-or-"):
        return PROVIDER_OPENROUTER
    return PROVIDER_GOOGLE


def create_llm_client(api_key: str, provider: str):
    if provider == PROVIDER_OPENROUTER:
        return OpenRouterClient(api_key)
    from google import genai

    return genai.Client(api_key=api_key)


class _TextResponse:
    def __init__(self, text: str):
        self.text = text or ""


class OpenRouterClient:
    """OpenAI-compatible client with the same generate_content surface as google-genai."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.models = self

    def generate_content(self, model, contents, config=None):
        system = ""
        temperature = 0.2
        schema = None
        mime = None
        if config is not None:
            system = getattr(config, "system_instruction", None) or ""
            temperature = getattr(config, "temperature", 0.2) or 0.2
            schema = getattr(config, "response_schema", None)
            mime = getattr(config, "response_mime_type", None)

        user = contents if isinstance(contents, str) else str(contents)
        want_json = bool(schema) or mime == "application/json"
        if schema is not None:
            json_schema = (
                schema.model_json_schema()
                if hasattr(schema, "model_json_schema")
                else schema
            )
            schema_text = json.dumps(json_schema, ensure_ascii=False)
            extra = (
                "You must reply with a single valid JSON object only. "
                "No markdown, no code fences, no extra commentary.\n"
                f"JSON schema:\n{schema_text}"
            )
            system = f"{system}\n\n{extra}" if system else extra

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if want_json:
            body["response_format"] = {"type": "json_object"}

        try:
            data = self._post_chat(body)
        except OpenRouterAPIError as e:
            if want_json and "response_format" in str(e).lower():
                body.pop("response_format", None)
                data = self._post_chat(body)
            else:
                raise

        text = self._message_text(data)
        if want_json:
            text = _extract_json_text(text)
        return _TextResponse(text)

    def _post_chat(self, body: dict) -> dict:
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            OPENROUTER_CHAT_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # แก้
                "HTTP-Referer": "https://github.com/antigravity-agent",
                "X-Title": "Project Agent",
            },
        )
        return _openrouter_request(req)

    @staticmethod
    def _message_text(data: dict) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise OpenRouterAPIError("OpenRouter returned no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text") or "")
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return content or ""


class OpenRouterAPIError(Exception):
    pass


def validate_openrouter_key(api_key: str) -> tuple[bool, str]:
    req = urllib.request.Request(
        OPENROUTER_KEY_URL,
        method="GET",
        headers={"Authorization": f"Bearer {api_key.strip()}"},
    )
    try:
        data = _openrouter_request(req)
        info = data.get("data") or data
        label = info.get("label") or "OpenRouter"
        return True, f"Connection successful: {label}"
    except OpenRouterAPIError as e:
        return False, f"API Error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def _openrouter_request(req: urllib.request.Request) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        try:
            parsed = json.loads(detail)
            err = parsed.get("error")
            if isinstance(err, dict):
                detail = err.get("message") or detail
            elif isinstance(err, str):
                detail = err
        except Exception:
            pass
        raise OpenRouterAPIError(f"{e.code} {detail}") from e
    except urllib.error.URLError as e:
        raise OpenRouterAPIError(str(e.reason if hasattr(e, "reason") else e)) from e


def _extract_json_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text
