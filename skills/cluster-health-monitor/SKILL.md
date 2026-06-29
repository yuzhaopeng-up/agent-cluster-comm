---
name: cluster-health-monitor
version: 1.0.0
author: open-community
license: MIT
description: |
  Multi-channel health monitoring for multi-agent clusters.
  Monitors node liveness across all communication channels (P2P relay,
  message bus, group chat bots), detects heartbeats, tracks version
  drift and task queue depth, and triggers tiered alerts.
  Acts as the cluster's "vital signs dashboard".
---

# cluster-health-monitor

## Design Motivation

A multi-agent cluster depends on multiple communication channels — P2P links, message buses, group chat bots. When any channel or node fails, downstream agents stall silently. **cluster-health-monitor** watches all channels simultaneously and provides early warning before a partial failure cascades into a cluster-wide outage.

**Unique value**: Unlike monitoring a single service, this skill monitors the **intersection** of all communication layers. A node may be reachable via P2P but have a stale message bus heartbeat — only cross-channel monitoring catches this discrepancy.

## Core Capabilities

| Capability | Description |
|---|---|
| Multi-Channel Monitoring | Check P2P relay, message bus, and group chat bot status in one pass |
| Heartbeat Detection | Track per-node heartbeat recency with configurable thresholds |
| Tiered Alerts | INFO / WARNING / CRITICAL levels with escalation rules |
| Version Drift Detection | Flag agents running different software versions |
| Queue Depth Tracking | Alert when task queues exceed capacity |
| CLI + API | One-shot check or continuous watch mode |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│               ClusterHealthMonitor                   │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│
│  │  P2P Channel  │  │  MsgBus Chan │  │  Chat Chan  ││
│  │  Check        │  │  Check       │  │  Check      ││
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘│
│         │                 │                  │       │
│         └────────┬────────┴──────────┬──────┘       │
│                  │                   │               │
│            ┌─────┴─────┐      ┌──────┴──────┐       │
│            │  Node      │      │  Alert      │       │
│            │  Status    │      │  Engine     │       │
│            │  Merger    │      │             │       │
│            └─────┬─────┘      └──────┬──────┘       │
│                  │                   │               │
│            ┌─────┴─────┐      ┌──────┴──────┐       │
│            │  Health    │      │  Report     │       │
│            │  Report    │◄─────┤  Generator  │       │
│            └───────────┘      └─────────────┘       │
└─────────────────────────────────────────────────────┘
```

**Cross-channel fusion**: A node is considered healthy only if it is active on **at least one** communication channel. If a node appears on P2P but not on the message bus, the monitor flags a "partial degradation" warning.

## Configuration

```yaml
# cluster-health-monitor config
cluster:
  name: ${CLUSTER_NAME:default-cluster}
  nodes:
    - id: ${NODE_ALPHA_ID:}
      name: "agent-alpha"
      roles: ["coordinator", "analyst"]
    - id: ${NODE_BETA_ID:}
      name: "agent-beta"
      roles: ["executor"]
    - id: ${NODE_GAMMA_ID:}
      name: "agent-gamma"
      roles: ["reviewer"]

channels:
  p2p_relay:
    enabled: true
    status_command: "p2p-messaging status"
    friends_command: "p2p-messaging friends"
  
  message_bus:
    enabled: true
    redis_url: ${REDIS_URL:redis://localhost:6379/0}
    heartbeat_prefix: "cluster:node:"
    registry_prefix: "cluster:registry:"
  
  group_chat:
    enabled: false
    platform: ${CHAT_PLATFORM:feishu}
    chat_id: ${GROUP_CHAT_ID:}

alerts:
  critical_threshold: 300    # seconds without heartbeat → CRITICAL
  warning_threshold: 120     # seconds without heartbeat → WARNING
  queue_overflow: 100        # pending tasks → overflow alert
  notify_channels:
    - "group_chat"
    - "webhook"
  webhook_url: ${ALERT_WEBHOOK_URL:}
```

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `CLUSTER_NAME` | Cluster identifier | `production-cluster` |
| `REDIS_URL` | Redis connection string | `redis://:password@redis-host:6379/0` |
| `NODE_ALPHA_ID` | Node Alpha's P2P ID | `claw_xxxxxxxx` |
| `ALERT_WEBHOOK_URL` | Webhook for alert notifications | `https://your-server/alerts` |

## Check Items

### 1. Node Liveness via P2P Relay

```bash
p2p-messaging status      # This node's status
p2p-messaging friends     # All friends' online status
p2p-messaging messages    # Channel health (can we send/receive?)
```

### 2. Node Heartbeat via Message Bus

```python
# Each node writes heartbeat key: cluster:node:{node_id}
# Contains: {"last_seen": timestamp, "version": "1.2.0", "queue_depth": 3}
import redis
r = redis.from_url("redis://localhost:6379/0")
heartbeat = r.get("cluster:node:agent-alpha")
```

### 3. Group Chat Bot Status

Check if bots are responding to messages in the configured group chat.

### 4. Version Consistency

Compare software version across all nodes. Flag if any node runs a different version.

### 5. Queue Depth

Check each node's task queue. Alert if any node's queue exceeds the overflow threshold.

## Alert Rules

| Level | Condition | Action |
|-------|-----------|--------|
| CRITICAL | Heartbeat missing > 5 minutes | Immediate notification to all channels |
| WARNING | Heartbeat missing > 2 minutes | Log + notify coordinator |
| INFO | Node recovered online | Log + notification |
| CRITICAL | Queue depth > overflow threshold | Immediate notification |
| WARNING | Version drift detected | Log + notify admin |

## Python API

```python
from cluster_health_monitor import ClusterHealthMonitor

monitor = ClusterHealthMonitor(config_path="health_config.yaml")

# One-shot health check
report = await monitor.check_all()

# Print summary
print(report.summary())

# Print per-node details
for node, status in report.details().items():
    print(f"  {node}: {status['state']} (heartbeat: {status['last_seen']}s ago)")

# Get filtered alerts
alerts = report.get_alerts(level="WARNING")
for alert in alerts:
    print(f"[{alert['level']}] {alert['node']}: {alert['message']}")

# Check specific channel
channel_status = report.channel_status()
for channel, healthy in channel_status.items():
    print(f"  {channel}: {'OK' if healthy else 'UNREACHABLE'}")
```

## CLI Usage

```bash
# One-shot health check
cluster-health-monitor check

# Continuous monitoring (every 60 seconds)
cluster-health-monitor watch --interval 60

# JSON output for integration
cluster-health-monitor check --format json

# Check specific channel only
cluster-health-monitor check --channel message_bus
```

## Output Example

```
Agent Cluster Health Report
========================================
Check Time: 2026-06-28 15:30:00

  Agent-Alpha    ONLINE   (heartbeat: 10s ago, queue: 3 tasks)
  Agent-Beta     ONLINE   (heartbeat: 30s ago, queue: 7 tasks)
  Agent-Gamma    STALE    (heartbeat: 3 min ago, queue: 2 tasks)
  Agent-Delta    OFFLINE  (heartbeat: 10 min ago, queue: unknown)

Channel Status:
  P2P Relay      OK
  Message Bus    OK
  Group Chat     UNREACHABLE

Alerts:
  [WARNING]  Agent-Gamma: Heartbeat delay (3 min)
  [CRITICAL] Agent-Delta: Node offline (10 min no heartbeat)
  [WARNING]  Group Chat: Channel unreachable

========================================
Overall Status: DEGRADED (2/4 nodes healthy)
```

## Integration with Other Communication Layers

cluster-health-monitor is the **L5 observability layer** in the 5-layer architecture:

```
L5: Health Monitoring     ← cluster-health-monitor (THIS SKILL)
L4: Async Handoff         ← github-async-handoff
L3: Group Collaboration   ← group-chat-bot
L2: Message Bus           ← redis-message-bus
L1: Encrypted P2P         ← encrypted-p2p-messaging
```

**Fallback detection**: When L2 (message bus) goes down, the health monitor detects it within one check cycle and triggers L4 (async handoff) as a fallback channel.

**Health-driven failover protocol**:
1. Monitor detects L2 Redis unreachable
2. Emits CRITICAL alert via L3 (group chat) and L1 (P2P)
3. All agents switch to L4 (GitHub async handoff) for inter-agent communication
4. Monitor continues checking L2 every 60s
5. When L2 recovers, monitor emits INFO alert
6. Agents replay unresolved handoff Issues back to L2 and resume normal operation

## Pitfalls & Solutions

### 1. False Positive Alerts
A node under heavy load may miss a heartbeat window but is still functional. **Fix**: Use a 2-out-of-3 check strategy — only trigger WARNING if 2+ consecutive checks miss the heartbeat. Only escalate to CRITICAL after 5+ minutes.

### 2. Monitor Itself Goes Down
If the health monitor crashes, nobody is watching the cluster. **Fix**: Run a lightweight heartbeat daemon (separate process) that only emits an "I'm alive" signal. If it stops, another agent detects the missing signal and restarts the monitor.

### 3. Alert Fatigue
Too many alerts cause operators to ignore them. **Fix**: Implement alert suppression — if a node is already in CRITICAL state, don't re-alert until it recovers and goes CRITICAL again.

### 4. Password Rotation Breaks Redis Connection
When Redis password changes, health checks silently fail. **Fix**: Store Redis credentials in an environment variable and validate the connection on each check cycle. If auth fails, emit a specific "auth error" alert distinct from "node unreachable".

## Quick Start

```bash
# Install
pip install cluster-health-monitor

# Configure
export REDIS_URL="redis://:your-password@your-redis-host:6379/0"
export CLUSTER_NAME="my-cluster"

# Run one-shot check
cluster-health-monitor check

# Run continuous watch
cluster-health-monitor watch --interval 60
```
