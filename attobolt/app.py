"""Slack Bolt async application with Claude CLI integration."""

from __future__ import annotations

import asyncio
import logging
import os
import re

from slack_bolt.app.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from attobolt.claude_cli import ask_claude, ClaudeCLIError
from attobolt.session_store import SessionStore

logger = logging.getLogger(__name__)

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])
sessions = SessionStore()


def _strip_mention(text: str) -> str:
    """Remove the leading bot <@U...> mention from message text."""
    return re.sub(r"^\s*<@[A-Z0-9]+>\s*", "", text).strip()


async def _start_session(prompt: str, thread_ts: str, say) -> None:
    """Start a new Claude session and post the response as a thread reply."""
    cwd = os.getcwd()
    prompt = prompt or "Hello"

    try:
        response = await ask_claude(prompt=prompt, cwd=cwd)
    except ClaudeCLIError as exc:
        logger.error("Claude CLI error: %s", exc)
        await say(text=f"Failed to start Claude session:\n```{exc}```", thread_ts=thread_ts)
        return

    if response.is_error:
        await say(text=f"Claude returned an error:\n```{response.text}```", thread_ts=thread_ts)
        return

    sessions.set(thread_ts, response.session_id, cwd=cwd)
    logger.info("New session: thread=%s -> session=%s", thread_ts, response.session_id)
    await say(text=response.text, thread_ts=thread_ts)


async def _reply_in_session(text: str, thread_ts: str, say) -> None:
    """Route a message to an existing Claude session thread."""
    if not text:
        return

    info = sessions.get(thread_ts)
    if info is None:
        return

    try:
        response = await ask_claude(prompt=text, session_id=info.session_id, cwd=info.cwd)
    except ClaudeCLIError as exc:
        logger.error("Claude CLI error: %s", exc)
        await say(text=f"Sorry, I encountered an error:\n```{exc}```", thread_ts=thread_ts)
        return

    if response.is_error:
        await say(text=f"Claude returned an error:\n```{response.text}```", thread_ts=thread_ts)
        return

    await say(text=response.text, thread_ts=thread_ts)


@app.event("app_mention")
async def handle_mention(event: dict, say) -> None:
    """Handle @mentions of the bot in channels."""
    # If inside an existing session thread, continue the conversation
    if event.get("thread_ts") and sessions.get(event["thread_ts"]):
        text = _strip_mention(event.get("text", ""))
        await _reply_in_session(text, event["thread_ts"], say)
        return

    # New mention — start a session; the mention message itself anchors the thread
    text = _strip_mention(event.get("text", ""))
    await _start_session(text, event["ts"], say)


@app.event("assistant_thread_started")
async def handle_assistant_thread_started() -> None:
    """Acknowledge assistant thread start; the first user message will open the session."""


@app.event("assistant_thread_context_changed")
async def handle_assistant_thread_context_changed() -> None:
    """Acknowledge assistant thread context changes."""


@app.event("message")
async def handle_dm(event: dict, say) -> None:
    """Handle direct messages to the bot."""
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id") or event.get("subtype"):
        return

    thread_ts = event.get("thread_ts")

    # If inside an existing session thread, continue the conversation
    if thread_ts and sessions.get(thread_ts):
        await _reply_in_session(event.get("text", ""), thread_ts, say)
        return

    # Use the existing thread_ts if present (assistant mode thread), otherwise
    # anchor to this message's ts (regular DM — creates a new thread for the session)
    anchor_ts = thread_ts or event["ts"]
    await _start_session(event.get("text", ""), anchor_ts, say)


async def main() -> None:
    """Start the Slack Socket Mode handler."""
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()


def run_sync() -> None:
    """Synchronous wrapper for main(), used as a picklable target by watchfiles."""
    asyncio.run(main())
