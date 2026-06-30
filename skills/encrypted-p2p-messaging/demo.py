"""
Demo: L1 Encrypted P2P Messaging
Two simulated agents exchange encrypted messages through a relay server.
"""

from skills.encrypted_p2p_messaging import P2PMessagingEngine, SimulatedRelayServer


def main():
    relay = SimulatedRelayServer()

    # Create two agents
    alice = P2PMessagingEngine("agent-alpha", relay)
    bob = P2PMessagingEngine("agent-beta", relay)

    # Establish friendship
    alice.send_friend_request("agent-beta")
    bob.accept_pending_requests()

    # Alice sends encrypted message to Bob
    msg_id = alice.send("agent-beta", '{"task": "credit_check", "payload": {"company": "Acme Corp"}}')
    print(f"[Alice] Sent encrypted message: {msg_id}")

    # Bob polls and decrypts
    messages = bob.poll()
    for msg in messages:
        print(f"[Bob] Decrypted from {msg.sender_id}: {msg.plaintext}")

    # Relay cannot read plaintext (only sees ciphertext)
    print(f"\n[Relay Stats] {relay.get_stats()}")
    print("[Proof] Relay stored encrypted blobs only — no plaintext visible.")


if __name__ == "__main__":
    main()
