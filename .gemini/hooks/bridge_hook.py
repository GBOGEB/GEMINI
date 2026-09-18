"""Gemini CLI hook for governed Gemini -> Drive -> GitHub handovers.

Contract:
- stdin: exactly one JSON hook payload from Gemini CLI
- stdout: exactly one JSON object, no other text
- stderr: diagnostics only

The hook intentionally persists metadata and hashes, not prompt/tool payloads.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(os.environ.get("GEMINI_PROJECT_DIR", Path.cwd())).resolve()
RECEIPT_DIR = PROJECT_ROOT / "handover" / "runtime_receipts"
SECRET_PATTERNS = (
    re.compile(r"(^|/|\\)\.env($|/|\\)", re.IGNORECASE),
    re.compile(r"credentials.*\.json$", re.IGNORECASE),
    re.compile(r"service[-_ ]?account.*\.json$", re.IGNORECASE),
    re.compile(r"api[-_ ]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
)
DIRECT_MAIN_WRITE = re.compile(r"\bgit\s+push\b[^\n]*\b(main|master)\b", re.IGNORECASE)


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read()
    payload = json.loads(raw or "{}")
    return payload if isinstance(payload, dict) else {}


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_write_receipt(event: str, payload: dict[str, Any]) -> None:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    session_id = str(payload.get("session_id") or os.environ.get("GEMINI_SESSION_ID") or "unknown")
    timestamp = str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat())
    event_id = hashlib.sha256(f"{session_id}|{timestamp}|{event}|{_digest(payload)}".encode()).hexdigest()[:20]
    receipt = {
        "schema_version": 1,
        "event_id": event_id,
        "session_id": session_id,
        "event": event,
        "timestamp": timestamp,
        "cwd": str(payload.get("cwd") or os.environ.get("GEMINI_CWD") or ""),
        "payload_sha256": _digest(payload),
        "tool_name": payload.get("tool_name"),
        "has_tool_response": "tool_response" in payload,
        "has_prompt": "prompt" in payload,
        "has_prompt_response": "prompt_response" in payload,
        "persistence_policy": "metadata_and_hash_only",
    }
    target = RECEIPT_DIR / f"{timestamp.replace(':', '').replace('/', '-')}_{event_id}_{event}.json"
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _candidate_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        items: list[str] = []
        for key, nested in value.items():
            items.append(str(key))
            items.extend(_candidate_strings(nested))
        return items
    if isinstance(value, list):
        items = []
        for nested in value:
            items.extend(_candidate_strings(nested))
        return items
    return []


def _before_tool(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input", {})
    strings = _candidate_strings(tool_input)

    for text in strings:
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            return {
                "decision": "deny",
                "reason": "Governed bridge policy blocks access to credential-, token-, secret-, API-key-, or .env-like paths/arguments. Use approved credential injection instead.",
            }

    if tool_name == "run_shell_command":
        command = "\n".join(strings)
        if DIRECT_MAIN_WRITE.search(command):
            return {
                "decision": "deny",
                "reason": "Direct push to main/master is blocked by the bridge policy. Use a feature branch and pull request so the Git SHA remains review-bound.",
            }

    return {"decision": "allow"}


def _session_start(payload: dict[str, Any]) -> dict[str, Any]:
    context = (
        "GEMINI bridge mode is active. Treat Google Drive as persistent source/handover storage, "
        "GitHub as governed code/audit authority, and chat as orchestration only. "
        "Use evidence states VERIFIED/IMPLEMENTED/DECLARED/INFERRED/PARTIAL/DEFERRED. "
        "Do not promote source-agent claims to VERIFIED without independent evidence. "
        "Do not expose credentials. Prefer branch + PR over direct main mutation."
    )
    return {
        "systemMessage": "Governed cross-agent bridge hooks active.",
        "hookSpecificOutput": {"additionalContext": context},
    }


def main() -> None:
    try:
        payload = _read_payload()
        event = str(payload.get("hook_event_name") or "Unknown")
        _safe_write_receipt(event, payload)

        if event == "SessionStart":
            result = _session_start(payload)
        elif event == "BeforeTool":
            result = _before_tool(payload)
        elif event == "AfterTool":
            result = {
                "hookSpecificOutput": {
                    "additionalContext": "Bridge receipt recorded (metadata/hash only); tool payload not persisted by the hook."
                }
            }
        elif event == "AfterAgent":
            result = {
                "systemMessage": "Bridge turn checkpoint recorded.",
                "suppressOutput": True,
            }
        elif event in {"PreCompress", "SessionEnd"}:
            result = {"suppressOutput": True}
        else:
            result = {}

        sys.stdout.write(json.dumps(result, separators=(",", ":")))
    except Exception as exc:
        print(f"bridge_hook warning: {exc}", file=sys.stderr)
        sys.stdout.write(json.dumps({"systemMessage": "Bridge hook warning; interaction continues."}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
