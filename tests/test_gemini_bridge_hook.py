import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(".gemini/hooks/bridge_hook.py")


def _run_hook(payload: dict, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GEMINI_PROJECT_DIR"] = str(tmp_path)
    env["GEMINI_SESSION_ID"] = "test-session"
    return subprocess.run(
        [sys.executable, str(HOOK.resolve())],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_session_start_emits_json_and_context(tmp_path: Path) -> None:
    result = _run_hook(
        {
            "session_id": "s1",
            "hook_event_name": "SessionStart",
            "timestamp": "2026-09-17T07:00:00+02:00",
            "cwd": str(tmp_path),
            "source": "startup",
        },
        tmp_path,
    )
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert "additionalContext" in parsed["hookSpecificOutput"]
    assert result.stdout.strip().startswith("{")
    assert (tmp_path / "handover" / "runtime_receipts").exists()


def test_before_tool_blocks_secret_like_path(tmp_path: Path) -> None:
    result = _run_hook(
        {
            "session_id": "s2",
            "hook_event_name": "BeforeTool",
            "timestamp": "2026-09-17T07:01:00+02:00",
            "cwd": str(tmp_path),
            "tool_name": "read_file",
            "tool_input": {"path": ".env"},
        },
        tmp_path,
    )
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["decision"] == "deny"


def test_before_tool_blocks_direct_main_push(tmp_path: Path) -> None:
    result = _run_hook(
        {
            "session_id": "s3",
            "hook_event_name": "BeforeTool",
            "timestamp": "2026-09-17T07:02:00+02:00",
            "cwd": str(tmp_path),
            "tool_name": "run_shell_command",
            "tool_input": {"command": "git push origin main"},
        },
        tmp_path,
    )
    parsed = json.loads(result.stdout)
    assert parsed["decision"] == "deny"


def test_before_tool_allows_regular_repo_read(tmp_path: Path) -> None:
    result = _run_hook(
        {
            "session_id": "s4",
            "hook_event_name": "BeforeTool",
            "timestamp": "2026-09-17T07:03:00+02:00",
            "cwd": str(tmp_path),
            "tool_name": "read_file",
            "tool_input": {"path": "README.md"},
        },
        tmp_path,
    )
    parsed = json.loads(result.stdout)
    assert parsed["decision"] == "allow"


def test_receipt_does_not_persist_prompt_body(tmp_path: Path) -> None:
    secret_prompt = "this exact sentence must not be stored"
    result = _run_hook(
        {
            "session_id": "s5",
            "hook_event_name": "AfterAgent",
            "timestamp": "2026-09-17T07:04:00+02:00",
            "cwd": str(tmp_path),
            "prompt": secret_prompt,
            "prompt_response": "response body",
        },
        tmp_path,
    )
    assert result.returncode == 0
    receipt_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "handover" / "runtime_receipts").glob("*.json")
    )
    assert secret_prompt not in receipt_text
    assert "response body" not in receipt_text
    assert "payload_sha256" in receipt_text
