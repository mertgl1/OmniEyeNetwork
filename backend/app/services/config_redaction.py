import re
from typing import List, Tuple

_REDACTED = "[REDACTED]"
_SECRET_DIRECTIVE = re.compile(
    r"^(?P<prefix>.*?\b(?:password|passwd|secret|community|shared-secret|"
    r"pre-shared-key|psksecret|key-string|authentication-key|private-key|"
    r"token|key)\b\s+)(?P<value>\S.*)$",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?P<prefix>\b(?:password|passwd|secret|community|shared-secret|"
    r"pre-shared-key|psksecret|key-string|authentication-key|private-key|"
    r"token)\s*=\s*)(?P<value>\"[^\"]*\"|'[^']*'|[^\s]+)",
    re.IGNORECASE,
)


def redact_configuration(config_text: str) -> Tuple[str, int]:
    """Mask secret-bearing values in configuration lines before persistence."""
    redacted_lines: List[str] = []
    findings = 0
    for line in config_text.splitlines(keepends=True):
        newline = ""
        content = line
        if content.endswith("\r\n"):
            content, newline = content[:-2], "\r\n"
        elif content.endswith(("\r", "\n")):
            content, newline = content[:-1], content[-1]

        assignment = _SECRET_ASSIGNMENT.search(content)
        if assignment and _REDACTED not in assignment.group("value"):
            content = _SECRET_ASSIGNMENT.sub(
                lambda match: f"{match.group('prefix')}{_REDACTED}",
                content,
            )
            findings += 1
        else:
            directive = _SECRET_DIRECTIVE.match(content)
            if directive and _REDACTED not in directive.group("value"):
                content = f"{directive.group('prefix')}{_REDACTED}"
                findings += 1
        redacted_lines.append(content + newline)
    return "".join(redacted_lines), findings


def count_unredacted_secret_lines(config_text: str) -> int:
    """Count likely secret-bearing lines without returning their contents."""
    return redact_configuration(config_text)[1]
