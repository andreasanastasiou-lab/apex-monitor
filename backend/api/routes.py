import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query

from ai.anomaly import get_anomaly_status
from alerts.engine import alert_engine
from config import load_config
from db.influx import run_query
from monitors.icmp import ping_device

router = APIRouter()

# Validated whitelist for query parameters that flow into Flux query strings.
_ALLOWED_METRICS = {"latency_ms", "packet_loss_pct", "is_alive"}
_ALLOWED_RANGES = {"1h", "6h", "24h", "7d"}

# Latency above this threshold (ms) on a reachable host reports WARNING.
_LATENCY_WARNING_MS = 100.0


def _alert_to_dict(alert) -> dict:
    return {
        "id": alert.id,
        "device": alert.device,
        "metric": alert.metric,
        "message": alert.message,
        "severity": alert.severity.value,
        "timestamp": alert.timestamp.isoformat() + "Z",
        "is_read": alert.is_read,
        "value": alert.value,
    }


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/devices")
def get_devices():
    devices = load_config().get("devices", [])

    def _probe(device: dict) -> dict:
        result = ping_device(device["ip"])
        is_alive = result["is_alive"]
        latency = result.get("latency_ms")

        if is_alive:
            status = "WARNING" if latency and latency > _LATENCY_WARNING_MS else "UP"
        else:
            status = "DOWN"

        return {
            "id": device["name"],
            "name": device["name"],
            "ip": device["ip"],
            "type": device["type"],
            "status": status,
            "latency_ms": latency,
            "last_checked": result["timestamp"],
        }

    if not devices:
        return []

    with ThreadPoolExecutor(max_workers=min(len(devices), 10)) as pool:
        results = list(pool.map(_probe, devices))

    return results


@router.get("/devices/{device_id}/metrics")
def get_device_metrics(
    device_id: str,
    metric: str = Query(default="latency_ms"),
    time_range: str = Query(default="1h", alias="range"),
):
    if metric not in _ALLOWED_METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"metric must be one of: {', '.join(sorted(_ALLOWED_METRICS))}",
        )
    if time_range not in _ALLOWED_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"range must be one of: {', '.join(sorted(_ALLOWED_RANGES))}",
        )

    devices = load_config().get("devices", [])
    device = next((d for d in devices if d["name"] == device_id), None)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    host = device["ip"]
    bucket = os.environ.get("INFLUXDB_BUCKET", "")

    flux = f"""
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "icmp")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "{metric}")
  |> keep(columns: ["_time", "_value"])
"""
    rows = run_query(flux)
    return [{"timestamp": str(r.get("_time", "")), "value": r.get("_value")} for r in rows]


@router.get("/alerts")
def get_alerts():
    bucket = os.environ.get("INFLUXDB_BUCKET", "")

    # Union ICMP down-events and port-closed events from the last 24 h.
    # ICMP records have no "port" tag; it will be None in those rows.
    flux = f"""
alive_alerts = from(bucket: "{bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "icmp" and r._field == "is_alive" and r._value == 0)

port_alerts = from(bucket: "{bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "port_check" and r._field == "is_open" and r._value == 0)

union(tables: [alive_alerts, port_alerts])
  |> sort(columns: ["_time"], desc: true)
"""
    rows = run_query(flux)

    results = []
    for r in rows:
        field = r.get("_field", "")
        severity = "critical" if field == "is_alive" else "warning"
        entry = {
            "device": r.get("host", "unknown"),
            "metric": field,
            "value": r.get("_value"),
            "timestamp": str(r.get("_time", "")),
            "severity": severity,
        }
        if r.get("port") is not None:
            entry["port"] = r["port"]
        results.append(entry)

    return results


@router.get("/summary")
def get_summary():
    total_devices = len(load_config().get("devices", []))
    bucket = os.environ.get("INFLUXDB_BUCKET", "")

    # Most-recent is_alive value per host within the last polling window.
    flux_alive = f"""
from(bucket: "{bucket}")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "icmp" and r._field == "is_alive")
  |> last()
  |> keep(columns: ["host", "_value"])
"""

    # Most-recent latency per host — only where the host was reachable.
    flux_latency = f"""
from(bucket: "{bucket}")
  |> range(start: -5m)
  |> filter(fn: (r) => r._measurement == "icmp" and r._field == "latency_ms" and r._value > 0.0)
  |> last()
  |> keep(columns: ["host", "_value"])
"""

    alive_rows = run_query(flux_alive)
    latency_rows = run_query(flux_latency)

    devices_up = sum(1 for r in alive_rows if r.get("_value") == 1)
    devices_down = sum(1 for r in alive_rows if r.get("_value") == 0)

    latencies = [r["_value"] for r in latency_rows if r.get("_value")]
    avg_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else None

    health_score = round((devices_up / total_devices) * 100) if total_devices > 0 else 0

    return {
        "total_devices": total_devices,
        "devices_up": devices_up,
        "devices_down": devices_down,
        "avg_latency_ms": avg_latency_ms,
        "health_score": health_score,
    }


@router.get("/anomalies")
def get_anomalies():
    bucket = os.environ.get("INFLUXDB_BUCKET", "")

    # We only write to the "anomaly" measurement when is_anomaly is True,
    # so every row here is a confirmed anomaly event.
    flux = f"""
from(bucket: "{bucket}")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "anomaly")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
"""
    rows = run_query(flux)
    return [
        {
            "device": r.get("device", "unknown"),
            "metric": r.get("metric", ""),
            "value": r.get("value"),
            "confidence": r.get("confidence"),
            "timestamp": str(r.get("_time", "")),
        }
        for r in rows
    ]


@router.get("/devices/{device_id}/anomaly-status")
def get_device_anomaly_status(device_id: str):
    devices = load_config().get("devices", [])
    if not any(d["name"] == device_id for d in devices):
        raise HTTPException(status_code=404, detail="Device not found")

    return get_anomaly_status(device_id)


@router.get("/notifications")
def get_notifications(unread_only: bool = Query(default=False)):
    return [_alert_to_dict(a) for a in alert_engine.get_alerts(unread_only=unread_only)]


@router.post("/notifications/{alert_id}/read")
def mark_notification_read(alert_id: str):
    return {"success": alert_engine.mark_read(alert_id)}


@router.post("/notifications/read-all")
def mark_all_notifications_read():
    return {"success": alert_engine.mark_all_read()}


@router.get("/notifications/count")
def get_notification_count():
    return {
        "unread": alert_engine.get_unread_count(),
        "total": len(alert_engine.get_alerts()),
    }
