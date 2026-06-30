"""
Demo: L3 Group Chat Bot
Demonstrate the reply-tag trap and correct bot-to-bot collaboration.
"""

from skills.group_chat_bot import GroupChatBotEngine, SimulatedChatPlatform


async def main():
    platform = SimulatedChatPlatform()

    # Create three bots
    bot_a = GroupChatBotEngine("bot-alpha", platform)
    bot_b = GroupChatBotEngine("bot-beta", platform)
    bot_c = GroupChatBotEngine("bot-gamma", platform)

    # User @bot-alpha in group chat
    await platform.inject_message(
        sender="user-alice",
        content="@bot-alpha Please analyze Acme Corp risk",
        mentions=["bot-alpha"],
    )

    # Bot A processes and delegates to Bot B
    events = await bot_a.poll_events()
    for event in events:
        if event.is_mention:
            await bot_a.send_group_message(
                chat_id="group-001",
                content="Starting risk analysis. @bot-beta please run the query.",
                mentions=["bot-beta"],
            )
            # Simulate delegation
            await bot_b.send_group_message(
                chat_id="group-001",
                content="Query executed. Risk score: 72/100. @bot-gamma please review.",
                mentions=["bot-gamma"],
            )
            await bot_c.send_group_message(
                chat_id="group-001",
                content="Review passed. @user-alice report is ready.",
                mentions=["user-alice"],
            )

    # Demonstrate reply-tag trap
    print("\n[Reply-Tag Trap Demo]")
    result_with_reply_tag = await bot_a.send_group_message(
        chat_id="group-001",
        content="[[reply_to_current]] This message will be suppressed",
        use_reply_tag=True,
    )
    print(f"  With reply_tag: visible_users={result_with_reply_tag['visible_users']} (TRAP!)")

    result_plain = await bot_a.send_group_message(
        chat_id="group-001",
        content="@user-alice This message is visible to everyone.",
        mentions=["user-alice"],
    )
    print(f"  Plain text + @: visible_users={result_plain['visible_users']} (CORRECT)")

    # Print chat history
    print("\n[Group Chat Thread]")
    for msg in platform.get_chat_history("group-001"):
        print(f"  {msg['sender']}: {msg['content']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
