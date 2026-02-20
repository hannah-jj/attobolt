# attobolt

A Slack bot that gives you a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) session from anywhere — your phone, a meeting, on the go. Type `/attobolt` in any Slack channel and get a full AI coding assistant working in the directory where the server is running.

## How it works

1. You message the bot directly (DM) or @mention it in a channel
2. The bot spawns a Claude Code CLI session in the server's working directory
3. Claude's response is posted as a thread reply to your message
4. Reply in the thread to keep the conversation going — session context is preserved across server restarts

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — fast Python package manager
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated (`claude` must be on your PATH)
- A Slack workspace where you can create apps

> **Security notice:** Claude is invoked with `--dangerously-skip-permissions`, which grants it full file system and shell access in the working directory. This is intentional for an agentic coding assistant but means Claude can read, write, and execute anything it can reach. Run the server in a directory and as a user with only the access you're comfortable granting. Adjust the flag in `attobolt/claude_cli.py` if you want to restrict permissions.

---

## 1. Create the Slack app

Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.

### Enable Socket Mode

1. In the left sidebar go to **Socket Mode**
2. Toggle **Enable Socket Mode** on
3. You'll be prompted to create an **App-Level Token** — give it the `connections:write` scope
4. Copy the token (starts with `xapp-`) — this is your `SLACK_APP_TOKEN`

### Set bot token scopes

Go to **OAuth & Permissions** → **Bot Token Scopes** and add:

| Scope | Why |
|---|---|
| `chat:write` | Post messages and replies |
| `app_mentions:read` | Receive @mention events |
| `im:history` | Receive direct messages |

### Enable event subscriptions

Go to **Event Subscriptions** → toggle **Enable Events** on.

Under **Subscribe to bot events** add:

- `app_mention`
- `message.im`

### Install the app

Go to **OAuth & Permissions** → **Install to Workspace**. After installing, copy the **Bot User OAuth Token** (starts with `xoxb-`) — this is your `SLACK_BOT_TOKEN`.

---

## 2. Install and configure

```bash
git clone https://github.com/your-username/attobolt.git
cd attobolt

# Install dependencies
uv sync

# Copy and fill in your tokens
cp .env.example .env
```

Edit `.env`:

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

---

## 3. Run

```bash
# Start the bot from the directory you want Claude to work in
cd /path/to/your/project

uv run python -m attobolt
```

The bot connects to Slack via Socket Mode — no public URL or ngrok needed.

For auto-reload during development:

```bash
uv run python -m attobolt --dev
```

---

## Usage

| Action | What to do |
|---|---|
| Start a session | DM the bot, or @mention it in a channel |
| Continue a session | Reply in the thread the bot created |
| @mention in a session thread | Works the same as replying |

Session state (thread → Claude session ID) is saved to `sessions.json` in the working directory and survives server restarts.

> **Note:** The file-based session store is designed for personal, single-user local use. If you're deploying attobolt for a team or organization, consider replacing it with a proper database (e.g. PostgreSQL, SQLite with WAL mode, or Redis) to handle concurrent sessions safely and avoid data loss under load.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | — | **Required.** `xoxb-` bot token |
| `SLACK_APP_TOKEN` | — | **Required.** `xapp-` Socket Mode token |
| `SESSIONS_FILE` | `sessions.json` | Path to session persistence file |

---

## License

MIT
