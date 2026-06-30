"""
Demo: L4 GitHub Async Handoff
Agent A hands off a task to Agent B via simulated GitHub Issues.
"""

from skills.github_async_handoff import HandoffClient, InMemoryGitHubBackend


def main():
    backend = InMemoryGitHubBackend()

    agent_a = HandoffClient(repo="demo-org/workspace", backend=backend)
    agent_b = HandoffClient(repo="demo-org/workspace", backend=backend)

    # Agent A creates handoff
    issue = agent_a.create_handoff(
        title="[Handoff] Analyze Q2 revenue",
        body="Dataset prepared in /data/q2_revenue.csv",
        labels=["handoff", "data_analysis"],
    )
    print(f"[Agent A] Created Issue #{issue['number']}: {issue['title']}")

    # Agent A pushes artifact
    agent_a.push_code(
        branch="handoff/agent-alpha",
        files={"data/q2_revenue.csv": "month,revenue\n2026-04,1200000\n2026-05,1350000\n2026-06,1420000"},
        commit_message="Add Q2 revenue dataset",
    )
    print("[Agent A] Pushed artifact to handoff/agent-alpha")

    # Agent B comes online, claims and completes
    agent_b.claim_handoff(issue["number"], assignee="agent-beta")
    print(f"[Agent B] Claimed Issue #{issue['number']}")

    # Agent B pulls artifact
    artifacts = agent_b.pull_code(branch="handoff/agent-alpha", path="data/")
    print(f"[Agent B] Pulled artifacts: {list(artifacts.keys())}")

    # Agent B completes
    agent_b.complete_handoff(
        issue_number=issue["number"],
        summary="Analysis complete. Q2 revenue grew 18.3% QoQ.",
    )
    print(f"[Agent B] Completed Issue #{issue['number']}")

    # Check state
    print(f"\n[Issue State] {agent_a.is_ready(issue['number'])}")
    print(f"[Pending Handoffs] {len(agent_a.list_pending())}")


if __name__ == "__main__":
    main()
