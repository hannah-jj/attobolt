"""Wrapper around the `claude` CLI subprocess."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClaudeResponse:
    """Parsed response from the Claude CLI."""

    text: str
    session_id: str
    is_error: bool


class ClaudeCLIError(Exception):
    """Raised when the Claude CLI invocation fails."""


def _find_claude_binary() -> str:
    path = shutil.which("claude")
    if path is None:
        raise ClaudeCLIError(
            "claude CLI not found on PATH. "
            "Install it: https://docs.anthropic.com/en/docs/claude-code"
        )
    return path


def _build_env() -> dict[str, str]:
    """Build subprocess environment, removing CLAUDECODE to avoid nested-session refusal."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    return env


async def ask_claude(
    prompt: str,
    session_id: str | None = None,
    timeout_seconds: float = 600.0,
    cwd: str | None = None,
) -> ClaudeResponse:
    """Send a prompt to the Claude CLI and return the parsed response.

    If session_id is provided, resumes that session for conversation continuity.
    If cwd is provided, the CLI subprocess runs in that working directory.

    NOTE: Claude is invoked with --dangerously-skip-permissions, which grants it
    full file system and shell access. Adjust this in your fork if needed.
    """
    claude_bin = _find_claude_binary()

    cmd: list[str] = [claude_bin]
    if session_id:
        cmd.extend(["--resume", session_id])
    cmd.extend(["--dangerously-skip-permissions", "-p", prompt, "--output-format", "json"])

    logger.info("Running claude CLI (session=%s, cwd=%s)", session_id or "new", cwd or "default")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_build_env(),
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        proc.kill()
        raise ClaudeCLIError(f"Claude CLI timed out after {timeout_seconds}s")
    except FileNotFoundError:
        raise ClaudeCLIError("claude CLI binary not found")

    if proc.returncode != 0:
        err_text = stderr.decode(errors="replace").strip()
        raise ClaudeCLIError(
            f"Claude CLI exited with code {proc.returncode}: {err_text}"
        )

    raw_output = stdout.decode(errors="replace").strip()
    if not raw_output:
        raise ClaudeCLIError("Claude CLI returned empty output")

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ClaudeCLIError(
            f"Failed to parse Claude CLI JSON: {exc}\n"
            f"Raw output: {raw_output[:500]}"
        )

    return ClaudeResponse(
        text=data.get("result", ""),
        session_id=data.get("session_id", ""),
        is_error=data.get("is_error", False),
    )
