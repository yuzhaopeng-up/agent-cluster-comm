"""
L3 Group Chat Bot Engine
Group chat bot collaboration with reply-tag trap handling.

CRITICAL DESIGN: In group chats, the platform's reply_to feature often fails
because threading models break in multi-participant contexts. This engine
demonstrates the "reply-tag trap" and the safe alternative: plain text + @-mention.
"""

import re
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set


class MessageType(Enum):
    TEXT = "text"
    RICH_CARD = "rich_card"
    REPLY_TAGGED = "reply_tagged"


class DeliveryStatus(Enum):
    DELIVERED = "delivered"
    REPLY_TAG_STRIPPED = "reply_tag_stripped"
    MENTION_LOST = "mention_lost"
    DELIVERED_INTACT = "delivered_intact"


@dataclass
class ChatMessage:
    msg_id: str
    sender_id: str
    sender_name: str
    chat_id: str
    content: str
    msg_type: MessageType
    mentions: List[str] = field(default_factory=list)
    reply_to: Optional[str] = None
    card_data: Optional[dict] = None
    timestamp: float = field(default_factory=time.time)
    delivery_status: DeliveryStatus = DeliveryStatus.DELIVERED
    visible_reply_chain: Optional[str] = None
    original_reply_to_content: Optional[str] = None


@dataclass
class RichCard:
    title: str
    body: str
    actions: List[dict] = field(default_factory=list)
    color: str = "#4A90D9"
    footer: str = ""


@dataclass
class ChatParticipant:
    agent_id: str
    name: str
    is_bot: bool = True
    joined_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


@dataclass
class ChatThread:
    thread_id: str
    root_msg_id: str
    messages: List[ChatMessage] = field(default_factory=list)


class SimulatedChatPlatform:
    """
    In-memory group chat platform.

    Simulates the reply-tag trap: reply_to messages in group chats
    have their threading information stripped at a configurable rate,
    while plain text + @-mention always works.
    """

    REPLY_TAG_FAILURE_RATE = 1.0  # 100% in demo to clearly show the trap

    def __init__(self, reply_failure_rate: float = 1.0):
        self._chats: Dict[str, List[ChatMessage]] = defaultdict(list)
        self._participants: Dict[str, Dict[str, ChatParticipant]] = defaultdict(dict)
        self._threads: Dict[str, ChatThread] = {}
        self._delivery_log: List[dict] = []
        self._reply_failures: List[dict] = []
        self.REPLY_TAG_FAILURE_RATE = reply_failure_rate

    def join_chat(self, chat_id: str, participant: ChatParticipant):
        self._participants[chat_id][participant.agent_id] = participant

    def get_participants(self, chat_id: str) -> List[ChatParticipant]:
        return list(self._participants.get(chat_id, {}).values())

    def _resolve_agent_name(self, chat_id: str, agent_id: str) -> str:
        p = self._participants.get(chat_id, {}).get(agent_id)
        return p.name if p else agent_id

    def _find_message(self, chat_id: str, msg_id: str) -> Optional[ChatMessage]:
        for msg in self._chats.get(chat_id, []):
            if msg.msg_id == msg_id:
                return msg
        return None

    def send_message(self, message: ChatMessage) -> dict:
        if message.msg_type == MessageType.REPLY_TAGGED:
            return self._handle_reply_tagged(message)
        else:
            return self._handle_normal_message(message)

    def _handle_reply_tagged(self, message: ChatMessage) -> dict:
        """
        Handle reply-tagged messages — the trap.

        In group chats, the reply_to threading often breaks because:
        1. The platform strips the reply reference in multi-participant threads
        2. Some clients don't show reply chains in group context
        3. API-level reply_to doesn't propagate to all participants

        This simulates that failure deterministically.
        """
        original = self._find_message(message.chat_id, message.reply_to)
        original_content = original.content if original else "[unknown]"

        # Simulate reply tag getting stripped in group chat
        import hashlib
        trap_key = f"{message.msg_id}:{message.chat_id}"
        trap_value = int(hashlib.md5(trap_key.encode()).hexdigest()[:8], 16)
        fails = (trap_value % 100) < (self.REPLY_TAG_FAILURE_RATE * 100)

        if fails:
            message.delivery_status = DeliveryStatus.REPLY_TAG_STRIPPED
            message.visible_reply_chain = None
            message.original_reply_to_content = original_content
            self._chats[message.chat_id].append(message)
            self._reply_failures.append({
                "msg_id": message.msg_id,
                "chat_id": message.chat_id,
                "intended_reply_to": message.reply_to,
                "original_content_snippet": original_content[:50],
                "failure": "reply_tag_stripped_in_group",
                "recipients_see_reply_chain": False,
            })
            return {
                "status": "partial_delivery",
                "msg_id": message.msg_id,
                "warning": "REPLY_TAG_TRAP: reply_to reference lost in group chat",
                "reply_chain_broken": True,
                "recipients_see_thread": False,
                "original_content_snippet": original_content[:50],
            }
        else:
            message.delivery_status = DeliveryStatus.DELIVERED_INTACT
            message.visible_reply_chain = message.reply_to
            self._chats[message.chat_id].append(message)
            return {
                "status": "delivered",
                "msg_id": message.msg_id,
                "reply_chain_intact": True,
            }

    def _handle_normal_message(self, message: ChatMessage) -> dict:
        message.delivery_status = DeliveryStatus.DELIVERED_INTACT
        self._chats[message.chat_id].append(message)
        participant_ids = list(self._participants.get(message.chat_id, {}).keys())
        notified = [pid for pid in participant_ids if pid != message.sender_id]
        mentioned_notified = [pid for pid in notified if pid in message.mentions]
        return {
            "status": "delivered",
            "msg_id": message.msg_id,
            "notified_count": len(notified),
            "mentioned_count": len(mentioned_notified),
            "msg_type": message.msg_type.value,
        }

    def get_messages(self, chat_id: str, since: float = 0,
                     limit: int = 100) -> List[ChatMessage]:
        msgs = [m for m in self._chats.get(chat_id, [])
                if m.timestamp >= since]
        return msgs[-limit:]

    def get_reply_failures(self) -> List[dict]:
        return list(self._reply_failures)

    def get_chat_stats(self, chat_id: str) -> dict:
        msgs = self._chats.get(chat_id, [])
        by_type = defaultdict(int)
        for m in msgs:
            by_type[m.msg_type.value] += 1
        return {
            "chat_id": chat_id,
            "participant_count": len(self._participants.get(chat_id, {})),
            "total_messages": len(msgs),
            "by_type": dict(by_type),
            "reply_tag_failures": len(self._reply_failures),
        }


class GroupChatBotEngine:
    """Core engine for group chat bot collaboration."""

    def __init__(self, bot_id: str, bot_name: str,
                 platform: SimulatedChatPlatform):
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.platform = platform
        self._handlers: List[Callable] = []
        self._sent: List[ChatMessage] = []
        self._received: List[ChatMessage] = []
        self.platform.join_chat("", ChatParticipant(
            agent_id=bot_id, name=bot_name,
        ))

    def join_chat(self, chat_id: str):
        self.platform.join_chat(chat_id, ChatParticipant(
            agent_id=self.bot_id, name=self.bot_name,
        ))

    def send_text(self, chat_id: str, content: str,
                  mentions: List[str] = None) -> dict:
        msg = ChatMessage(
            msg_id=str(uuid.uuid4())[:8],
            sender_id=self.bot_id,
            sender_name=self.bot_name,
            chat_id=chat_id,
            content=content,
            msg_type=MessageType.TEXT,
            mentions=mentions or [],
        )
        self._sent.append(msg)
        return self.platform.send_message(msg)

    def send_reply_tagged(self, chat_id: str, reply_to_msg_id: str,
                          content: str, mentions: List[str] = None) -> dict:
        """
        Send using the platform's reply_to feature.
        WARNING: This falls into the reply-tag trap in group chats.
        The reply reference is often stripped, breaking the thread.
        """
        msg = ChatMessage(
            msg_id=str(uuid.uuid4())[:8],
            sender_id=self.bot_id,
            sender_name=self.bot_name,
            chat_id=chat_id,
            content=content,
            msg_type=MessageType.REPLY_TAGGED,
            mentions=mentions or [],
            reply_to=reply_to_msg_id,
        )
        self._sent.append(msg)
        return self.platform.send_message(msg)

    def send_safe_reply(self, chat_id: str, target_agent_id: str,
                        content: str) -> dict:
        """
        Send using plain text + @-mention — the reliable group chat pattern.
        This avoids the reply-tag trap entirely.
        """
        safe_content = f"@{target_agent_id} {content}"
        return self.send_text(chat_id, safe_content, mentions=[target_agent_id])

    def send_rich_card(self, chat_id: str, card: RichCard,
                       mentions: List[str] = None) -> dict:
        msg = ChatMessage(
            msg_id=str(uuid.uuid4())[:8],
            sender_id=self.bot_id,
            sender_name=self.bot_name,
            chat_id=chat_id,
            content=card.title,
            msg_type=MessageType.RICH_CARD,
            mentions=mentions or [],
            card_data={
                "title": card.title,
                "body": card.body,
                "actions": card.actions,
                "color": card.color,
                "footer": card.footer,
            },
        )
        self._sent.append(msg)
        return self.platform.send_message(msg)

    def read_messages(self, chat_id: str, since: float = 0) -> List[ChatMessage]:
        messages = self.platform.get_messages(chat_id, since)
        for msg in messages:
            if msg.sender_id != self.bot_id:
                already = any(r.msg_id == msg.msg_id for r in self._received)
                if not already:
                    is_relevant = (self.bot_id in msg.mentions
                                   or not msg.mentions)
                    if is_relevant:
                        self._received.append(msg)
                        for handler in self._handlers:
                            try:
                                handler(msg)
                            except Exception:
                                pass
        return messages

    def on_message(self, handler: Callable):
        self._handlers.append(handler)

    def parse_mentions(self, content: str) -> List[str]:
        return re.findall(r"@(\w+)", content)

    def get_sent(self) -> List[ChatMessage]:
        return list(self._sent)

    def get_received(self) -> List[ChatMessage]:
        return list(self._received)

    def get_info(self) -> dict:
        return {
            "bot_id": self.bot_id,
            "bot_name": self.bot_name,
            "sent_count": len(self._sent),
            "received_count": len(self._received),
        }
