"""
L1 Encrypted P2P Messaging Engine
End-to-end encrypted P2P messaging via simulated relay server.
Uses cryptography.fernet for E2E encryption with simulated DH key exchange.
"""

import base64
import hashlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


@dataclass
class FriendRecord:
    agent_id: str
    public_key_b64: str
    shared_secret: bytes = field(default=None, repr=False)
    added_at: float = 0.0
    verified: bool = False


@dataclass
class OutboundMessage:
    msg_id: str
    recipient_id: str
    plaintext: str
    sent_at: float
    status: str = "sent"


@dataclass
class InboundMessage:
    msg_id: str
    sender_id: str
    plaintext: str
    received_at: float
    verified: bool


@dataclass
class RelayEnvelope:
    msg_id: str
    sender_id: str
    recipient_id: str
    ciphertext: bytes
    nonce_tag: str
    timestamp: float


@dataclass
class FriendRequest:
    request_id: str
    from_agent: str
    to_agent: str
    public_key_b64: str
    timestamp: float
    status: str = "pending"


class KeyExchange:
    """Simulated Diffie-Hellman key exchange using PBKDF2."""

    @staticmethod
    def generate_agent_keypair(agent_id: str, passphrase: str = None) -> Tuple[bytes, str]:
        if passphrase is None:
            passphrase = f"{agent_id}:{uuid.uuid4()}"
        salt = hashlib.sha256(agent_id.encode()).digest()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        private_key = kdf.derive(passphrase.encode())
        public_key_b64 = base64.b64encode(private_key[:16]).decode()
        return private_key, public_key_b64

    @staticmethod
    def derive_shared_secret(my_private: bytes, peer_public_b64: str) -> bytes:
        peer_bytes = base64.b64decode(peer_public_b64)
        combined = my_private[:16] + peer_bytes
        salt = hashlib.sha256(combined).digest()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
        )
        return kdf.derive(combined)

    @staticmethod
    def shared_secret_to_fernet_key(shared_secret: bytes) -> bytes:
        return base64.urlsafe_b64encode(shared_secret)


class SimulatedRelayServer:
    """In-memory relay server that queues encrypted envelopes per recipient."""

    def __init__(self):
        self._queues: Dict[str, List[RelayEnvelope]] = defaultdict(list)
        self._agents: Dict[str, str] = {}
        self._friend_requests: List[FriendRequest] = []
        self._audit_log: List[dict] = []
        self._total_envelopes = 0
        self._total_bytes = 0

    def register_agent(self, agent_id: str, public_key_b64: str):
        self._agents[agent_id] = public_key_b64
        self._audit_log.append({
            "event": "register", "agent_id": agent_id,
            "timestamp": time.time(),
        })

    def get_public_key(self, agent_id: str) -> Optional[str]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[str]:
        return list(self._agents.keys())

    def submit_friend_request(self, request: FriendRequest):
        self._friend_requests.append(request)
        self._audit_log.append({
            "event": "friend_request", "from": request.from_agent,
            "to": request.to_agent, "timestamp": time.time(),
        })

    def poll_friend_requests(self, agent_id: str) -> List[FriendRequest]:
        return [r for r in self._friend_requests
                if r.to_agent == agent_id and r.status == "pending"]

    def accept_friend_request(self, request_id: str):
        for r in self._friend_requests:
            if r.request_id == request_id:
                r.status = "accepted"
                break

    def deliver(self, envelope: RelayEnvelope):
        self._queues[envelope.recipient_id].append(envelope)
        self._total_envelopes += 1
        self._total_bytes += len(envelope.ciphertext)
        self._audit_log.append({
            "event": "deliver", "msg_id": envelope.msg_id,
            "from": envelope.sender_id, "to": envelope.recipient_id,
            "size": len(envelope.ciphertext), "timestamp": time.time(),
        })

    def poll(self, agent_id: str, limit: int = 20) -> List[RelayEnvelope]:
        messages = self._queues[agent_id][:limit]
        self._queues[agent_id] = self._queues[agent_id][limit:]
        return messages

    def peek(self, agent_id: str, limit: int = 20) -> List[RelayEnvelope]:
        return self._queues[agent_id][:limit]

    def get_stats(self) -> dict:
        return {
            "registered_agents": len(self._agents),
            "total_envelopes_delivered": self._total_envelopes,
            "total_bytes_transferred": self._total_bytes,
            "pending_messages": sum(len(q) for q in self._queues.values()),
            "friend_requests": len(self._friend_requests),
        }


class P2PMessagingEngine:
    """Core engine for encrypted P2P messaging between agents."""

    def __init__(self, agent_id: str, relay: SimulatedRelayServer, passphrase: str = None):
        self.agent_id = agent_id
        self.relay = relay
        self._private_key, self._public_key_b64 = KeyExchange.generate_agent_keypair(
            agent_id, passphrase
        )
        self._friends: Dict[str, FriendRecord] = {}
        self._sent: List[OutboundMessage] = []
        self._received: List[InboundMessage] = []
        self.relay.register_agent(agent_id, self._public_key_b64)

    def send_friend_request(self, friend_id: str) -> str:
        request = FriendRequest(
            request_id=str(uuid.uuid4())[:8],
            from_agent=self.agent_id,
            to_agent=friend_id,
            public_key_b64=self._public_key_b64,
            timestamp=time.time(),
        )
        self.relay.submit_friend_request(request)
        return request.request_id

    def accept_pending_requests(self) -> List[str]:
        accepted = []
        for req in self.relay.poll_friend_requests(self.agent_id):
            self.relay.accept_friend_request(req.request_id)
            self._add_friend_from_request(req)
            accepted.append(req.from_agent)
        return accepted

    def _add_friend_from_request(self, req: FriendRequest):
        shared = KeyExchange.derive_shared_secret(self._private_key, req.public_key_b64)
        self._friends[req.from_agent] = FriendRecord(
            agent_id=req.from_agent,
            public_key_b64=req.public_key_b64,
            shared_secret=shared,
            added_at=time.time(),
            verified=True,
        )

    def add_friend(self, friend_id: str) -> bool:
        public_key = self.relay.get_public_key(friend_id)
        if public_key is None:
            return False
        shared = KeyExchange.derive_shared_secret(self._private_key, public_key)
        self._friends[friend_id] = FriendRecord(
            agent_id=friend_id,
            public_key_b64=public_key,
            shared_secret=shared,
            added_at=time.time(),
            verified=True,
        )
        return True

    def remove_friend(self, friend_id: str) -> bool:
        if friend_id in self._friends:
            del self._friends[friend_id]
            return True
        return False

    def list_friends(self) -> List[str]:
        return list(self._friends.keys())

    def encrypt_for(self, friend_id: str, plaintext: str) -> Optional[Tuple[bytes, str]]:
        friend = self._friends.get(friend_id)
        if friend is None:
            return None
        fernet_key = KeyExchange.shared_secret_to_fernet_key(friend.shared_secret)
        fernet = Fernet(fernet_key)
        ciphertext = fernet.encrypt(plaintext.encode("utf-8"))
        nonce_tag = hashlib.sha256(ciphertext[:16]).hexdigest()[:8]
        return ciphertext, nonce_tag

    def decrypt_from(self, friend_id: str, ciphertext: bytes) -> Optional[str]:
        friend = self._friends.get(friend_id)
        if friend is None:
            return None
        fernet_key = KeyExchange.shared_secret_to_fernet_key(friend.shared_secret)
        fernet = Fernet(fernet_key)
        try:
            return fernet.decrypt(ciphertext).decode("utf-8")
        except Exception:
            return None

    def send(self, recipient_id: str, plaintext: str) -> Optional[str]:
        result = self.encrypt_for(recipient_id, plaintext)
        if result is None:
            return None
        ciphertext, nonce_tag = result
        msg_id = str(uuid.uuid4())[:8]
        envelope = RelayEnvelope(
            msg_id=msg_id,
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            ciphertext=ciphertext,
            nonce_tag=nonce_tag,
            timestamp=time.time(),
        )
        self.relay.deliver(envelope)
        self._sent.append(OutboundMessage(
            msg_id=msg_id, recipient_id=recipient_id,
            plaintext=plaintext, sent_at=time.time(),
        ))
        return msg_id

    def poll(self, limit: int = 20) -> List[InboundMessage]:
        envelopes = self.relay.poll(self.agent_id, limit)
        decrypted = []
        for env in envelopes:
            plaintext = self.decrypt_from(env.sender_id, env.ciphertext)
            if plaintext is not None:
                msg = InboundMessage(
                    msg_id=env.msg_id, sender_id=env.sender_id,
                    plaintext=plaintext, received_at=time.time(),
                    verified=True,
                )
                self._received.append(msg)
                decrypted.append(msg)
            else:
                decrypted.append(InboundMessage(
                    msg_id=env.msg_id, sender_id=env.sender_id,
                    plaintext="[DECRYPTION_FAILED]",
                    received_at=time.time(), verified=False,
                ))
        return decrypted

    def get_sent_history(self) -> List[OutboundMessage]:
        return list(self._sent)

    def get_received_history(self) -> List[InboundMessage]:
        return list(self._received)

    def get_info(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "public_key": self._public_key_b64,
            "friends": self.list_friends(),
            "sent_count": len(self._sent),
            "received_count": len(self._received),
        }
