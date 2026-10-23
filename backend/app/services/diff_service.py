import difflib
import hashlib
from typing import Any, Dict, List


def calculate_sha256(text: str) -> str:
    """Computes standard SHA-256 hex digest for a configuration text."""
    normalized = (text or "").replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_config_diff(
    old_config: str,
    new_config: str,
    fromfile: str = "Previous Version",
    tofile: str = "Current Version",
) -> Dict[str, Any]:
    """Generates a structured Unix Unified Diff between two network configuration snapshots.
    Provides line-by-line categorization and statistics for frontend diff viewers.
    """
    old_lines = (old_config or "").replace("\r\n", "\n").splitlines(keepends=True)
    new_lines = (new_config or "").replace("\r\n", "\n").splitlines(keepends=True)

    diff_generator = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=fromfile,
        tofile=tofile,
        lineterm="",
    )

    raw_diff_lines = list(diff_generator)
    has_changes = len(raw_diff_lines) > 0

    lines_added = 0
    lines_removed = 0
    structured_lines: List[Dict[str, str]] = []

    for line in raw_diff_lines:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            line_type = "header"
        elif line.startswith("+"):
            line_type = "added"
            lines_added += 1
        elif line.startswith("-"):
            line_type = "removed"
            lines_removed += 1
        else:
            line_type = "unchanged"

        structured_lines.append({"type": line_type, "content": line})

    return {
        "has_changes": has_changes,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "diff_text": "\n".join(raw_diff_lines),
        "diff_lines": structured_lines,
    }
