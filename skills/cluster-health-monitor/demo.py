"""
Demo: L5 Cluster Health Monitor
Monitor 4 simulated nodes across P2P, message bus, and group chat channels.
"""

import asyncio
from skills.cluster_health_monitor import ClusterHealthMonitor


async def main():
    monitor = ClusterHealthMonitor(config={
        "cluster_name": "demo-cluster",
        "nodes": [
            {"id": "agent-alpha", "name": "Coordinator", "roles": ["coordinator"]},
            {"id": "agent-beta", "name": "Analyst", "roles": ["analyst"]},
            {"id": "agent-gamma", "name": "Reviewer", "roles": ["reviewer"]},
            {"id": "agent-delta", "name": "Executor", "roles": ["executor"]},
        ],
        "channels": {
            "p2p_relay": {"enabled": True},
            "message_bus": {"enabled": True, "redis_url": "redis://localhost:6379/0"},
            "group_chat": {"enabled": True, "platform": "feishu"},
        },
        "alerts": {
            "critical_threshold": 300,
            "warning_threshold": 120,
        },
    })

    # Simulate healthy cluster
    print("=== Initial Check (Healthy) ===")
    report = await monitor.check_all()
    print(report.summary())

    # Simulate failures
    print("\n=== After Failures ===")
    monitor.simulate_node_failure("agent-delta")
    monitor.simulate_channel_unreachable("message_bus")

    report = await monitor.check_all()
    print(report.summary())

    print("\n[Alerts]")
    for alert in report.get_alerts():
        print(f"  [{alert['level']}] {alert['node']}: {alert['message']}")


if __name__ == "__main__":
    asyncio.run(main())
