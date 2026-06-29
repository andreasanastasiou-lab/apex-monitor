import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Alert:
    id: str
    device: str
    metric: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    is_read: bool = False
    value: Optional[float] = None


class AlertEngine:
    _MAX_ALERTS = 100
    _COOLDOWN_MINUTES = 10
    _FAILURE_THRESHOLD = 3
    _CORRELATION_WINDOW_SECONDS = 120
    _CORRELATION_THRESHOLD = 3

    def __init__(self):
        self._alerts: list[Alert] = []
        self._cooldowns: dict[str, datetime] = {}
        self._failure_counts: dict[str, int] = {}

    def _key(self, device: str, metric: str) -> str:
        return f"{device}:{metric}"

    def _is_on_cooldown(self, device: str, metric: str) -> bool:
        last = self._cooldowns.get(self._key(device, metric))
        if last is None:
            return False
        return datetime.utcnow() - last < timedelta(minutes=self._COOLDOWN_MINUTES)

    def _set_cooldown(self, device: str, metric: str) -> None:
        self._cooldowns[self._key(device, metric)] = datetime.utcnow()

    def _add_alert(self, alert: Alert) -> Alert:
        self._alerts.append(alert)
        if len(self._alerts) > self._MAX_ALERTS:
            self._alerts = self._alerts[-self._MAX_ALERTS:]
        self._set_cooldown(alert.device, alert.metric)
        return alert

    def process_ping_result(self, device_name: str, result: dict) -> Optional[Alert]:
        fail_key = self._key(device_name, "ping_is_alive")

        if not result.get("is_alive", True):
            self._failure_counts[fail_key] = self._failure_counts.get(fail_key, 0) + 1
            if (
                self._failure_counts[fail_key] >= self._FAILURE_THRESHOLD
                and not self._is_on_cooldown(device_name, "ping_is_alive")
            ):
                return self._add_alert(Alert(
                    id=str(uuid.uuid4()),
                    device=device_name,
                    metric="ping_is_alive",
                    message=f"{device_name} is down",
                    severity=AlertSeverity.CRITICAL,
                    timestamp=datetime.utcnow(),
                ))
        else:
            self._failure_counts[fail_key] = 0
            latency = result.get("latency_ms")
            if latency is not None and latency > 100.0:
                if not self._is_on_cooldown(device_name, "high_latency"):
                    return self._add_alert(Alert(
                        id=str(uuid.uuid4()),
                        device=device_name,
                        metric="high_latency",
                        message=f"{device_name} high latency: {latency:.1f} ms",
                        severity=AlertSeverity.WARNING,
                        timestamp=datetime.utcnow(),
                        value=float(latency),
                    ))
        return None

    def process_port_result(self, device_name: str, port: int, result: dict) -> Optional[Alert]:
        metric = f"port_{port}"
        if not result.get("is_open", True):
            if not self._is_on_cooldown(device_name, metric):
                return self._add_alert(Alert(
                    id=str(uuid.uuid4()),
                    device=device_name,
                    metric=metric,
                    message=f"{device_name} port {port} closed unexpectedly",
                    severity=AlertSeverity.WARNING,
                    timestamp=datetime.utcnow(),
                    value=float(port),
                ))
        return None

    def process_anomaly(self, device_name: str, metric: str, anomaly: dict) -> Optional[Alert]:
        if not anomaly.get("is_anomaly"):
            return None
        confidence = float(anomaly.get("confidence", 0.0))
        alert_metric = f"anomaly_{metric}"
        if self._is_on_cooldown(device_name, alert_metric):
            return None
        if confidence > 0.8:
            severity = AlertSeverity.CRITICAL
            message = f"{device_name} security/anomaly threat on {metric} (confidence {confidence:.0%})"
        elif confidence > 0.5:
            severity = AlertSeverity.WARNING
            message = f"{device_name} anomaly detected on {metric} (confidence {confidence:.0%})"
        else:
            return None
        return self._add_alert(Alert(
            id=str(uuid.uuid4()),
            device=device_name,
            metric=alert_metric,
            message=message,
            severity=severity,
            timestamp=datetime.utcnow(),
            value=confidence,
        ))

    def get_alerts(self, unread_only: bool = False) -> list[Alert]:
        alerts = sorted(self._alerts, key=lambda a: a.timestamp, reverse=True)
        if unread_only:
            return [a for a in alerts if not a.is_read]
        return alerts

    def mark_read(self, alert_id: str) -> bool:
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.is_read = True
                return True
        return False

    def mark_all_read(self) -> bool:
        for alert in self._alerts:
            alert.is_read = True
        return True

    def get_unread_count(self) -> int:
        return sum(1 for a in self._alerts if not a.is_read)

    def correlate_alerts(self) -> Optional[Alert]:
        window_start = datetime.utcnow() - timedelta(seconds=self._CORRELATION_WINDOW_SECONDS)
        recent_criticals = [
            a for a in self._alerts
            if a.severity == AlertSeverity.CRITICAL
            and a.timestamp >= window_start
            and a.device != "network"
        ]
        if len(recent_criticals) < self._CORRELATION_THRESHOLD:
            return None
        already_exists = any(
            a.device == "network"
            and a.metric == "correlation"
            and a.timestamp >= window_start
            for a in self._alerts
        )
        if already_exists:
            return None
        for a in recent_criticals:
            a.is_read = True
        return self._add_alert(Alert(
            id=str(uuid.uuid4()),
            device="network",
            metric="correlation",
            message=f"Network-level event: {len(recent_criticals)} critical alerts in the last 2 minutes",
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.utcnow(),
        ))


alert_engine = AlertEngine()
