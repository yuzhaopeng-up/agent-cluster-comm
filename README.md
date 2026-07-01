# Agent Cluster Communication

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Skills](https://img.shields.io/badge/Skills-5-blue.svg)]()
[![Layers](https://img.shields.io/badge/Layers-5-green.svg)]()

> **5-Layer Communication Architecture for Multi-Agent Clusters** — Not a single messaging solution, but a complete communication stack: encrypted P2P, message bus, group chat, async handoff, and health monitoring. Each layer has a distinct role; together they provide full-spectrum coverage from confidential 1:1 to cross-timezone N:N coordination.

## Why 5 Layers?

No single communication channel covers all multi-agent scenarios:

| Scenario | What You Need | Single Channel Can't |
|----------|--------------|---------------------|
| Send credit check containing PII | End-to-end encryption | Message bus exposes to all subscribers |
| Broadcast "config updated" to all agents | 1:N real-time push | P2P requires N separate calls |
| Human observes bot negotiation in real time | Visible, rich-media thread | Message bus is invisible to humans |
| Agent in UTC+8 hands off to agent in UTC-5 | Async, zero-deploy, timezone-tolerant | Message bus requires both online |
| Two agents report conflicting heartbeats | Cross-channel health fusion | Checking one channel misses the other |

**The insight**: You don't choose one channel — you layer them like a network stack. Each layer handles what it's best at, and they degrade into each other when failures occur.

---

## 5-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  L5: Health Monitoring     cluster-health-monitor           │
│  Watches all layers, triggers failover                      │
├─────────────────────────────────────────────────────────────┤
│  L4: Async Handoff         github-async-handoff             │
│  Cross-timezone, zero-deploy, Issues-as-tickets             │
├─────────────────────────────────────────────────────────────┤
│  L3: Group Collaboration   group-chat-bot                   │
│  Human-visible, rich-media, bot-to-bot negotiation          │
├─────────────────────────────────────────────────────────────┤
│  L2: Message Bus           redis-message-bus                │
│  1:N broadcast, persistent queue, service discovery          │
├─────────────────────────────────────────────────────────────┤
│  L1: Encrypted P2P         encrypted-p2p-messaging          │
│  End-to-end encrypted 1:1, cross-firewall, webhook push     │
└─────────────────────────────────────────────────────────────┘
```

| Layer | Skill | Topology | Latency | Persistence | Encryption | Human-Visible |
|-------|-------|----------|---------|-------------|------------|---------------|
| L1 | encrypted-p2p-messaging | 1:1 | Medium (relay) | Relay stores until delivered | End-to-end | No |
| L2 | redis-message-bus | 1:N / N:N | Low (sub-ms) | Stream durable | Transport only | No |
| L3 | group-chat-bot | N:N | Medium (API) | Platform stores | Platform-level | **Yes** |
| L4 | github-async-handoff | 1:1 / 1:N | Hours OK | Issues + Git history | HTTPS + ACL | **Yes** |
| L5 | cluster-health-monitor | Monitor | Check cycle | Alert history | — | **Yes** (via L3) |

---

## Scene-Based Selection Guide

### When to use L1 — Encrypted P2P

| You should use P2P when... | Example |
|---|---|
| Message contains PII, credentials, or financial data | Credit check, compliance query, KYC data exchange |
| You need confidential 1:1 communication between specific agents | Legal review bot sending privileged documents to compliance bot |
| Agents are behind different firewalls/NATs with no direct connectivity | Cloud agent talking to on-premise agent |

### When to use L2 — Message Bus

| You should use Message Bus when... | Example |
|---|---|
| You need to broadcast a notification to all agents | "Config updated", "Model reload required", "Market data refresh" |
| You need persistent queuing with guaranteed delivery | Task dispatch with audit trail, message replay after disconnect |
| You need service discovery — "which agents can do X?" | Find all agents with "anomaly detection" capability |

### When to use L3 — Group Chat Bot

| You should use Group Chat when... | Example |
|---|---|
| Humans need to observe the collaboration process | Financial analysis team with human analysts in the loop |
| You need rich-media output (cards, tables, charts) | Risk dashboard cards, interactive buttons for approval |
| You want human-in-the-loop intervention | "Should I proceed with this trade?" — human says yes/no |
| Bots need to negotiate in a visible thread | Bot A proposes analysis plan, Bot B suggests alternative, human picks |

### When to use L4 — GitHub Async Handoff

| You should use Async Handoff when... | Example |
|---|---|
| Agents operate on different schedules / timezones | Team in UTC+8 finishes, team in UTC-5 starts tomorrow |
| You need zero-deploy coordination (no Redis, no relay) | Open-source collaboration, hackathon, classroom |
| You need built-in artifact transfer (code, data, docs) | CI/CD pipeline: build → test → deploy handoff chain |
| You need full audit trail for compliance | Regulated industries requiring immutable, timestamped records |

### When to use L5 — Cluster Health Monitor

| You should use Health Monitor when... | Example |
|---|---|
| Your cluster has 3+ agents that must stay coordinated | Production financial analysis cluster |
| You need to detect and recover from partial failures | One agent goes stale, others need to redistribute its tasks |
| You want automated failover between communication layers | L2 (Redis) goes down → automatically switch to L4 (GitHub) |

---

## Combination Patterns

### Pattern 1: Real-Time Analysis Cluster (L1 + L2 + L3)

```
                  ┌───────────────────────────────┐
                  │   Group Chat (L3)              │
                  │   Human-visible thread         │
                  │   "Risk analysis starting..."   │
                  └──────────┬────────────────────┘
                             │ observe
┌──────────┐  L2: Broadcast  ┌──────────┐  L1: Encrypted  ┌──────────┐
│ Agent A   │ ──────────────> │ Agent B   │ <─────────────> │ Agent C   │
│Coordinator│  "Start query"  │ Executor  │   Credit check   │Compliance│
└──────────┘                  └──────────┘   (PII encrypted)  └──────────┘
```

**How it works**: Agent A broadcasts a task via L2 (message bus). Agent B picks it up and executes. For the compliance sub-task that contains PII, Agent B uses L1 (encrypted P2P) to communicate with Agent C. Throughout, all status updates appear in L3 (group chat) so humans can observe.

**Typical for**: Financial analysis, healthcare diagnostics, legal review.

### Pattern 2: Cross-Timezone Research Team (L2 + L3 + L4)

```
┌──────────┐                  ┌──────────┐
│ Agent A   │ ── L4: Handoff ─> │ Agent B   │
│ UTC+8     │  GitHub Issue     │ UTC-5     │
│ Evening   │  "Data collected" │ Morning   │
└────┬─────┘                  └────┬─────┘
     │ L3: Status update            │ L3: "Continuing analysis"
     ▼                              ▼
┌──────────────────────────────────────────┐
│         Group Chat (L3)                   │
│  "Agent A: Data collection done for today │
│   Agent B: Picking up where A left off"   │
└──────────────────────────────────────────┘
```

**How it works**: Agent A finishes its workday and creates a GitHub Issue (L4) with the day's results pushed to its branch. Agent B starts its workday, claims the Issue, pulls the data, and continues. Both post status updates in group chat (L3) so the team sees continuity.

**Typical for**: Distributed research teams, open-source collaboration, education/classroom scenarios.

### Pattern 3: Failover Chain (L2 → L4, triggered by L5)

```
          L5 detects L2 failure
                 │
                 ▼
    ┌─────────────────────────────┐
    │  Normal: L2 (Message Bus)   │ ──X── DOWN
    │  Fallback: L4 (Handoff)     │ ──→  ACTIVE
    └─────────────────────────────┘
         │                    │
         ▼                    ▼
    L3: Alert posted     L4: All agents
    "Redis unreachable"  switch to Issues
```

**How it works**: L5 (health monitor) detects that the Redis message bus is unreachable. It immediately posts a CRITICAL alert in group chat (L3) and sends P2P notifications (L1). All agents switch to L4 (GitHub async handoff) for inter-agent coordination. When Redis recovers, agents replay unresolved Issues back to the message bus.

**Typical for**: Production clusters requiring high availability, any system where communication failure cascades into data loss.

### Pattern 4: Secure Multi-Party Computation (L1 + L5)

```
┌──────────┐   L1: Encrypted     ┌──────────┐   L1: Encrypted     ┌──────────┐
│ Agent A   │ <─────────────────> │ Agent B   │ <─────────────────> │ Agent C   │
│Has data A │  "Request for B"   │Has data B │  "Request for C"   │Has data C │
└──────────┘                     └──────────┘                     └──────────┘
     ▲                                ▲                                ▲
     │         L5: Health Watch       │                                │
     └────────────────────────────────┴────────────────────────────────┘
```

**How it works**: Three agents each hold different pieces of sensitive data. They must compute a combined result without revealing their individual inputs. All communication uses L1 (encrypted P2P) — no message bus, no group chat. L5 monitors that all three agents remain online and responsive throughout the computation.

**Typical for**: Multi-party risk scoring, cross-institution compliance verification, privacy-preserving analytics.

---

## Failover Decision Flowchart

```
Agent needs to send a message
         │
         ▼
   Contains PII/sensitive data?
    ├── YES → Use L1 (Encrypted P2P)
    │           │
    │           ▼
    │      Recipient online?
    │       ├── YES → Send via L1
    │       └── NO  → Queue in L4 (Async Handoff), notify via L3
    │
    └── NO → Need broadcast (1:N)?
             ├── YES → L2 (Message Bus) available?
             │        ├── YES → Use L2
             │        └── NO  → Fall back to L4 (create Issue per recipient)
             │                  + Notify via L3 + L5 alert
             │
             └── NO → Need human visibility?
                      ├── YES → Use L3 (Group Chat)
                      └── NO  → Use L1 (P2P) or L2 (Bus) based on latency needs
```

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/yuzhaopeng-up/agent-cluster-comm.git

# Install all 5 skills
cp -r agent-cluster-comm/skills/* ~/.config/TeleAgent/skills/
```

### Minimum Viable Cluster (2 layers)

If you want to start simple, just use L1 + L2:

```bash
# L1: Encrypted P2P for sensitive data
pip install encrypted-p2p-messaging

# L2: Redis Message Bus for broadcast
docker run -d --name redis-bus -p 6379:6379 redis:7-alpine
pip install redis-message-bus
```

### Full Stack (all 5 layers)

```bash
# L1: Encrypted P2P
docker run -d --name p2p-relay -p 8765:8765 your-org/p2p-relay:latest

# L2: Redis Message Bus
docker run -d --name redis-bus -p 6379:6379 redis:7-alpine

# L3: Group Chat Bot (configure with your platform credentials)
export CHAT_PLATFORM=feishu
export CHAT_APP_ID=your-app-id
export CHAT_APP_SECRET=your-app-secret

# L4: GitHub Async Handoff (zero deploy)
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
export HANDOFF_REPO=your-org/agent-workspace

# L5: Cluster Health Monitor
cluster-health-monitor watch --interval 60
```

---

## Skills Overview

| # | Layer | Skill | Description | Key Value |
|---|-------|-------|-------------|-----------|
| 1 | L1 | [encrypted-p2p-messaging](skills/encrypted-p2p-messaging/) | End-to-end encrypted 1:1 communication via relay | Confidentiality, cross-firewall |
| 2 | L2 | [redis-message-bus](skills/redis-message-bus/) | Async Pub/Sub + Stream message bus | Broadcast, persistence, service discovery |
| 3 | L3 | [group-chat-bot](skills/group-chat-bot/) | Group chat bot collaboration with rich media | Human-visible, intervenable, the reply-tag trap solution |
| 4 | L4 | [github-async-handoff](skills/github-async-handoff/) | Decentralized async task handoff via GitHub | Zero-deploy, cross-timezone, built-in audit |
| 5 | L5 | [cluster-health-monitor](skills/cluster-health-monitor/) | Multi-channel health monitoring with tiered alerts | Cross-channel fusion, failover trigger |

---

## Comparison Matrix

| Dimension | L1 P2P | L2 Message Bus | L3 Group Chat | L4 Async Handoff | L5 Health Monitor |
|-----------|--------|----------------|---------------|------------------|-------------------|
| Topology | 1:1 | 1:N, N:N | N:N | 1:1, 1:N | Monitor |
| Latency | Medium | Low | Medium | Hours OK | Check cycle |
| Persistence | Relay | Stream | Platform | Issues + Git | Alert log |
| Encryption | E2E | Transport | Platform | HTTPS | — |
| Human-visible | No | No | **Yes** | **Yes** | **Yes** |
| Zero deploy | No (relay) | No (Redis) | No (platform) | **Yes** | No |
| Artifact transfer | Small only | No | Rich media | **Git push/pull** | — |
| Fall back to | L4 | L4 | L1 | — | Alert via L1/L3 |

---

## Industry Scenarios

### Financial Services
- L1: Encrypted credit check between risk and compliance agents
- L2: Real-time market event broadcast to all analysis agents
- L3: Human analysts observe bot negotiation in group chat
- L4: Overnight batch results handed off to morning shift
- L5: Detect stale risk agents and trigger redistribution

### Healthcare
- L1: Patient data exchange between diagnostic and specialist agents
- L2: Alert broadcast to all monitoring agents
- L3: Doctor observes AI diagnostic process in real time
- L4: Lab results uploaded for next-day review
- L5: Monitor all agents processing patient data for compliance

### DevOps / SRE
- L1: Secure credential exchange between deployment agents
- L2: Incident alert broadcast to all on-call agents
- L3: On-call engineer observes automated incident response
- L4: Build → test → deploy CI/CD pipeline handoff chain
- L5: Detect agent failures and trigger automated remediation

### Education / Research
- L1: Student-teacher private query channel
- L2: Assignment broadcast to all student agents
- L3: Classroom-visible collaborative problem solving
- L4: Asynchronous peer review across time zones
- L5: Monitor student agent participation and flag inactive students

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). We especially welcome:
- New platform adapters for L3 (Slack, Teams, DingTalk, Discord)
- New failover strategies for L5
- Architecture patterns combining these layers in novel ways
- Real-world deployment stories

## Security

- All example data is fully anonymized
- No real credentials, IP addresses, or internal identifiers in any file
- See [SECURITY.md](SECURITY.md) for vulnerability reporting

## License

Apache License 2.0 — Free for commercial and personal use.

---

If this 5-layer architecture helps your multi-agent project, please give it a star! It helps others discover it.

---

## 🌐 Agent Skills Ecosystem

This repo is part of the **Agent Skills** open-source ecosystem. Five repos work together to cover the full Agent development lifecycle:

| Repository | Focus | Scale | Core Capabilities |
|------------|-------|-------|-------------------|
| [financial-ai-skills](https://github.com/yuzhaopeng-up/financial-ai-skills) | Financial industry Agent | 104 Skills | Invoice verification, budget control, risk compliance, wealth management |
| [teleagent-skills](https://github.com/yuzhaopeng-up/teleagent-skills) | General-purpose Agent | 5 Skills | Scoring engine, evidence chain, data aggregator, NL2Query, visualization |
| [agent-cluster-comm](https://github.com/yuzhaopeng-up/agent-cluster-comm) (this repo) | Agent cluster communication | 5 Skills | Encrypted P2P, Redis message bus, group chat bot, GitHub async handoff, health monitoring |
| [skill-framework](https://github.com/yuzhaopeng-up/skill-framework) | Skill governance framework & templates | 208 cataloged | Skill catalog, governance templates, standardization tooling |
| [fintech-h5-demos](https://github.com/yuzhaopeng-up/fintech-h5-demos) | Financial dashboard demos (zero-dependency HTML) | 12 demos | Interactive financial visualization, pure frontend implementation |