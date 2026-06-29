---
name: group-chat-bot
version: 1.0.0
author: open-community
license: MIT
description: |
  Group chat bot collaboration skill for multi-agent clusters.
  Enables bots to interact in group chat platforms (Feishu/Lark, DingTalk,
  Slack, etc.) with human-visible, rich-media collaboration process.
  Includes the critical "reply tag trap" solution and bot-to-bot
  negotiation patterns.
---

# group-chat-bot

## Design Motivation

Agent cluster communication often happens in invisible channels — message buses, P2P links, GitHub Issues. But **humans need to see what's happening**. Group chat bots bridge this gap: every inter-agent interaction becomes a visible, searchable, rich-media message thread that humans can observe, intervene in, and audit.

**Unique value**: Unlike pure machine-to-machine channels, group chat makes the collaboration process **perceivable** and **intervenable** by humans.

## Core Capabilities

| Capability | Description |
|---|---|
| Human-Visible Collaboration | All bot interactions visible in group chat threads |
| Rich Media Messages | Cards, tables, images, at-mentions — not just plain text |
| Human-in-the-Loop | Humans can observe, comment, and redirect bot workflows in real time |
| Bot-to-Bot Negotiation | Bots can delegate tasks to each other via the group chat channel |
| Multi-Platform Support | Feishu/Lark, DingTalk, Slack, Teams (adaptable connector) |

## Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Human    │     │  Bot A    │     │  Bot B    │     │  Bot C    │
│  Observer │     │ (Analyst) │     │ (Executor)│     │ (Reviewer)│
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │    ┌───────────┴────────────────┴────────────────┘
     │    │
     ▼    ▼
┌──────────────────────────────────────────┐
│           Group Chat Platform             │
│  ┌─────────────────────────────────────┐ │
│  │  Thread: "Q2 Risk Analysis"         │ │
│  │  Bot A: Starting credit risk check  │ │
│  │  Bot B: Executing data query...     │ │
│  │  Bot C: Review passed ✅            │ │
│  │  Human: Looks good, finalize       │ │
│  └─────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

## Configuration

```yaml
# group-chat-bot config
platform:
  type: ${CHAT_PLATFORM:feishu}  # feishu | dingtalk | slack | teams
  app_id: ${CHAT_APP_ID:}
  app_secret: ${CHAT_APP_SECRET:}

group:
  chat_id: ${GROUP_CHAT_ID:}      # Target group chat ID
  bot_names:                       # Bot identity mapping
    coordinator: ${BOT_A_OPEN_ID:}
    executor: ${BOT_B_OPEN_ID:}
    reviewer: ${BOT_C_OPEN_ID:}

webhook:
  url: ${CHAT_WEBHOOK_URL:http://localhost:8001/api/chat/webhook}
  event_types:
    - message.receive              # Message received event
```

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `CHAT_PLATFORM` | Chat platform type | `feishu`, `slack`, `dingtalk` |
| `CHAT_APP_ID` | Platform application ID | `cli_xxxxxxxxxxxx` |
| `CHAT_APP_SECRET` | Platform application secret | `your-app-secret` |
| `GROUP_CHAT_ID` | Default group chat ID | `oc_xxxxxxxxxxxxxxxx` |
| `BOT_A_OPEN_ID` | Bot A's open ID in the platform | `ou_xxxxxxxxxxxxxxxx` |
| `BOT_B_OPEN_ID` | Bot B's open ID in the platform | `ou_xxxxxxxxxxxxxxxx` |

## Python API

```python
from group_chat_bot import GroupChatBotEngine

engine = GroupChatBotEngine(
    platform="feishu",
    app_id="your-app-id",
    app_secret="your-app-secret",
)

# Handle incoming message event
async def on_message(event):
    if event.is_bot_mention():
        target = event.mentioned_bot()
        if target == "bot-alpha":
            await engine.handle_coordinator_task(event)
        elif target == "bot-beta":
            await engine.handle_executor_task(event)

# Send a group message
await engine.send_group_message(
    chat_id="oc_xxxxxxxxxxxxxxxx",
    content="Analysis report generated. All checks passed.",
    mentions=["ou_xxxxxxxxxxxxxxxx"],  # @-mention specific users
)

# Bot-to-bot delegation
await engine.send_bot_message(
    target_open_id="ou_yyyyyyyyyyyyyyyy",
    content={"task": "code_review", "payload": {"file": "/output/report_v1.html"}},
)

# Send rich-media card message
await engine.send_card_message(
    chat_id="oc_xxxxxxxxxxxxxxxx",
    title="Analysis Complete",
    content=[
        {"tag": "text", "text": "Risk Score: "},
        {"tag": "text", "text": "72/100", "style": "bold"},
        {"tag": "at", "user_id": "ou_xxxxxxxxxxxxxxxx", "user_name": "Alice"},
    ],
)
```

## The Reply Tag Trap

**This is the #1 pitfall in group chat bot development.**

### Problem
In group chat "one-shot run" scenarios, using `reply_to` / `reply_tag` to respond to specific messages causes the platform runtime to **silently suppress** the bot's response. The API returns success, but `replies=0` — humans never see the message.

### Root Cause
When a bot uses `reply_to` in a group chat, the platform treats it as an inline reply to a thread. In certain runtime modes (especially one-shot invocation), the reply gets attached to an internal context that is discarded before rendering.

### Solution
| Situation | Correct Approach | Wrong Approach |
|---|---|---|
| Group chat response | Plain text + `<at>` mention | `reply_to` / `reply_tag` |
| DM (private chat) response | `reply_to` is fine | — |
| Multi-bot thread | Each bot sends independent message | Trying to reply to another bot's message |

```python
# GOOD: Group chat response
await engine.send_group_message(
    chat_id=chat_id,
    content="<at user_id=\"ou_xxx\">Alice</at> The analysis is complete.",
)

# BAD: Using reply tag in group chat
# [[reply_to_current]]  ← This will cause replies=0!
```

## Bot-to-Bot Collaboration Flow

```
User: @BotA Help me analyze Acme Corp's financial risk
    │
    ▼
BotA (Coordinator): "Starting financial risk analysis..."
    │ (Delegates via internal channel or direct message)
    ▼
BotB (Executor): "Querying financial database..."
    │ (Processes data, returns result)
    ▼
BotA: "Analysis complete. Risk score: 72/100"
    │ (Posts result in group — human can see and intervene)
    ▼
Human: "Check compliance as well"
    │
    ▼
BotA: "@BotC Please run compliance check on Acme Corp"
```

## Message Construction

### Rich Text (Post) Message

```python
post_content = {
    "zh_cn": {
        "title": "Analysis Report",
        "content": [
            [{"tag": "text", "text": "Company: "}],
            [{"tag": "text", "text": "Acme Corp", "style": "bold"}],
            [{"tag": "text", "text": "\nRisk Score: 72/100"}],
        ]
    }
}
```

### @-Mention in Text

```python
text_with_at = '<at user_id="ou_xxx">Alice</at> Please review the report'
```

### Interactive Card

```python
card = {
    "header": {"title": {"tag": "plain_text", "content": "Task Dispatch"}},
    "elements": [
        {"tag": "div", "text": {"tag": "lark_md", "content": "**Task:** Credit risk analysis\n**Deadline:** 2026-07-15"}},
        {"tag": "action", "actions": [
            {"tag": "button", "text": "Accept", "value": {"action": "accept"}},
            {"tag": "button", "text": "Reject", "value": {"action": "reject"}},
        ]},
    ],
}
```

## Platform-Specific Adapters

| Platform | Connector | Key Differences |
|---|---|---|
| Feishu/Lark | `FeishuConnector` | Reply tag trap, Bot cannot @Bot, rich cards |
| DingTalk | `DingTalkConnector` | Different webhook format, robot webhook only |
| Slack | `SlackConnector` | Bolt framework, block kit for rich messages |
| Teams | `TeamsConnector` | Adaptive cards, Bot Framework SDK |

## Pitfalls & Solutions

### 1. Reply Tag Trap (Critical)
Using `reply_to` in group chats causes silent message suppression. **Fix**: Always use plain text + `<at>` in group chats. Reserve `reply_to` for DMs only.

### 2. Bot Cannot @Bot on Most Platforms
Most chat platforms (Feishu, DingTalk) do not allow bots to directly @-mention other bots to trigger them. **Fix**: Use the platform's message send API to send a message that the target bot's webhook will receive. The bot sees it as an incoming event, not an @-mention.

### 3. Message Rate Limits
Sending too many messages in a short period triggers platform rate limits. **Fix**: Batch related information into a single rich-text or card message instead of multiple plain-text messages.

### 4. Webhook Security
Anyone who knows your webhook URL can send spoofed events. **Fix**: Always verify the event signature using the platform's verification protocol before processing.

## Industry Scenarios

### Financial Analysis Team
Three bots collaborate in a group chat visible to human analysts: Bot A coordinates, Bot B executes SQL queries, Bot C reviews for compliance. Human analysts can jump in anytime to redirect or add context.

### DevOps Incident Response
An alert bot posts a critical incident card. A diagnosis bot automatically begins investigation. A remediation bot proposes a fix. The on-call engineer reviews the thread and approves the fix with a single click.

### Customer Service Escalation
A tier-1 support bot handles routine queries. When it detects escalation signals, it @-mentions a tier-2 specialist bot in the same chat thread. The customer sees a seamless handoff. The human supervisor can monitor both bots' interactions.

## Quick Start

```bash
# Install
pip install group-chat-bot

# Configure
export CHAT_PLATFORM=feishu
export CHAT_APP_ID=your-app-id
export CHAT_APP_SECRET=your-app-secret
export GROUP_CHAT_ID=oc_xxxxxxxxxxxxxxxx

# Run
python -m group_chat_bot --config chat_config.yaml
```
