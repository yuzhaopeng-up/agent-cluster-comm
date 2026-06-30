"""
L5 Cluster Health Monitor Engine
Multi-channel health monitoring with tiered alerts.
Fuses health signals from L1 (P2P), L2 (MessageBus), L3 (GroupChat) channels.
Implements INFO / WARNING / CRITICAL tiered alerting with cross-channel fusion.
"""

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Set, Tuple


class AlertLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ChannelType(Enum):
    P2P_RELAY = "p2p_relay"
    MESSAGE_BUS = "message_bus"
    GROUP_CHAT = "group_chat"
    GITHUB = "github"


class NodeStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


HEALTH_SCORE_THRESHOLDS = {
    AlertLevel.INFO: 0.8,
    AlertLevel.WARNING: 0.5,
    AlertLevel.CRITICAL: 0.0,
}


@dataclass
class HealthCheck:
    check_id: str
    channel: ChannelType
    node_id: str
    check_name: str
    passed: bool
    score: float
    details: str
    timestamp: float
    latency_ms: float = 0.0


@dataclass
class Alert:
    alert_id: str
    level: AlertLevel
    channel: ChannelType
    node_id: str
    message: str
    score: float
    checks: List[HealthCheck]
    timestamp: float
    suppressed: bool = False
    acknowledged: bool = False


@dataclass
class NodeRecord:
    node_id: str
    channels: Dict[ChannelType, NodeStatus]
    last_check: Dict[ChannelType, float]
    consecutive_failures: Dict[ChannelType, int]
    health_score: Dict[ChannelType, float]
    overall_score: float = 1.0
    registered_at: float = field(default_factory=time.time)


@dataclass
class FusionResult:
    node_id: str
    overall_score: float
    channel_scores: Dict[ChannelType, float]
    dominant_channel: ChannelType
    alert_level: AlertLevel
    contributing_factors: List[str]


class SimulatedHealthProbe:
    """Simulates health probes for each channel type."""

    def __init__(self):
        self._node_health: Dict[str, Dict[ChannelType, dict]] = defaultdict(dict)
        self._failure_injections: Dict[str, Dict[ChannelType, bool]] = defaultdict(dict)

    def register_node(self, node_id: str, channel: ChannelType,
                      initial_status: NodeStatus = NodeStatus.HEALTHY):
        self._node_health[node_id][channel] = {
            "status": initial_status,
            "latency_ms": 10.0,
            "last_seen": time.time(),
        }

    def inject_failure(self, node_id: str, channel: ChannelType):
        self._failure_injections[node_id][channel] = True

    def clear_failure(self, node_id: str, channel: ChannelType):
        self._failure_injections[node_id].pop(channel, None)

    def check(self, node_id: str, channel: ChannelType) -> HealthCheck:
        is_failed = self._failure_injections.get(node_id, {}).get(channel, False)
        health_info = self._node_health.get(node_id, {}).get(channel, {})

        if is_failed:
            return HealthCheck(
                check_id=str(uuid.uuid4())[:8],
                channel=channel, node_id=node_id,
                check_name=f"{channel.value}_connectivity",
                passed=False, score=0.0,
                details=f"{channel.value} channel unreachable for {node_id}",
                timestamp=time.time(), latency_ms=9999.0,
            )

        latency = health_info.get("latency_ms", 10.0)
        status = health_info.get("status", NodeStatus.UNKNOWN)
        if status == NodeStatus.HEALTHY:
            score = max(0.0, 1.0 - (latency / 1000.0))
            return HealthCheck(
                check_id=str(uuid.uuid4())[:8],
                channel=channel, node_id=node_id,
                check_name=f"{channel.value}_connectivity",
                passed=True, score=score,
                details=f"{channel.value} OK, latency={latency:.0f}ms",
                timestamp=time.time(), latency_ms=latency,
            )
        elif status == NodeStatus.DEGRADED:
            return HealthCheck(
                check_id=str(uuid.uuid4())[:8],
                channel=channel, node_id=node_id,
                check_name=f"{channel.value}_connectivity",
                passed=True, score=0.4,
                details=f"{channel.value} degraded, latency={latency:.0f}ms",
                timestamp=time.time(), latency_ms=latency,
            )
        else:
            return HealthCheck(
                check_id=str(uuid.uuid4())[:8],
                channel=channel, node_id=node_id,
                check_name=f"{channel.value}_connectivity",
                passed=False, score=0.0,
                details=f"{channel.value} unreachable",
                timestamp=time.time(), latency_ms=9999.0,
            )

    def get_registered_nodes(self) -> List[str]:
        return list(self._node_health.keys())


class CrossChannelFusion:
    """
    Cross-channel health fusion engine.
    Combines health signals from multiple channels to produce
    a unified health assessment with tiered alert levels.
    """

    CHANNEL_WEIGHTS = {
        ChannelType.P2P_RELAY: 0.2,
        ChannelType.MESSAGE_BUS: 0.3,
        ChannelType.GROUP_CHAT: 0.3,
        ChannelType.GITHUB: 0.2,
    }

    FAILURE_AMPLIFICATION = 2.0

    @staticmethod
    def fuse(checks: List[HealthCheck],
             node: NodeRecord) -> FusionResult:
        channel_scores: Dict[ChannelType, float] = {}
        channel_checks: Dict[ChannelType, List[HealthCheck]] = defaultdict(list)

        for check in checks:
            channel_checks[check.channel].append(check)

        for ch, ch_checks in channel_checks.items():
            if not ch_checks:
                channel_scores[ch] = node.health_score.get(ch, 1.0)
                continue
            avg_score = sum(c.score for c in ch_checks) / len(ch_checks)
            failures = sum(1 for c in ch_checks if not c.passed)
            if failures > 0:
                avg_score = max(0.0, avg_score - failures * 0.15)
            channel_scores[ch] = avg_score

        overall = 0.0
        total_weight = 0.0
        for ch, score in channel_scores.items():
            weight = CrossChannelFusion.CHANNEL_WEIGHTS.get(ch, 0.25)
            overall += weight * score
            total_weight += weight
        if total_weight > 0:
            overall /= total_weight

        multi_channel_failure = sum(
            1 for s in channel_scores.values() if s < 0.3
        )
        if multi_channel_failure >= 2:
            overall *= (1.0 / CrossChannelFusion.FAILURE_AMPLIFICATION)

        if overall >= HEALTH_SCORE_THRESHOLDS[AlertLevel.INFO]:
            level = AlertLevel.INFO
        elif overall >= HEALTH_SCORE_THRESHOLDS[AlertLevel.WARNING]:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.CRITICAL

        dominant = max(channel_scores, key=lambda k: channel_scores.get(k, 0))
        factors = []
        for ch, score in channel_scores.items():
            if score < 0.8:
                factors.append(
                    f"{ch.value}: score={score:.2f}"
                )
        if multi_channel_failure >= 2:
            factors.append("multi-channel-failure-amplification")

        return FusionResult(
            node_id=node.node_id,
            overall_score=round(overall, 3),
            channel_scores=channel_scores,
            dominant_channel=dominant,
            alert_level=level,
            contributing_factors=factors,
        )


class AlertManager:
    """Manages tiered alerts with suppression and acknowledgment."""

    SUPPRESSION_WINDOW = 60.0

    def __init__(self):
        self._alerts: List[Alert] = []
        self._suppression_keys: Dict[str, float] = {}
        self._handlers: Dict[AlertLevel, List[Callable]] = defaultdict(list)

    def add_handler(self, level: AlertLevel, handler: Callable):
        self._handlers[level].append(handler)

    def emit(self, level: AlertLevel, channel: ChannelType,
             node_id: str, message: str, score: float,
             checks: List[HealthCheck]) -> Optional[Alert]:
        suppression_key = f"{channel.value}:{node_id}:{level.value}"
        last_time = self._suppression_keys.get(suppression_key, 0)
        if (time.time() - last_time) < self.SUPPRESSION_WINDOW:
            return None
        self._suppression_keys[suppression_key] = time.time()

        alert = Alert(
            alert_id=str(uuid.uuid4())[:8],
            level=level, channel=channel,
            node_id=node_id, message=message,
            score=score, checks=checks,
            timestamp=time.time(),
        )
        self._alerts.append(alert)
        for handler in self._handlers.get(level, []):
            try:
                handler(alert)
            except Exception:
                pass
        return alert

    def acknowledge(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_active_alerts(self, level: AlertLevel = None) -> List[Alert]:
        alerts = [a for a in self._alerts if not a.acknowledged]
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts

    def get_alert_stats(self) -> dict:
        by_level = defaultdict(int)
        for a in self._alerts:
            by_level[a.level.value] += 1
        return {
            "total_alerts": len(self._alerts),
            "by_level": dict(by_level),
            "acknowledged": sum(1 for a in self._alerts if a.acknowledged),
            "active": sum(1 for a in self._alerts if not a.acknowledged),
        }


class HealthMonitorEngine:
    """Core engine for multi-channel cluster health monitoring."""

    CONSECUTIVE_FAILURE_THRESHOLD = 3

    def __init__(self, probe: SimulatedHealthProbe = None):
        self.probe = probe or SimulatedHealthProbe()
        self.fusion = CrossChannelFusion()
        self.alert_mgr = AlertManager()
        self._nodes: Dict[str, NodeRecord] = {}
        self._check_history: Dict[str, List[HealthCheck]] = defaultdict(list)
        self._fusion_history: Dict[str, List[FusionResult]] = defaultdict(list)

    def register_node(self, node_id: str,
                      channels: List[ChannelType] = None):
        if channels is None:
            channels = list(ChannelType)
        record = NodeRecord(
            node_id=node_id,
            channels={ch: NodeStatus.HEALTHY for ch in channels},
            last_check={ch: 0.0 for ch in channels},
            consecutive_failures={ch: 0 for ch in channels},
            health_score={ch: 1.0 for ch in channels},
        )
        self._nodes[node_id] = record
        for ch in channels:
            self.probe.register_node(node_id, ch)

    def inject_failure(self, node_id: str, channel: ChannelType):
        self.probe.inject_failure(node_id, channel)

    def clear_failure(self, node_id: str, channel: ChannelType):
        self.probe.clear_failure(node_id, channel)

    def check_node(self, node_id: str,
                   channels: List[ChannelType] = None) -> FusionResult:
        node = self._nodes.get(node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not registered")
        if channels is None:
            channels = list(node.channels.keys())

        checks = []
        for ch in channels:
            check = self.probe.check(node_id, ch)
            checks.append(check)
            node.last_check[ch] = time.time()
            self._check_history[node_id].append(check)

            if check.passed:
                node.consecutive_failures[ch] = 0
                node.health_score[ch] = (
                    0.7 * node.health_score[ch] + 0.3 * check.score
                )
            else:
                node.consecutive_failures[ch] += 1
                node.health_score[ch] = (
                    0.5 * node.health_score[ch] + 0.5 * check.score
                )
                if node.consecutive_failures[ch] >= self.CONSECUTIVE_FAILURE_THRESHOLD:
                    node.channels[ch] = NodeStatus.UNREACHABLE
                    self.alert_mgr.emit(
                        AlertLevel.CRITICAL, ch, node_id,
                        f"Node {node_id} unreachable on {ch.value} "
                        f"({node.consecutive_failures[ch]} consecutive failures)",
                        node.health_score[ch], [check],
                    )
                elif node.consecutive_failures[ch] >= 1:
                    node.channels[ch] = NodeStatus.DEGRADED
                    self.alert_mgr.emit(
                        AlertLevel.WARNING, ch, node_id,
                        f"Node {node_id} degraded on {ch.value}",
                        node.health_score[ch], [check],
                    )

        fusion_result = self.fusion.fuse(checks, node)
        node.overall_score = fusion_result.overall_score
        self._fusion_history[node_id].append(fusion_result)

        if fusion_result.alert_level == AlertLevel.WARNING:
            self.alert_mgr.emit(
                AlertLevel.WARNING,
                ChannelType.MESSAGE_BUS,
                node_id,
                f"Overall health degraded: score={fusion_result.overall_score:.2f}",
                fusion_result.overall_score,
                checks,
            )
        elif fusion_result.alert_level == AlertLevel.CRITICAL:
            self.alert_mgr.emit(
                AlertLevel.CRITICAL,
                fusion_result.dominant_channel,
                node_id,
                f"Overall health critical: score={fusion_result.overall_score:.2f}. "
                f"Factors: {', '.join(fusion_result.contributing_factors)}",
                fusion_result.overall_score,
                checks,
            )

        return fusion_result

    def check_cluster(self) -> List[FusionResult]:
        results = []
        for node_id in list(self._nodes.keys()):
            result = self.check_node(node_id)
            results.append(result)
        return results

    def generate_health_report(self) -> dict:
        nodes = []
        for nid, node in self._nodes.items():
            latest_fusion = (self._fusion_history[nid][-1]
                             if self._fusion_history[nid] else None)
            nodes.append({
                "node_id": nid,
                "overall_score": round(node.overall_score, 3),
                "channels": {
                    ch.value: {
                        "status": node.channels[ch].value,
                        "score": round(node.health_score[ch], 3),
                        "consecutive_failures": node.consecutive_failures[ch],
                    }
                    for ch in node.channels
                },
                "latest_alert_level": (
                    latest_fusion.alert_level.value if latest_fusion else "NONE"
                ),
            })

        active = self.alert_mgr.get_active_alerts()
        critical = [a for a in active if a.level == AlertLevel.CRITICAL]
        warnings = [a for a in active if a.level == AlertLevel.WARNING]

        return {
            "report_time": time.time(),
            "cluster_size": len(self._nodes),
            "healthy_nodes": sum(
                1 for n in self._nodes.values()
                if n.overall_score >= 0.8
            ),
            "degraded_nodes": sum(
                1 for n in self._nodes.values()
                if 0.5 <= n.overall_score < 0.8
            ),
            "critical_nodes": sum(
                1 for n in self._nodes.values()
                if n.overall_score < 0.5
            ),
            "nodes": nodes,
            "alerts": {
                "active_critical": len(critical),
                "active_warnings": len(warnings),
                "total_alerts": self.alert_mgr.get_alert_stats()["total_alerts"],
            },
            "recommendations": self._generate_recommendations(),
        }

    def _generate_recommendations(self) -> List[str]:
        recs = []
        for nid, node in self._nodes.items():
            for ch, status in node.channels.items():
                if status == NodeStatus.UNREACHABLE:
                    recs.append(
                        f"[CRITICAL] {nid}: {ch.value} unreachable — "
                        f"restart or replace node"
                    )
                elif status == NodeStatus.DEGRADED:
                    recs.append(
                        f"[WARNING] {nid}: {ch.value} degraded — "
                        f"check latency and load"
                    )
        if not recs:
            recs.append("All nodes healthy — no action required")
        return recs

    def get_info(self) -> dict:
        return {
            "monitored_nodes": len(self._nodes),
            "total_checks": sum(len(h) for h in self._check_history.values()),
            "alert_stats": self.alert_mgr.get_alert_stats(),
        }
