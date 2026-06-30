"""
Demo: L2 Redis Message Bus
Three agents broadcast and consume messages via a simulated Redis backend.
"""

from skills.redis_message_bus import RedisMessageBus, SimulatedRedisBackend


async def main():
    backend = SimulatedRedisBackend()

    # Create three agents sharing the same bus
    alpha = RedisMessageBus("agent-alpha", backend)
    beta = RedisMessageBus("agent-beta", backend)
    gamma = RedisMessageBus("agent-gamma", backend)

    # Register services
    await alpha.register_service("coordinator", ["dispatch"])
    await beta.register_service("analyst", ["trend", "anomaly"])
    await gamma.register_service("reviewer", ["review"])

    # Subscribe to broadcast channel
    await alpha.subscribe("agent:broadcast")
    await beta.subscribe("agent:broadcast")
    await gamma.subscribe("agent:broadcast")

    # Alpha broadcasts config update
    await alpha.publish("agent:broadcast", {"type": "config_update", "threshold": 0.85})

    # Alpha dispatches persistent task
    await alpha.send_to_stream("agent:tasks", {"task_id": "T001", "target": "agent-beta", "action": "analyze"})

    # Beta and Gamma listen
    print("[Beta] Listening for messages...")
    async for msg in beta.listen(timeout=2):
        print(f"  [Beta] Received: {msg}")
        if msg["source"] == "stream":
            await beta.ack_stream_message(msg["id"])
        break

    print("\n[Gamma] Listening for broadcast...")
    async for msg in gamma.listen(timeout=2):
        print(f"  [Gamma] Received: {msg}")
        break

    # Service discovery
    print("\n[Service Discovery]")
    analysts = await alpha.discover_services(capability="anomaly")
    print(f"  Agents with 'anomaly' capability: {analysts}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
