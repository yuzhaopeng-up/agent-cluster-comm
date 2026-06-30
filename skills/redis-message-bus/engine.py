"""
L2 Redis Message Bus Engine
Async Pub/Sub + Stream message bus with simulated Redis backend.
Supports service discovery, heartbeat, consumer groups.
"""

import json
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple


@dataclass
class PubSubMessage:
    topic: str
    payload: dict
    sender_id: str
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)


@dataclass
class StreamEntry:
    entry_id: str
    stream: str
    payload: dict
    sender_id: str
    timestamp: float
    acknowledged: bool = False


@dataclass
class ConsumerGroupState:
    group_name: str
    stream: str
    consumers: Set[str]
    pending: Dict[str, StreamEntry]
    delivered: Dict[str, str]


@dataclass
class ServiceRegistration:
    service_name: str
    agent_id: str
    metadata: dict
    registered_at: float
    last_heartbeat: float
    status: str = "active"


class SimulatedRedis:
    """In-memory simulation of Redis with Streams and key-value store."""

    def __init__(self):
        self._kv: Dict[str, object] = {}
        self._streams: Dict[str, List[StreamEntry]] = defaultdict(list)
        self._consumer_groups: Dict[str, Dict[str, ConsumerGroupState]] = defaultdict(dict)
        self._stream_seq: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._expiry: Dict[str, float] = {}

    def set(self, key: str, value: object, ttl: float = None):
        with self._lock:
            self._kv[key] = value
            if ttl:
                self._expiry[key] = time.time() + ttl

    def get(self, key: str) -> Optional[object]:
        with self._lock:
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._kv[key]
                del self._expiry[key]
                return None
            return self._kv.get(key)

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._kv
            self._kv.pop(key, None)
            self._expiry.pop(key, None)
            return existed

    def keys(self, pattern: str = None) -> List[str]:
        with self._lock:
            all_keys = list(self._kv.keys())
            if pattern and pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k for k in all_keys if k.startswith(prefix)]
            return all_keys

    def xadd(self, stream: str, fields: dict) -> str:
        with self._lock:
            self._stream_seq[stream] += 1
            ts_ms = int(time.time() * 1000)
            entry_id = f"{ts_ms}-{self._stream_seq[stream]}"
            entry = StreamEntry(
                entry_id=entry_id,
                stream=stream,
                payload=fields,
                sender_id=fields.get("_sender_id", ""),
                timestamp=time.time(),
            )
            self._streams[stream].append(entry)
            return entry_id

    def xrange(self, stream: str, count: int = 10) -> List[StreamEntry]:
        with self._lock:
            return list(self._streams.get(stream, [])[:count])

    def xlen(self, stream: str) -> int:
        with self._lock:
            return len(self._streams.get(stream, []))

    def xcreate_group(self, stream: str, group: str) -> bool:
        with self._lock:
            if group in self._consumer_groups.get(stream, {}):
                return False
            self._consumer_groups[stream][group] = ConsumerGroupState(
                group_name=group, stream=stream,
                consumers=set(), pending={}, delivered={},
            )
            return True

    def xreadgroup(self, stream: str, group: str, consumer: str,
                   count: int = 1) -> List[StreamEntry]:
        with self._lock:
            cg = self._consumer_groups.get(stream, {}).get(group)
            if cg is None:
                return []
            cg.consumers.add(consumer)
            entries = self._streams.get(stream, [])[:count]
            for e in entries:
                if e.entry_id not in cg.pending:
                    cg.pending[e.entry_id] = e
                    cg.delivered[e.entry_id] = consumer
            return list(entries[:count])

    def xack(self, stream: str, group: str, entry_id: str) -> bool:
        with self._lock:
            cg = self._consumer_groups.get(stream, {}).get(group)
            if cg and entry_id in cg.pending:
                cg.pending[entry_id].acknowledged = True
                del cg.pending[entry_id]
                return True
            return False

    def xpending(self, stream: str, group: str) -> dict:
        with self._lock:
            cg = self._consumer_groups.get(stream, {}).get(group)
            if cg is None:
                return {"pending_count": 0, "consumers": {}}
            by_consumer = defaultdict(int)
            for eid, c in cg.delivered.items():
                if eid in cg.pending:
                    by_consumer[c] += 1
            return {
                "pending_count": len(cg.pending),
                "consumers": dict(by_consumer),
            }


class SimulatedPubSub:
    """In-memory Pub/Sub hub with topic-based routing."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._pattern_subscribers: List[Tuple[str, Callable]] = []
        self._lock = threading.Lock()
        self._message_count: Dict[str, int] = defaultdict(int)

    def publish(self, topic: str, message: PubSubMessage) -> int:
        delivered = 0
        with self._lock:
            self._message_count[topic] += 1
            for callback in self._subscribers.get(topic, []):
                try:
                    callback(message)
                    delivered += 1
                except Exception:
                    pass
            for pattern, callback in self._pattern_subscribers:
                if topic.startswith(pattern.rstrip("*")):
                    try:
                        callback(message)
                        delivered += 1
                    except Exception:
                        pass
        return delivered

    def subscribe(self, topic: str, callback: Callable):
        with self._lock:
            self._subscribers[topic].append(callback)

    def psubscribe(self, pattern: str, callback: Callable):
        with self._lock:
            self._pattern_subscribers.append((pattern, callback))

    def unsubscribe(self, topic: str, callback: Callable):
        with self._lock:
            subs = self._subscribers.get(topic, [])
            if callback in subs:
                subs.remove(callback)

    def get_topic_stats(self) -> Dict[str, int]:
        return dict(self._message_count)


class MessageBusEngine:
    """Core engine for async Pub/Sub + Stream message bus."""

    HEARTBEAT_INTERVAL = 5.0
    HEARTBEAT_TIMEOUT = 15.0

    def __init__(self, agent_id: str, redis: SimulatedRedis,
                 pubsub: SimulatedPubSub):
        self.agent_id = agent_id
        self.redis = redis
        self.pubsub = pubsub
        self._subscriptions: Dict[str, Callable] = {}
        self._received_broadcasts: List[PubSubMessage] = []
        self._services: Dict[str, ServiceRegistration] = {}
        self._last_heartbeat = time.time()

    def broadcast(self, topic: str, payload: dict) -> str:
        msg = PubSubMessage(
            topic=topic, payload=payload,
            sender_id=self.agent_id,
        )
        self.pubsub.publish(topic, msg)
        stream_fields = {
            "payload": json.dumps(payload),
            "_sender_id": self.agent_id,
            "msg_id": msg.msg_id,
        }
        self.redis.xadd(topic, stream_fields)
        return msg.msg_id

    def subscribe(self, topic: str, callback: Callable = None):
        if callback is None:
            callback = self._default_broadcast_handler
        self._subscriptions[topic] = callback
        self.pubsub.subscribe(topic, callback)

    def _default_broadcast_handler(self, msg: PubSubMessage):
        if msg.sender_id != self.agent_id:
            self._received_broadcasts.append(msg)

    def consume_stream(self, stream: str, group: str = "workers",
                       count: int = 10) -> List[StreamEntry]:
        if self.redis.xlen(stream) > 0:
            self.redis.xcreate_group(stream, group)
        entries = self.redis.xreadgroup(stream, group, self.agent_id, count)
        for e in entries:
            self.redis.xack(stream, group, e.entry_id)
        return entries

    def get_stream_history(self, stream: str, count: int = 20) -> List[StreamEntry]:
        return self.redis.xrange(stream, count)

    def register_service(self, service_name: str, metadata: dict = None):
        reg = ServiceRegistration(
            service_name=service_name,
            agent_id=self.agent_id,
            metadata=metadata or {},
            registered_at=time.time(),
            last_heartbeat=time.time(),
        )
        key = f"svc:{service_name}:{self.agent_id}"
        self.redis.set(key, reg, ttl=self.HEARTBEAT_TIMEOUT * 2)
        self._services[service_name] = reg

    def send_heartbeat(self):
        self._last_heartbeat = time.time()
        for svc_name, reg in self._services.items():
            reg.last_heartbeat = time.time()
            key = f"svc:{svc_name}:{self.agent_id}"
            self.redis.set(key, reg, ttl=self.HEARTBEAT_TIMEOUT * 2)

    def discover_service(self, service_name: str) -> List[dict]:
        results = []
        prefix = f"svc:{service_name}:"
        for key in self.redis.keys(f"{prefix}*"):
            val = self.redis.get(key)
            if val and isinstance(val, ServiceRegistration):
                age = time.time() - val.last_heartbeat
                alive = age < self.HEARTBEAT_TIMEOUT
                results.append({
                    "service_name": val.service_name,
                    "agent_id": val.agent_id,
                    "metadata": val.metadata,
                    "last_heartbeat_age": f"{age:.1f}s",
                    "alive": alive,
                })
        return results

    def get_received_broadcasts(self) -> List[PubSubMessage]:
        return list(self._received_broadcasts)

    def get_info(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "subscriptions": list(self._subscriptions.keys()),
            "services": list(self._services.keys()),
            "received_count": len(self._received_broadcasts),
            "last_heartbeat": self._last_heartbeat,
        }
