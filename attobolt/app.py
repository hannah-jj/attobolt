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

SLASH_CMD_HINT = "Use `/attobolt [optional prompt]` to start a new Claude session in this channel."


def _strip_mention(text: str) -> str:
    """Remove the leading bot <@U...> mention from message text."""
    return re.sub(r"^\s*<@[A-Z0-9]+>\s*", "", text).strip()


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
    thread_ts = event.get("thread_ts") or event["ts"]

    # If inside an existing session thread, continue the conversation
    if event.get("thread_ts") and sessions.get(event["thread_ts"]):
        text = _strip_mention(event.get("text", ""))
        await _reply_in_session(text, event["thread_ts"], say)
        return

    await say(text=SLASH_CMD_HINT, thread_ts=thread_ts)


@app.event("message")
async def handle_dm(event: dict, say) -> None:
    """Handle direct messages to the bot."""
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id") or event.get("subtype"):
        return

    thread_ts = event.get("thread_ts") or event["ts"]

    # If inside an existing session thread, continue the conversation
    if event.get("thread_ts") and sessions.get(event["thread_ts"]):
        await _reply_in_session(event.get("text", ""), event["thread_ts"], say)
        return

    await say(text=SLASH_CMD_HINT, thread_ts=thread_ts)


@app.command("/attobolt")
async def handle_attobolt(ack, body, say) -> None:
    """Handle /attobolt slash command.

    Starts a Claude Code session in the directory where the server is running.
    An optional prompt can be passed as the command text; if omitted, Claude
    is greeted with a default "Hello" to open the session.
    """
    await ack()
    user_id = body["user_id"]
    prompt = (body.get("text") or "").strip() or "Hello"
    cwd = os.getcwd()

    await say(text=f"<@{user_id}> Starting Claude session in `{cwd}`…")

    try:
        response = await ask_claude(prompt=prompt, cwd=cwd)
    except ClaudeCLIError as exc:
        logger.error("Claude CLI error for /attobolt: %s", exc)
        await say(text=f"<@{user_id}> Failed to start Claude session:\n```{exc}```")
        return

    if response.is_error:
        await say(text=f"<@{user_id}> Claude returned an error:\n```{response.text}```")
        return

    # Post a new top-level message that becomes the dedicated thread
    thread_msg = await say(
        text=f"<@{user_id}> Claude session started in `{cwd}`\nSession: `{response.session_id}`",
    )
    thread_ts = thread_msg["ts"]

    # Store the session so future replies in this thread reuse it
    sessions.set(thread_ts, response.session_id, cwd=cwd)
    logger.info("/attobolt session: thread=%s -> session=%s", thread_ts, response.session_id)

    # Post Claude's initial response as the first reply in the thread
    await say(text=response.text, thread_ts=thread_ts)


async def main() -> None:
    """Start the Slack Socket Mode handler."""
    handler = AsyncSocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    await handler.start_async()


def run_sync() -> None:
    """Synchronous wrapper for main(), used as a picklable target by watchfiles."""
    asyncio.run(main())
