"""
Master Demo: 5-Layer Agent Cluster Communication Architecture

This script demonstrates how all 5 communication layers work together:
L1: Encrypted P2P      - Two agents exchange a confidential message
L2: Message Bus        - Coordinator broadcasts a task to all workers
L3: Group Chat Bot     - Bots negotiate in a human-visible thread
L4: GitHub Handoff     - Async handoff when an agent is "offline"
L5: Health Monitor     - Detect failure and trigger alert
"""

import asyncio

from skills.encrypted_p2p_messaging import P2PMessagingEngine, SimulatedRelayServer
from skills.redis_message_bus import RedisMessageBus, SimulatedRedisBackend
from skills.group_chat_bot import GroupChatBotEngine, SimulatedChatPlatform
from skills.github_async_handoff import HandoffClient, InMemoryGitHubBackend
from skills.cluster_health_monitor import ClusterHealthMonitor


async def demo_l1_p2p():
    print("\n" + "=" * 60)
    print("L1: Encrypted P2P Messaging")
    print("=" * 60)
    relay = SimulatedRelayServer()
    alice = P2PMessagingEngine("agent-alpha", relay)
    bob = P2PMessagingEngine("agent-beta", relay)
    alice.send_friend_request("agent-beta")
    bob.accept_pending_requests()
    msg_id = alice.send("agent-beta", '{"task": "credit_check", "company": "Acme Corp"}')
    messages = bob.poll()
    print(f"[Agent Alpha] Sent encrypted message: {msg_id}")
    print(f"[Agent Beta] Decrypted: {messages[0].plaintext}")
    print(f"[Relay Stats] {relay.get_stats()}")


async def demo_l2_bus():
    print("\n" + "=" * 60)
    print("L2: Redis Message Bus")
    print("=" * 60)
    backend = SimulatedRedisBackend()
    alpha = RedisMessageBus("agent-alpha", backend)
    beta = RedisMessageBus("agent-beta", backend)
    await alpha.subscribe("agent:broadcast")
    await beta.subscribe("agent:broadcast")
    await alpha.publish("agent:broadcast", {"type": "config_update", "threshold": 0.85})
    await alpha.send_to_stream("agent:tasks", {"task_id": "T001", "action": "analyze"})
    async for msg in beta.listen(timeout=2):
        print(f"[Agent Beta] Received broadcast: {msg['data']}")
        break


async def demo_l3_chat():
    print("\n" + "=" * 60)
    print("L3: Group Chat Bot")
    print("=" * 60)
    platform = SimulatedChatPlatform()
    bot_a = GroupChatBotEngine("bot-alpha", platform)
    bot_b = GroupChatBotEngine("bot-beta", platform)
    await bot_a.send_group_message(
        chat_id="group-001",
        content="Starting analysis. @bot-beta please run query.",
        mentions=["bot-beta"],
    )
    await bot_b.send_group_message(
        chat_id="group-001",
        content="Query done. Risk score: 72/100.",
    )
    print("[Group Chat Thread]")
    for msg in platform.get_chat_history("group-001"):
        print(f"  {msg['sender']}: {msg['content']}")


async def demo_l4_handoff():
    print("\n" + "=" * 60)
    print("L4: GitHub Async Handoff")
    print("=" * 60)
    backend = InMemoryGitHubBackend()
    agent_a = HandoffClient(repo="demo-org/workspace", backend=backend)
    agent_b = HandoffClient(repo="demo-org/workspace", backend=backend)
    issue = agent_a.create_handoff(
        title="[Handoff] Analyze Q2 revenue",
        body="Dataset ready in /data/q2_revenue.csv",
        labels=["handoff"],
    )
    print(f"[Agent A] Created Issue #{issue['number']}")
    agent_b.claim_handoff(issue["number"], assignee="agent-beta")
    agent_b.complete_handoff(issue["number"], summary="Q2 revenue grew 18.3% QoQ.")
    print(f"[Agent B] Completed Issue #{issue['number']}")


async def demo_l5_health():
    print("\n" + "=" * 60)
    print("L5: Cluster Health Monitor")
    print("=" * 60)
    monitor = ClusterHealthMonitor(config={
        "cluster_name": "demo-cluster",
        "nodes": [
            {"id": "agent-alpha", "name": "Coordinator"},
            {"id": "agent-beta", "name": "Analyst"},
            {"id": "agent-gamma", "name": "Reviewer"},
            {"id": "agent-delta", "name": "Executor"},
        ],
        "channels": {
            "p2p_relay": {"enabled": True},
            "message_bus": {"enabled": True},
            "group_chat": {"enabled": True},
        },
        "alerts": {"critical_threshold": 300, "warning_threshold": 120},
    })
    monitor.simulate_node_failure("agent-delta")
    report = await monitor.check_all()
    print(report.summary())
    print("[Alerts]")
    for alert in report.get_alerts():
        print(f"  [{alert['level']}] {alert['node']}: {alert['message']}")


async def main():
    print("\nAgent Cluster Communication — 5-Layer Master Demo")
    print("Running all layers in sequence...")
    await demo_l1_p2p()
    await demo_l2_bus()
    await demo_l3_chat()
    await demo_l4_handoff()
    await demo_l5_health()
    print("\n" + "=" * 60)
    print("Demo complete. All 5 layers executed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
