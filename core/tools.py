from dataclasses import dataclass
from typing import Callable, Any
from pathlib import Path
import subprocess
import webbrowser
import pymupdf
import os
import json

from core.security import SecurityGuard, RiskLevel
from core.config_manager import ConfigManager

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class ToolDefinition:
    name: str
    description: str
    risk_level: RiskLevel
    func: Callable[..., Any]
    parameter_docs: dict


class ToolRegistry:
    def __init__(self):
        self.tools: dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(
        self,
        name: str,
        description: str,
        risk_level: RiskLevel,
        func: Callable,
        parameter_docs: dict = None,
    ):
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            risk_level=risk_level,
            func=func,
            parameter_docs=parameter_docs or {},
        )

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self.tools.get(name)

    def _register_default_tools(self):
        # 1. Read File
        self.register(
            name="read_file",
            description="Read the content of a text file (Text, Code, Markdown) from the specified path",
            risk_level=RiskLevel.SAFE,
            func=self._tool_read_file,
            parameter_docs={"file_path": "Path of the file to read"},
        )

        # 2. Write File (create or overwrite)
        self.register(
            name="write_file",
            description="Create or overwrite a file inside the workspace folder",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            func=self._tool_write_file,
            parameter_docs={
                "file_path": "Path of the file to create or overwrite (must be inside workspace)",
                "content": "File content to write",
            },
        )

        # 3. Delete File
        self.register(
            name="delete_file",
            description="Permanently delete a file inside the workspace folder",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            func=self._tool_delete_file,
            parameter_docs={
                "file_path": "Path of the file to delete (must be inside workspace)"
            },
        )

        # 4. Create Folder
        self.register(
            name="create_folder",
            description="Create a new folder (and any parent folders) inside the workspace",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            func=self._tool_create_folder,
            parameter_docs={
                "dir_path": "Path of the folder to create (must be inside workspace)"
            },
        )

        # 5. List Directory
        self.register(
            name="list_directory",
            description="List files and folders inside a directory",
            risk_level=RiskLevel.SAFE,
            func=self._tool_list_directory,
            parameter_docs={
                "dir_path": "Path of the folder (defaults to workspace root)"
            },
        )

        # 6. Run Terminal Command
        self.register(
            name="run_terminal_command",
            description="Run a Terminal command (PowerShell / Command Prompt) on the system",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            func=self._tool_run_terminal,
            parameter_docs={"command": "Terminal command to execute"},
        )

        # 7. Read PDF
        self.register(
            name="read_pdf",
            description="Read and extract text from a PDF document",
            risk_level=RiskLevel.SAFE,
            func=self._tool_read_pdf,
            parameter_docs={"file_path": "Path of the PDF file"},
        )

        # 8. Open Browser
        self.register(
            name="open_browser",
            description="Open a web page (URL) in the system's default browser",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            func=self._tool_open_browser,
            parameter_docs={"url": "URL to open, e.g. https://google.com"},
        )

        # 9. DuckDuckGo Search
        self.register(
            name="duckduckgo_search",
            description="Search the web using DuckDuckGo and return the results as a JSON array",
            risk_level=RiskLevel.SAFE,
            func=self._tool_duckduckgo_search,
            parameter_docs={
                "query": "The search keywords/query",
                "max_results": "Maximum number of results to fetch (default: 5)",
            },
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_workspace(self) -> Path:
        return ConfigManager().get_workspace_folder()

    def _check_workspace(
        self, file_path: str, must_exist: bool = False
    ) -> tuple[bool, str, Path]:
        """Validate that file_path is inside the workspace folder."""
        workspace = self._get_workspace()
        safe, msg, path_obj = SecurityGuard.is_within_workspace(file_path, workspace)
        if not safe:
            return False, msg, path_obj
        if must_exist and not path_obj.exists():
            return False, f"File not found: {file_path}", path_obj
        return True, msg, path_obj

    # ── Tool implementations ──────────────────────────────────────────────────

    def _tool_read_file(self, file_path: str) -> str:
        safe, msg, path_obj = self._check_workspace(file_path, must_exist=True)
        if not safe:
            return f"Security Error: {msg}"
        try:
            if path_obj.is_dir():
                return f"Error: '{path_obj}' is a directory, not a file."
            return path_obj.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _tool_write_file(self, file_path: str, content: str) -> str:
        safe, msg, path_obj = self._check_workspace(file_path, must_exist=False)
        if not safe:
            return f"Security Error: {msg}"
        try:
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            path_obj.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to '{path_obj.name}'"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def _tool_delete_file(self, file_path: str) -> str:
        safe, msg, path_obj = self._check_workspace(file_path, must_exist=True)
        if not safe:
            return f"Security Error: {msg}"
        try:
            if path_obj.is_dir():
                return f"Error: '{path_obj.name}' is a directory, not a file. Use a different approach to remove directories."
            path_obj.unlink()
            return f"Successfully deleted '{path_obj.name}'"
        except Exception as e:
            return f"Error deleting file: {str(e)}"

    def _tool_create_folder(self, dir_path: str) -> str:
        safe, msg, path_obj = self._check_workspace(dir_path, must_exist=False)
        if not safe:
            return f"Security Error: {msg}"
        try:
            path_obj.mkdir(parents=True, exist_ok=True)
            return f"Successfully created folder '{path_obj}'"
        except Exception as e:
            return f"Error creating folder: {str(e)}"

    def _tool_list_directory(self, dir_path: str = ".") -> str:
        safe, msg, path_obj = self._check_workspace(dir_path or ".", must_exist=True)
        if not safe:
            return f"Security Error: {msg}"
        if not path_obj.is_dir():
            return f"Error: '{dir_path}' is not a directory."
        try:
            entries = []
            for item in sorted(path_obj.iterdir()):
                if item.name.startswith(".") and item.name not in [".gitignore"]:
                    continue
                type_str = "[DIR]" if item.is_dir() else "[FILE]"
                entries.append(f"{type_str} {item.name}")

            return "\n".join(entries) if entries else "(Empty Directory)"
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    def _tool_run_terminal(self, command: str) -> str:
        risk, msg = SecurityGuard.audit_terminal_command(command)
        if risk == RiskLevel.HIGH_RISK:
            return f"Security Rejected: {msg}"

        escaped, escape_msg = SecurityGuard.command_writes_outside_workspace(
            command, self._get_workspace()
        )
        if escaped:
            return f"Security Rejected: {escape_msg}"

        try:
            res = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self._get_workspace()),
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()

            output = []
            if stdout:
                output.append(f"[Output]\n{stdout}")
            if stderr:
                output.append(f"[Stderr]\n{stderr}")
            if not stdout and not stderr:
                output.append("(Command completed with no output)")

            output.append(f"[Exit Code: {res.returncode}]")
            return "\n".join(output)
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds"
        except Exception as e:
            return f"Execution Error: {str(e)}"

    def _tool_read_pdf(self, file_path: str) -> str:
        safe, msg, path_obj = self._check_workspace(file_path, must_exist=True)
        if not safe:
            return f"Security Error: {msg}"
        if path_obj.suffix.lower() != ".pdf":
            return f"Error: File is not a PDF: {file_path}"
        try:
            doc = pymupdf.open(str(path_obj))
            text_blocks = []
            for idx in range(len(doc)):
                page = doc.load_page(idx)
                text = page.get_text()
                if text.strip():
                    text_blocks.append(f"--- Page {idx + 1} ---\n{text}")
            doc.close()
            return (
                "\n\n".join(text_blocks)
                if text_blocks
                else "(PDF contains no readable text)"
            )
        except Exception as e:
            return f"Error reading PDF: {str(e)}"

    def _tool_open_browser(self, url: str) -> str:
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"
        try:
            webbrowser.open(url)
            return f"Successfully opened {url} in browser"
        except Exception as e:
            return f"Error opening browser: {str(e)}"

    def _tool_duckduckgo_search(self, query: str, max_results: int = 5) -> str:
        """Search tool implementation returning JSON string."""
        try:
            from duckduckgo_search import DDGS

            # เรียกใช้งาน DDGS() ตรงๆ โดยไม่ต้องใช้ context manager (with)
            ddgs = DDGS()
            raw_results = ddgs.text(query, max_results=int(max_results))

            # แปลงผลลัพธ์เป็น list และจัดรูปแบบข้อมูล
            results = list(raw_results) if raw_results else []
            return json.dumps(results, ensure_ascii=False, indent=2)

        except ImportError:
            error_msg = {
                "error": "Missing dependency. Please install duckduckgo-search (pip install duckduckgo-search)"
            }
            return json.dumps(error_msg, ensure_ascii=False)
        except Exception as e:
            error_msg = {"error": f"Search error: {str(e)}"}
            return json.dumps(error_msg, ensure_ascii=False)

    def format_tool_catalog(self) -> str:
        """Build a prompt block describing every registered tool."""
        lines = []
        for name, tool in self.tools.items():
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameter_docs.items())
            lines.append(f"- {name} ({tool.risk_level.value}): {tool.description}")
            if params:
                lines.append(f"  Parameters: {params}")
        return "\n".join(lines)


def scout_workspace(user_prompt: str = "", max_tree_chars: int = 6000) -> str:
    """List workspace and optionally read small files mentioned in the prompt."""
    import re

    registry = tools_registry
    list_tool = registry.get_tool("list_directory")
    read_tool = registry.get_tool("read_file")
    tree = list_tool.func(".") if list_tool else "(no list_directory tool)"
    if len(tree) > max_tree_chars:
        tree = tree[:max_tree_chars] + "\n... (truncated)"

    parts = [f"Directory listing (workspace root):\n{tree}"]

    if user_prompt and read_tool:
        path_pattern = re.compile(
            r"(?:[\w.-]+/)*[\w.-]+\.(?:py|txt|md|json|js|ts|tsx|jsx|html|css|yaml|yml|toml|ini|cfg|env)",
            re.IGNORECASE,
        )
        seen = set()
        for m in path_pattern.finditer(user_prompt):
            p = m.group(0)
            if p in seen:
                continue
            seen.add(p)
            if len(seen) > 3:
                break
            content = read_tool.func(p)
            if content.startswith("Security Error") or content.startswith("Error"):
                continue
            if len(content) > 3000:
                content = content[:3000] + "\n... (truncated)"
            parts.append(f"--- File: {p} ---\n{content}")

    return "\n\n".join(parts)[:8000]


# Singleton Instance
tools_registry = ToolRegistry()
