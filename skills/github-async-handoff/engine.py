"""
L4 GitHub Async Handoff Engine
Decentralized async task handoff via GitHub Issues (simulated).
State machine: CREATED -> CLAIMED -> COMPLETED -> CLOSED.
Branch-per-agent isolation, rate-limit cache, handoff protocol.
"""

import hashlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple


class IssueState(Enum):
    CREATED = "created"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    CLOSED = "closed"


class TransitionError(Exception):
    pass


@dataclass
class IssueComment:
    comment_id: str
    issue_number: int
    author: str
    body: str
    timestamp: float
    is_system: bool = False


@dataclass
class Issue:
    number: int
    title: str
    body: str
    author: str
    assignee: Optional[str]
    labels: List[str]
    state: IssueState
    branch: Optional[str]
    created_at: float
    updated_at: float
    closed_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class BranchRecord:
    branch_name: str
    owner_agent: str
    issue_number: int
    created_at: float
    last_commit: Optional[str] = None
    status: str = "active"


@dataclass
class RateLimitEntry:
    window_start: float
    request_count: int
    window_seconds: float


VALID_TRANSITIONS = {
    IssueState.CREATED: {IssueState.CLAIMED, IssueState.CLOSED},
    IssueState.CLAIMED: {IssueState.COMPLETED, IssueState.CREATED},
    IssueState.COMPLETED: {IssueState.CLOSED},
    IssueState.CLOSED: set(),
}


class SimulatedGitHub:
    """In-memory Issue tracker simulating GitHub Issues API."""

    def __init__(self, repo_name: str = "agent-cluster/tasks"):
        self.repo_name = repo_name
        self._issues: Dict[int, Issue] = {}
        self._comments: Dict[int, List[IssueComment]] = defaultdict(list)
        self._branches: Dict[str, BranchRecord] = {}
        self._next_number = 1
        self._rate_limits: Dict[str, RateLimitEntry] = {}
        self._audit_log: List[dict] = []

    def create_issue(self, title: str, body: str, author: str,
                     labels: List[str] = None,
                     metadata: dict = None) -> Issue:
        number = self._next_number
        self._next_number += 1
        issue = Issue(
            number=number, title=title, body=body, author=author,
            assignee=None, labels=labels or [], state=IssueState.CREATED,
            branch=None, created_at=time.time(), updated_at=time.time(),
            metadata=metadata or {},
        )
        self._issues[number] = issue
        self._audit_log.append({
            "action": "create_issue", "issue_number": number,
            "author": author, "timestamp": time.time(),
        })
        return issue

    def get_issue(self, number: int) -> Optional[Issue]:
        return self._issues.get(number)

    def list_issues(self, state: IssueState = None,
                    labels: List[str] = None,
                    assignee: str = None) -> List[Issue]:
        results = list(self._issues.values())
        if state:
            results = [i for i in results if i.state == state]
        if labels:
            results = [i for i in results
                       if any(l in i.labels for l in labels)]
        if assignee:
            results = [i for i in results if i.assignee == assignee]
        return results

    def update_issue_state(self, number: int, new_state: IssueState,
                           actor: str) -> Issue:
        issue = self._issues.get(number)
        if issue is None:
            raise ValueError(f"Issue #{number} not found")
        if new_state not in VALID_TRANSITIONS.get(issue.state, set()):
            raise TransitionError(
                f"Invalid transition: {issue.state.value} -> {new_state.value}"
            )
        old_state = issue.state
        issue.state = new_state
        issue.updated_at = time.time()
        if new_state == IssueState.CLOSED:
            issue.closed_at = time.time()
        self._audit_log.append({
            "action": "state_change", "issue_number": number,
            "from": old_state.value, "to": new_state.value,
            "actor": actor, "timestamp": time.time(),
        })
        return issue

    def assign_issue(self, number: int, assignee: str,
                     actor: str) -> Issue:
        issue = self._issues.get(number)
        if issue is None:
            raise ValueError(f"Issue #{number} not found")
        issue.assignee = assignee
        issue.updated_at = time.time()
        self._add_comment(number, actor,
                          f"Assigned to @{assignee}", is_system=True)
        return issue

    def add_label(self, number: int, label: str, actor: str):
        issue = self._issues.get(number)
        if issue and label not in issue.labels:
            issue.labels.append(label)
            issue.updated_at = time.time()

    def remove_label(self, number: int, label: str, actor: str):
        issue = self._issues.get(number)
        if issue and label in issue.labels:
            issue.labels.remove(label)
            issue.updated_at = time.time()

    def _add_comment(self, number: int, author: str, body: str,
                     is_system: bool = False) -> IssueComment:
        comment = IssueComment(
            comment_id=str(uuid.uuid4())[:8],
            issue_number=number, author=author, body=body,
            timestamp=time.time(), is_system=is_system,
        )
        self._comments[number].append(comment)
        return comment

    def add_comment(self, number: int, author: str, body: str) -> IssueComment:
        return self._add_comment(number, author, body)

    def get_comments(self, number: int) -> List[IssueComment]:
        return list(self._comments.get(number, []))

    def create_branch(self, branch_name: str, owner_agent: str,
                      issue_number: int) -> BranchRecord:
        record = BranchRecord(
            branch_name=branch_name, owner_agent=owner_agent,
            issue_number=issue_number, created_at=time.time(),
            last_commit=None, status="active",
        )
        self._branches[branch_name] = record
        self._audit_log.append({
            "action": "create_branch", "branch": branch_name,
            "owner": owner_agent, "issue": issue_number,
            "timestamp": time.time(),
        })
        return record

    def get_branch(self, branch_name: str) -> Optional[BranchRecord]:
        return self._branches.get(branch_name)

    def list_branches(self, owner: str = None) -> List[BranchRecord]:
        branches = list(self._branches.values())
        if owner:
            branches = [b for b in branches if b.owner_agent == owner]
        return branches

    def commit_to_branch(self, branch_name: str,
                         commit_msg: str) -> Optional[str]:
        record = self._branches.get(branch_name)
        if record is None:
            return None
        commit_hash = hashlib.sha256(
            f"{branch_name}:{commit_msg}:{time.time()}".encode()
        ).hexdigest()[:8]
        record.last_commit = commit_hash
        return commit_hash

    def check_rate_limit(self, agent_id: str,
                         max_per_window: int = 30,
                         window_seconds: float = 60.0) -> bool:
        now = time.time()
        entry = self._rate_limits.get(agent_id)
        if entry is None or (now - entry.window_start) > window_seconds:
            self._rate_limits[agent_id] = RateLimitEntry(
                window_start=now, request_count=1,
                window_seconds=window_seconds,
            )
            return True
        if entry.request_count >= max_per_window:
            return False
        entry.request_count += 1
        return True

    def get_rate_limit_status(self, agent_id: str) -> dict:
        entry = self._rate_limits.get(agent_id)
        if entry is None:
            return {"remaining": 30, "reset_in": 0}
        remaining = max(0, 30 - entry.request_count)
        reset_in = max(0, entry.window_seconds - (time.time() - entry.window_start))
        return {"remaining": remaining, "reset_in": f"{reset_in:.0f}s"}

    def get_repo_stats(self) -> dict:
        by_state = defaultdict(int)
        for issue in self._issues.values():
            by_state[issue.state.value] += 1
        return {
            "repo": self.repo_name,
            "total_issues": len(self._issues),
            "by_state": dict(by_state),
            "total_branches": len(self._branches),
            "total_comments": sum(len(c) for c in self._comments.values()),
        }


class GitHubHandoffEngine:
    """Core engine for decentralized async task handoff via GitHub Issues."""

    def __init__(self, agent_id: str, github: SimulatedGitHub):
        self.agent_id = agent_id
        self.github = github
        self._created_issues: List[int] = []
        self._claimed_issues: List[int] = []
        self._completed_issues: List[int] = []
        self._branch_prefix = f"agent/{agent_id}"

    def create_task(self, title: str, body: str,
                    labels: List[str] = None,
                    metadata: dict = None) -> Issue:
        if not self.github.check_rate_limit(self.agent_id):
            raise RuntimeError("Rate limit exceeded")
        issue = self.github.create_issue(
            title=title, body=body, author=self.agent_id,
            labels=labels or ["task"], metadata=metadata or {},
        )
        self._created_issues.append(issue.number)
        self.github.add_comment(
            issue.number, self.agent_id,
            f"Task created by {self.agent_id}. Awaiting claim.",
        )
        return issue

    def claim_task(self, issue_number: int) -> Issue:
        if not self.github.check_rate_limit(self.agent_id):
            raise RuntimeError("Rate limit exceeded")
        issue = self.github.get_issue(issue_number)
        if issue is None:
            raise ValueError(f"Issue #{issue_number} not found")
        self.github.update_issue_state(
            issue_number, IssueState.CLAIMED, self.agent_id)
        self.github.assign_issue(issue_number, self.agent_id, self.agent_id)
        branch_name = f"{self._branch_prefix}/issue-{issue_number}"
        self.github.create_branch(branch_name, self.agent_id, issue_number)
        issue.branch = branch_name
        self.github.add_comment(
            issue_number, self.agent_id,
            f"Claimed by {self.agent_id}. Working on branch `{branch_name}`.",
        )
        self._claimed_issues.append(issue_number)
        return issue

    def complete_task(self, issue_number: int,
                      result_summary: str = "") -> Issue:
        if not self.github.check_rate_limit(self.agent_id):
            raise RuntimeError("Rate limit exceeded")
        issue = self.github.get_issue(issue_number)
        if issue is None:
            raise ValueError(f"Issue #{issue_number} not found")
        if issue.assignee != self.agent_id:
            raise PermissionError(
                f"Only assignee can complete. Assigned to {issue.assignee}")
        self.github.update_issue_state(
            issue_number, IssueState.COMPLETED, self.agent_id)
        if issue.branch:
            commit = self.github.commit_to_branch(
                issue.branch, f"Complete task #{issue_number}")
        self.github.add_comment(
            issue_number, self.agent_id,
            f"Task completed. {result_summary}",
        )
        self._completed_issues.append(issue_number)
        return issue

    def close_task(self, issue_number: int) -> Issue:
        if not self.github.check_rate_limit(self.agent_id):
            raise RuntimeError("Rate limit exceeded")
        issue = self.github.get_issue(issue_number)
        if issue is None:
            raise ValueError(f"Issue #{issue_number} not found")
        self.github.update_issue_state(
            issue_number, IssueState.CLOSED, self.agent_id)
        self.github.add_comment(
            issue_number, self.agent_id,
            f"Closed by {self.agent_id}.",
        )
        return issue

    def handoff_task(self, issue_number: int,
                     target_agent: str,
                     reason: str = "") -> Issue:
        """
        Hand off a claimed task to another agent.
        Unclaims the current assignee, reverts to CREATED state,
        and adds a handoff comment for the target agent.
        """
        if not self.github.check_rate_limit(self.agent_id):
            raise RuntimeError("Rate limit exceeded")
        issue = self.github.get_issue(issue_number)
        if issue is None:
            raise ValueError(f"Issue #{issue_number} not found")
        if issue.assignee != self.agent_id:
            raise PermissionError("Only current assignee can hand off")
        self.github.update_issue_state(
            issue_number, IssueState.CREATED, self.agent_id)
        old_assignee = issue.assignee
        issue.assignee = None
        issue.branch = None
        self.github.add_label(issue_number, "handoff", self.agent_id)
        self.github.add_label(issue_number, f"for:{target_agent}", self.agent_id)
        self.github.add_comment(
            issue_number, self.agent_id,
            f"Handoff from {old_assignee} to @{target_agent}. "
            f"Reason: {reason or 'N/A'}",
        )
        return issue

    def find_pending_handoffs(self) -> List[Issue]:
        issues = self.github.list_issues(
            state=IssueState.CREATED,
            labels=[f"for:{self.agent_id}"],
        )
        return issues

    def find_available_tasks(self) -> List[Issue]:
        return self.github.list_issues(state=IssueState.CREATED)

    def get_issue_detail(self, issue_number: int) -> Optional[dict]:
        issue = self.github.get_issue(issue_number)
        if issue is None:
            return None
        comments = self.github.get_comments(issue_number)
        branch = (self.github.get_branch(issue.branch)
                  if issue.branch else None)
        return {
            "issue": {
                "number": issue.number,
                "title": issue.title,
                "state": issue.state.value,
                "assignee": issue.assignee,
                "labels": issue.labels,
                "branch": issue.branch,
            },
            "comments": [
                {
                    "author": c.author, "body": c.body,
                    "timestamp": c.timestamp, "system": c.is_system,
                }
                for c in comments
            ],
            "branch_record": {
                "owner": branch.owner_agent,
                "last_commit": branch.last_commit,
                "status": branch.status,
            } if branch else None,
            "rate_limit": self.github.get_rate_limit_status(self.agent_id),
        }

    def get_info(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "created": len(self._created_issues),
            "claimed": len(self._claimed_issues),
            "completed": len(self._completed_issues),
            "rate_limit": self.github.get_rate_limit_status(self.agent_id),
        }
