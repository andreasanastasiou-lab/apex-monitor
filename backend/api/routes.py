import html as _html
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ai.anomaly import get_anomaly_status
from alerts.engine import alert_engine
from auth.middleware import require_auth
from config import load_config
from db.influx import run_query
from monitors.icmp import ping_device

# Public router — no authentication required.
router = APIRouter()

# Protected router — every route requires a valid JWT.
_protected = APIRouter(dependencies=[Depends(require_auth)])

# Validated whitelist for query parameters that flow into Flux query strings.
_ALLOWED_METRICS = {"latency_ms", "packet_loss_pct", "is_alive"}
_ALLOWED_RANGES = {"1h", "6h", "24h", "7d"}

# Latency above this threshold (ms) on a reachable host reports WARNING.
_LATENCY_WARNING_MS = 100.0

_RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}

_REPORT_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f172a; color: #e2e8f0; font-family: system-ui, -apple-system, sans-serif; font-size: 14px; line-height: 1.6; }
.page { max-width: 960px; margin: 0 auto; padding: 40px 24px; }
h1 { font-size: 22px; font-weight: 700; color: #f8fafc; }
h2 { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin: 32px 0 12px; }
header { border-bottom: 1px solid #1e293b; padding-bottom: 20px; margin-bottom: 4px; }
.meta { color: #64748b; font-size: 12px; margin-top: 6px; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.stat { background: #1e293b; border-radius: 6px; padding: 12px 16px; }
.stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }
.stat-value { font-size: 22px; font-weight: 700; color: #f1f5f9; margin-top: 2px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 12px; background: #1e293b; color: #94a3b8; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
td { padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
tr:last-child td { border-bottom: none; }
.card { background: #1e293b; border-radius: 8px; margin-bottom: 4px; overflow: hidden; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
.badge-red { background: rgba(239,68,68,.15); color: #f87171; }
.badge-yellow { background: rgba(234,179,8,.15); color: #fbbf24; }
.badge-green { background: rgba(34,197,94,.15); color: #4ade80; }
.mono { font-family: 'Courier New', monospace; font-size: 12px; }
footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #1e293b; color: #475569; font-size: 11px; text-align: center; }
"""


def _get_diagnostic_data(device: dict, device_id: str, time_range: str) -> dict:
    host = device["ip"]
    bucket = os.environ.get("INFLUXDB_BUCKET", "")

    def _q_latency():
        return run_query(f"""
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "icmp")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "latency_ms")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
""")

    def _q_packet_loss():
        return run_query(f"""
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "icmp")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "packet_loss_pct")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
""")

    def _q_alive():
        return run_query(f"""
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "icmp")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "is_alive")
  |> keep(columns: ["_time", "_value"])
""")

    def _q_anomalies():
        return run_query(f"""
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "anomaly")
  |> filter(fn: (r) => r["device"] == "{device_id}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"], desc: true)
""")

    def _q_baseline():
        return run_query(f"""
from(bucket: "{bucket}")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "icmp")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "latency_ms")
  |> mean()
""")

    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = [
            pool.submit(_q_latency),
            pool.submit(_q_packet_loss),
            pool.submit(_q_alive),
            pool.submit(_q_anomalies),
            pool.submit(_q_baseline),
        ]
        lat_rows, pl_rows, alive_rows, anomaly_rows, baseline_rows = [f.result() for f in futs]

    lat_vals = [r["_value"] for r in lat_rows if r.get("_value") is not None]
    pl_vals = [r["_value"] for r in pl_rows if r.get("_value") is not None]

    avg_lat = round(sum(lat_vals) / len(lat_vals), 2) if lat_vals else None
    max_lat = round(max(lat_vals), 2) if lat_vals else None
    min_lat = round(min(lat_vals), 2) if lat_vals else None
    pl_avg = round(sum(pl_vals) / len(pl_vals), 2) if pl_vals else None

    total_checks = len(alive_rows)
    checks_up = sum(
        1 for r in alive_rows
        if r.get("_value") is not None and float(r["_value"]) > 0.5
    )
    uptime_pct = round((checks_up / total_checks) * 100, 2) if total_checks > 0 else None

    baseline_avg = baseline_rows[0].get("_value") if baseline_rows else None
    if avg_lat is not None and baseline_avg is not None and baseline_avg > 0:
        deviation_pct = round(((avg_lat - baseline_avg) / baseline_avg) * 100, 1)
        is_degraded = deviation_pct > 20
    else:
        deviation_pct = None
        is_degraded = False

    start_dt = datetime.utcnow() - _RANGE_DELTAS[time_range]
    device_alerts = [
        a for a in alert_engine.get_alerts()
        if a.device == device_id and a.timestamp >= start_dt
    ]

    return {
        "device": {
            "id": device_id,
            "name": device.get("name", device_id),
            "ip": host,
            "type": device.get("type", "unknown"),
        },
        "range": time_range,
        "summary": {
            "avg_latency_ms": avg_lat,
            "max_latency_ms": max_lat,
            "min_latency_ms": min_lat,
            "packet_loss_avg": pl_avg,
            "uptime_pct": uptime_pct,
            "total_checks": total_checks,
            "anomalies_count": len(anomaly_rows),
            "alerts_count": len(device_alerts),
        },
        "latency_timeline": [
            {"timestamp": str(r.get("_time", "")), "value": r.get("_value")}
            for r in lat_rows
        ],
        "packet_loss_timeline": [
            {"timestamp": str(r.get("_time", "")), "value": r.get("_value")}
            for r in pl_rows
        ],
        "alerts_in_range": [
            {
                "message": a.message,
                "severity": a.severity.value,
                "timestamp": a.timestamp.isoformat() + "Z",
            }
            for a in device_alerts
        ],
        "anomalies_in_range": [
            {
                "metric": r.get("metric", ""),
                "confidence": r.get("confidence"),
                "value": r.get("value"),
                "timestamp": str(r.get("_time", "")),
            }
            for r in anomaly_rows
        ],
        "baseline_comparison": {
            "current_avg_latency": avg_lat,
            "baseline_avg_latency": round(baseline_avg, 2) if baseline_avg is not None else None,
            "deviation_pct": deviation_pct,
            "is_degraded": is_degraded,
        },
    }


def _build_html_report(device: dict, time_range: str, diag: dict) -> str:
    dev = diag["device"]
    s = diag["summary"]
    bc = diag["baseline_comparison"]
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    dev_name = _html.escape(dev.get("name", "Unknown"))
    dev_ip = _html.escape(dev.get("ip", "—"))
    dev_type = _html.escape(dev.get("type", "—"))

    def _fv(v, unit=""):
        return f"{v}{unit}" if v is not None else "—"

    dev_pct = bc.get("deviation_pct")
    if dev_pct is None:
        bc_status = '<span class="badge">N/A</span>'
    elif abs(dev_pct) > 50:
        bc_status = '<span class="badge badge-red">Severely Degraded</span>'
    elif abs(dev_pct) > 20:
        bc_status = '<span class="badge badge-yellow">Degraded</span>'
    else:
        bc_status = '<span class="badge badge-green">Normal</span>'

    def _fmt_ts(ts_str: str) -> str:
        try:
            return str(ts_str)[:19].replace("T", " ")
        except Exception:
            return str(ts_str)

    alerts = diag.get("alerts_in_range", [])
    if alerts:
        alert_rows = ""
        for a in alerts:
            sev = a["severity"]
            cls = "badge-red" if sev == "CRITICAL" else "badge-yellow"
            alert_rows += (
                f'<tr><td><span class="badge {cls}">{_html.escape(sev)}</span></td>'
                f'<td>{_html.escape(a.get("message",""))}</td>'
                f'<td class="mono">{_fmt_ts(a.get("timestamp",""))}</td></tr>'
            )
    else:
        alert_rows = '<tr><td colspan="3" style="color:#4ade80;text-align:center;padding:16px">None during this period</td></tr>'

    anomalies = diag.get("anomalies_in_range", [])
    if anomalies:
        anomaly_rows = ""
        for a in anomalies:
            conf = a.get("confidence")
            val = a.get("value")
            anomaly_rows += (
                f'<tr><td>{_html.escape(str(a.get("metric","")))} </td>'
                f'<td>{f"{conf*100:.0f}%" if conf is not None else "—"}</td>'
                f'<td>{f"{val:.2f}" if val is not None else "—"}</td>'
                f'<td class="mono">{_fmt_ts(a.get("timestamp",""))}</td></tr>'
            )
    else:
        anomaly_rows = '<tr><td colspan="4" style="color:#4ade80;text-align:center;padding:16px">None during this period</td></tr>'

    lat_timeline = diag.get("latency_timeline", [])
    lat_slice = lat_timeline[-50:]
    if lat_slice:
        def _lat_row(r):
            ts_cell = _fmt_ts(r.get("timestamp", ""))
            v = r.get("value")
            val_cell = f"{v:.2f} ms" if v is not None else "—"
            return f'<tr><td class="mono">{ts_cell}</td><td>{val_cell}</td></tr>'

        lat_rows = "".join(_lat_row(r) for r in lat_slice)
        lat_heading = f"Latency Data (Last {len(lat_slice)} of {len(lat_timeline)} points)"
    else:
        lat_rows = '<tr><td colspan="2" style="color:#64748b;text-align:center;padding:16px">No latency data available</td></tr>'
        lat_heading = "Latency Data"

    dev_pct_str = f"{dev_pct}%" if dev_pct is not None else "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Apex Monitor — Diagnostic Report — {dev_name}</title>
  <style>{_REPORT_CSS}</style>
</head>
<body>
<div class="page">
  <header>
    <h1>Apex Monitor — Diagnostic Report</h1>
    <p class="meta">Device: <strong style="color:#e2e8f0">{dev_name}</strong> &nbsp;·&nbsp; IP: <strong style="color:#e2e8f0">{dev_ip}</strong> &nbsp;·&nbsp; Type: {dev_type}</p>
    <p class="meta">Time range: <strong style="color:#e2e8f0">Last {_html.escape(time_range)}</strong> &nbsp;·&nbsp; Generated: {now_str}</p>
  </header>

  <h2>Summary Statistics</h2>
  <div class="stat-grid">
    <div class="stat"><p class="stat-label">Avg Latency</p><p class="stat-value">{_fv(s.get("avg_latency_ms"), " ms")}</p></div>
    <div class="stat"><p class="stat-label">Max Latency</p><p class="stat-value">{_fv(s.get("max_latency_ms"), " ms")}</p></div>
    <div class="stat"><p class="stat-label">Min Latency</p><p class="stat-value">{_fv(s.get("min_latency_ms"), " ms")}</p></div>
    <div class="stat"><p class="stat-label">Uptime</p><p class="stat-value">{_fv(s.get("uptime_pct"), "%")}</p></div>
    <div class="stat"><p class="stat-label">Packet Loss Avg</p><p class="stat-value">{_fv(s.get("packet_loss_avg"), "%")}</p></div>
    <div class="stat"><p class="stat-label">Total Checks</p><p class="stat-value">{s.get("total_checks", 0)}</p></div>
  </div>

  <h2>Baseline Comparison (7-Day)</h2>
  <div class="card">
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Current Avg Latency</td><td>{_fv(bc.get("current_avg_latency"), " ms")}</td></tr>
      <tr><td>7-Day Baseline Avg</td><td>{_fv(bc.get("baseline_avg_latency"), " ms")}</td></tr>
      <tr><td>Deviation</td><td>{dev_pct_str}</td></tr>
      <tr><td>Status</td><td>{bc_status}</td></tr>
    </table>
  </div>

  <h2>Alerts During Period ({len(alerts)})</h2>
  <div class="card">
    <table>
      <thead><tr><th>Severity</th><th>Message</th><th>Time</th></tr></thead>
      <tbody>{alert_rows}</tbody>
    </table>
  </div>

  <h2>Anomalies During Period ({len(anomalies)})</h2>
  <div class="card">
    <table>
      <thead><tr><th>Metric</th><th>Confidence</th><th>Value</th><th>Time</th></tr></thead>
      <tbody>{anomaly_rows}</tbody>
    </table>
  </div>

  <h2>{_html.escape(lat_heading)}</h2>
  <div class="card">
    <table>
      <thead><tr><th>Timestamp</th><th>Latency</th></tr></thead>
      <tbody>{lat_rows}</tbody>
    </table>
  </div>

  <footer>Generated by Apex Monitor — Confidential</footer>
</div>
</body>
</html>"""


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


@_protected.get("/devices")
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


@_protected.get("/devices/{device_id}/metrics")
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


@_protected.get("/alerts")
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


@_protected.get("/summary")
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


@_protected.get("/anomalies")
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


@_protected.get("/devices/{device_id}/anomaly-status")
def get_device_anomaly_status(device_id: str):
    devices = load_config().get("devices", [])
    if not any(d["name"] == device_id for d in devices):
        raise HTTPException(status_code=404, detail="Device not found")

    return get_anomaly_status(device_id)


@_protected.get("/notifications")
def get_notifications(unread_only: bool = Query(default=False)):
    return [_alert_to_dict(a) for a in alert_engine.get_alerts(unread_only=unread_only)]


@_protected.post("/notifications/{alert_id}/read")
def mark_notification_read(alert_id: str):
    return {"success": alert_engine.mark_read(alert_id)}


@_protected.post("/notifications/read-all")
def mark_all_notifications_read():
    return {"success": alert_engine.mark_all_read()}


@_protected.get("/notifications/count")
def get_notification_count():
    return {
        "unread": alert_engine.get_unread_count(),
        "total": len(alert_engine.get_alerts()),
    }


# ── Diagnostic endpoints ────────────────────────────────────────────────────
# /diagnostic/correlation must be registered before /diagnostic/{device_id}
# so FastAPI doesn't match the literal segment "correlation" as a device_id.

@_protected.get("/diagnostic/correlation")
def get_diagnostic_correlation(
    time_range: str = Query(default="6h", alias="range"),
):
    if time_range not in _ALLOWED_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"range must be one of: {', '.join(sorted(_ALLOWED_RANGES))}",
        )
    devices = load_config().get("devices", [])
    bucket = os.environ.get("INFLUXDB_BUCKET", "")

    def _fetch(device: dict) -> dict:
        host = device["ip"]
        name = device.get("name", host)
        rows = run_query(f"""
from(bucket: "{bucket}")
  |> range(start: -{time_range})
  |> filter(fn: (r) => r._measurement == "icmp")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "latency_ms")
  |> keep(columns: ["_time", "_value"])
  |> sort(columns: ["_time"])
""")
        return {
            "device_name": name,
            "latency_timeline": [
                {"timestamp": str(r.get("_time", "")), "value": r.get("_value")}
                for r in rows
            ],
        }

    with ThreadPoolExecutor(max_workers=min(len(devices), 10)) as pool:
        results = list(pool.map(_fetch, devices))

    return {"range": time_range, "devices": results}


@_protected.get("/diagnostic/{device_id}/report")
def get_diagnostic_report(
    device_id: str,
    time_range: str = Query(default="6h", alias="range"),
):
    if time_range not in _ALLOWED_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"range must be one of: {', '.join(sorted(_ALLOWED_RANGES))}",
        )
    devices = load_config().get("devices", [])
    device = next((d for d in devices if d["name"] == device_id), None)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    diag = _get_diagnostic_data(device, device_id, time_range)
    html_content = _build_html_report(device, time_range, diag)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in device_id)
    date_str = datetime.utcnow().strftime("%Y%m%d")
    filename = f"apex-report-{safe_name}-{date_str}.html"
    return Response(
        content=html_content,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@_protected.get("/diagnostic/{device_id}")
def get_diagnostic(
    device_id: str,
    time_range: str = Query(default="6h", alias="range"),
):
    if time_range not in _ALLOWED_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"range must be one of: {', '.join(sorted(_ALLOWED_RANGES))}",
        )
    devices = load_config().get("devices", [])
    device = next((d for d in devices if d["name"] == device_id), None)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return _get_diagnostic_data(device, device_id, time_range)


# Merge all protected routes into the public router so main.py only
# needs to include_router(router) once.
router.include_router(_protected)
