---
name: encrypted-p2p-messaging
version: 1.0.0
author: open-community
license: MIT
description: |
  End-to-end encrypted P2P communication protocol for multi-agent clusters.
  Supports relay-based message routing, webhook push (no polling needed),
  and cross-firewall/NAT traversal. No public IP required on any node.
  Ideal for sensitive data exchange, private task delegation, and
  any scenario requiring confidentiality between specific agent pairs.
---

# encrypted-p2p-messaging

## Design Motivation

In a multi-agent cluster, some communications must remain private — credit checks, compliance queries, credential exchanges. Broadcasting through a message bus exposes these to all subscribers. **encrypted-p2p-messaging** provides end-to-end encrypted 1:1 channels where only the sender and designated receiver can read the content.

## Core Capabilities

| Capability | Description |
|---|---|
| End-to-end Encryption | Message payload encrypted before leaving sender; decrypted only at receiver |
| No Public IP Required | Relay server acts as encrypted router; nodes stay behind NAT/firewall |
| Webhook Push | Real-time delivery via webhook callback — no polling needed |
| Cross-Firewall/NAT | Works across corporate networks, cloud VPCs, and home offices |
| Friend-Based Trust | Nodes must mutually accept before communication begins |

## Architecture

```
┌──────────────┐                       ┌──────────────┐
│  Agent Alpha  │                       │  Agent Beta   │
│  (no public IP)│                      │  (no public IP)│
└──────┬───────┘                       └───────┬───────┘
       │        Encrypted Message               │
       │ ══════════════════════════════════════  │
       │          (E2E encrypted)                │
       └──────────────┬─────────────────────────┘
                      │
               ┌──────┴──────┐
               │  Relay Server │
               │  (public IP)  │
               └──────────────┘
```

**Trust model**: Nodes register with the relay and explicitly add each other as "friends". Only accepted friends can exchange messages. The relay sees encrypted blobs — it cannot read payloads.

## Configuration

```yaml
# encrypted-p2p-messaging config
relay:
  url: ${RELAY_URL:https://your-relay-server:8765}
  auth_token: ${RELAY_AUTH_TOKEN:}

node:
  id: ${NODE_ID:}              # Auto-generated on first start if empty
  name: ${NODE_NAME:agent-alpha}

push:
  mode: "webhook"              # webhook (recommended) | polling
  webhook_url: ${WEBHOOK_URL:}  # Your endpoint to receive pushed messages
  poll_interval: 30             # Seconds between polls (polling mode only)
```

### Environment Variables

| Variable | Description | Example |
|---|---|---|
| `RELAY_URL` | Relay server URL | `https://your-relay-host:8765` |
| `RELAY_AUTH_TOKEN` | Authentication token for relay | `your-relay-token` |
| `NODE_ID` | This node's unique ID | Auto-generated |
| `WEBHOOK_URL` | Endpoint for receiving pushed messages | `https://your-server/webhook/p2p` |

## CLI Interface

```bash
# Check status
p2p-messaging status

# List friends
p2p-messaging friends

# Send message to a friend
p2p-messaging send <friend_id> '{"task": "credit_check", "payload": {"company": "Acme Corp"}}'

# View message history with a friend
p2p-messaging history <friend_id>

# Accept friend request
p2p-messaging accept <request_id>

# Add a friend
p2p-messaging add-friend <friend_id>

# Configure webhook for push delivery
p2p-messaging set-webhook https://your-server.com/webhook/p2p
```

## Python API

```python
from encrypted_p2p_messaging import P2PMessagingEngine

engine = P2PMessagingEngine(
    relay_url="https://your-relay-host:8765",
    node_name="agent-alpha",
)

# Send encrypted message to specific agent
engine.send_message(
    target="claw_xxxxxxxx",  # Friend's node ID
    message={"task": "credit_check", "payload": {"company": "Acme Corp", "amount": "5M"}},
)

# Receive messages (polling mode)
messages = engine.poll_messages(timeout=5)

# Webhook mode: messages are pushed to your endpoint
# No polling needed — configure with set-webhook

# Get node status
status = engine.get_status()
```

## Message Protocol

All messages follow this JSON structure (encrypted in transit):

```json
{
    "from_node": "agent-alpha",
    "to_node": "agent-beta",
    "task_id": "task_20260628_001",
    "msg_type": "task",
    "task_type": "credit_check",
    "payload": { "...": "..." },
    "timestamp": "2026-06-28T10:00:00Z",
    "trace_id": "trace_abc123"
}
```

**Message types**:

| msg_type | Direction | Purpose |
|---|---|---|
| `task` | Initiator → Worker | Delegate a task |
| `result` | Worker → Initiator | Return task result |
| `event` | Any → Any | Notify of state change |
| `heartbeat` | Any → Relay | Keep-alive signal |

## Integration Modes

### Mode 1: Webhook Push (Recommended)

Real-time message delivery. The relay server pushes new messages to your webhook endpoint as they arrive.

```python
# Configure on receiver side
p2p-messaging set-webhook https://your-server.com/webhook/p2p

# Your webhook handler receives POST requests with encrypted messages
```

**Pros**: Zero latency, no wasted polling cycles.
**Cons**: Requires an HTTP endpoint reachable from the relay.

### Mode 2: Polling

Periodically check for new messages. Simple but introduces latency.

```python
while True:
    messages = engine.poll_messages(timeout=30)
    for msg in messages:
        process_message(msg)
```

**Pros**: Works behind any firewall, no public endpoint needed.
**Cons**: Up to `poll_interval` seconds of latency; wasted cycles when idle.

### Mode 3: SSH Tunnel (Internal Network)

Tunnel through an SSH connection to access the relay from restricted environments.

```bash
ssh -L 8765:localhost:8765 user@jump-server
p2p-messaging init --relay-url http://localhost:8765
```

**Pros**: Works in environments with strict outbound rules.
**Cons**: Requires SSH access to a relay-facing host.

## When to Use P2P vs. Message Bus

| Dimension | P2P Messaging | Message Bus (Redis) |
|---|---|---|
| Topology | 1:1 encrypted | 1:N broadcast |
| Confidentiality | End-to-end encrypted | All subscribers see messages |
| Latency | Medium (relay hop) | Low (direct network) |
| Persistence | Relay stores until delivered | Pub/Sub: none; Stream: durable |
| Deployment | Relay server | Redis server |
| Use for | Sensitive data, private delegation | Status broadcasts, general coordination |

**Selection rule**: Use P2P for any message containing sensitive data or requiring confidentiality. Use Message Bus for broadcast notifications and non-sensitive coordination.

## Industry Scenarios

### Financial Compliance Check
Agent Alpha receives a compliance query and needs to delegate a credit risk check to Agent Beta. The request contains customer PII and financial data. P2P ensures end-to-end encryption — even the relay server cannot read the payload.

### Healthcare Patient Data Exchange
A diagnostic agent needs to send patient imaging results to a specialist agent. HIPAA requires encryption in transit and at rest. P2P provides end-to-end encryption without exposing data to any intermediary.

### Legal Document Review
A contract review agent sends confidential legal documents to a compliance verification agent. The documents contain privileged information that must not be visible on any shared message bus.

## Pitfalls & Solutions

### 1. No Broadcast Capability
P2P is strictly 1:1. To notify multiple agents, you must send individually. **Fix**: Use message bus for broadcast notifications, then use P2P for the actual sensitive payload exchange.

### 2. Relay is a Single Point of Failure
If the relay goes down, all P2P communication stops. **Fix**: Deploy relay with high availability (replica set). Fall back to message bus or async handoff for critical messages during relay outages.

### 3. Message Size Limit
Encrypted P2P messages should stay under 64KB. **Fix**: For large payloads, send a reference/path via P2P and transfer the actual data through object storage or git. The P2P message serves as the auth token for the data fetch.

### 4. Friend Request Latency
New nodes must mutually accept friend requests before communicating, which can delay onboarding. **Fix**: Pre-configure friend relationships in the relay registry for known cluster members.

## Quick Start

```bash
# Deploy relay server
docker run -d --name p2p-relay -p 8765:8765 your-org/p2p-relay:latest

# Initialize a node
p2p-messaging init --relay-url https://your-relay:8765 --name agent-alpha

# Add a friend
p2p-messaging add-friend <friend-node-id>

# Send a message
p2p-messaging send <friend-node-id> '{"task": "analyze", "payload": {"dataset": "q2_report"}}'
```
