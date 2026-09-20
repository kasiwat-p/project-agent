from enum import Enum
from pathlib import Path
import re
import shlex

BASE_DIR = Path(__file__).resolve().parent.parent


class RiskLevel(Enum):
    SAFE = "SAFE"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    HIGH_RISK = "HIGH_RISK"


class SecurityGuard:
    SENSITIVE_FILES = {".env", "config.json", "id_rsa", "id_ecdsa", "id_ed25519", "credentials.json"}

    STRICT_BANNED_BINARIES = {
        "format",
        "diskpart",
        "dd",
        "rmdir",
        "rd",
    }

    HIGH_RISK_PATTERNS = [
        "rm -rf",
        "rm -r",
        "del /f /s /q",
        "rmdir /s",
        "rd /s",
        "remove-item -recurse",
        "drop database",
        ":(){ :|:& };:",
    ]

    _REDIRECT_ABS_PATH = re.compile(
        r'(?:>>?|out-file|set-content|add-content)\s*(?:-\w+\s+)*["\']?([A-Za-z]:[\\/][^\s"\']+)',
        re.IGNORECASE,
    )

    @classmethod
    def is_path_safe(cls, file_path: str, must_exist: bool = False) -> tuple[bool, str, Path]:
        """Check that the path is within the workspace and does not access sensitive files."""
        try:
            p = Path(file_path).resolve()
            
            # Check for sensitive file names
            if p.name.lower() in cls.SENSITIVE_FILES:
                return False, f"Access denied: reading or modifying sensitive file is not allowed ({p.name})", p

            # Check if file must exist
            if must_exist and not p.exists():
                return False, f"File not found: {file_path}", p

            return True, "Path is safe", p
        except Exception as e:
            return False, f"Invalid path: {str(e)}", Path(".")

    @classmethod
    def is_within_workspace(cls, file_path: str, workspace_dir: "Path") -> tuple[bool, str, "Path"]:
        """Check that the resolved path is strictly inside workspace_dir (prevents path traversal)."""
        try:
            workspace = Path(workspace_dir).resolve()
            raw = Path(file_path)
            # Relative paths are resolved against the workspace, not the process CWD.
            p = (workspace / raw).resolve() if not raw.is_absolute() else raw.resolve()

            # Check sensitive file names first
            if p.name.lower() in cls.SENSITIVE_FILES:
                return False, f"Access denied: sensitive file ({p.name}) cannot be modified", p

            # Ensure path is inside workspace (blocks ../../ and other drives)
            try:
                p.relative_to(workspace)
            except ValueError:
                return False, (
                    f"Access denied: '{p}' is outside the workspace folder '{workspace}'. "
                    "Please select a workspace folder in Settings."
                ), p

            return True, "Path is within workspace", p
        except Exception as e:
            return False, f"Invalid path: {str(e)}", Path(".")

    @classmethod
    def audit_terminal_command(cls, command: str) -> tuple[RiskLevel, str]:
        """Assess the risk level of a terminal command."""
        cmd_clean = command.strip()
        if not cmd_clean:
            return RiskLevel.SAFE, "Empty command"

        cmd_lower = cmd_clean.lower()

        # 1. Check banned patterns
        for pattern in cls.HIGH_RISK_PATTERNS:
            if pattern in cmd_lower:
                return RiskLevel.HIGH_RISK, f"Highly dangerous command detected: `{pattern}`"

        try:
            tokens = shlex.split(cmd_clean, posix=False)
            if not tokens:
                return RiskLevel.SAFE, "Empty command"
            base_bin = Path(tokens[0]).name.lower()
        except Exception:
            base_bin = cmd_lower.split()[0] if cmd_lower.split() else ""

        if base_bin in cls.STRICT_BANNED_BINARIES:
            return RiskLevel.HIGH_RISK, f"Command `{base_bin}` is blocked by the security system"

        # Allowed commands that always require user approval
        return RiskLevel.REQUIRES_APPROVAL, f"System command `{base_bin}` requires user confirmation before running"

    @classmethod
    def command_writes_outside_workspace(cls, command: str, workspace_dir: "Path") -> tuple[bool, str]:
        """True when a redirect/output target is an absolute path outside the workspace."""
        workspace = Path(workspace_dir).resolve()
        for raw in cls._REDIRECT_ABS_PATH.findall(command or ""):
            safe, msg, _ = cls.is_within_workspace(raw, workspace)
            if not safe:
                return True, msg
        return False, ""
