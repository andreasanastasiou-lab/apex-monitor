import logging

from apscheduler.schedulers.background import BackgroundScheduler

from ai.anomaly import detect_anomaly, train_baseline
from alerts.engine import alert_engine
from config import load_config
from db.influx import write_metric
from monitors.icmp import ping_device
from monitors.port_check import check_port

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _run_ping(host: str, name: str) -> None:
    result = ping_device(host)
    alert_engine.process_ping_result(name, result)

    latency = result.get("latency_ms")
    if result.get("is_alive") and latency is not None:
        anomaly = detect_anomaly(name, "latency_ms", latency)
        if anomaly["is_anomaly"]:
            write_metric(
                "anomaly",
                {"device": name, "metric": "latency_ms"},
                {
                    "is_anomaly": 1,
                    "confidence": float(anomaly["confidence"]),
                    "value": float(latency),
                },
            )
            logger.warning(
                "Anomaly — %s latency_ms=%.1f confidence=%.2f",
                name, latency, anomaly["confidence"],
            )
            alert_engine.process_anomaly(name, "latency_ms", anomaly)

    alert_engine.correlate_alerts()


def _run_port_check(host: str, port: int, name: str) -> None:
    result = check_port(host, port)
    alert_engine.process_port_result(name, port, result)

    response_time = result.get("response_time_ms")
    if result.get("is_open") and response_time is not None:
        anomaly = detect_anomaly(name, "response_time_ms", response_time)
        if anomaly["is_anomaly"]:
            write_metric(
                "anomaly",
                {"device": name, "metric": "response_time_ms"},
                {
                    "is_anomaly": 1,
                    "confidence": float(anomaly["confidence"]),
                    "value": float(response_time),
                },
            )
            logger.warning(
                "Anomaly — %s port %d response_time_ms=%.1f confidence=%.2f",
                name, port, response_time, anomaly["confidence"],
            )
            alert_engine.process_anomaly(name, "response_time_ms", anomaly)

    alert_engine.correlate_alerts()


def _retrain_all() -> None:
    """Daily retraining job — rebuilds IsolationForest models for every device."""
    config = load_config()
    for device in config.get("devices", []):
        name = device.get("name", device["ip"])
        monitors = device.get("monitors", [])
        if "icmp" in monitors:
            train_baseline(name, "latency_ms")
        if "port_check" in monitors:
            train_baseline(name, "response_time_ms")


def start_scheduler() -> None:
    config = load_config()
    devices = config.get("devices", [])

    for device in devices:
        host = device["ip"]
        name = device.get("name", host)
        monitors = device.get("monitors", [])

        if "icmp" in monitors:
            _scheduler.add_job(
                _run_ping,
                trigger="interval",
                seconds=60,
                args=[host, name],
                id=f"ping_{host}",
                replace_existing=True,
                name=f"ICMP {name}",
            )
            logger.info("Scheduled ICMP ping for %s (%s) every 60s", name, host)

        if "port_check" in monitors:
            for port in device.get("ports", []):
                _scheduler.add_job(
                    _run_port_check,
                    trigger="interval",
                    minutes=5,
                    args=[host, port, name],
                    id=f"port_{host}_{port}",
                    replace_existing=True,
                    name=f"Port {port} {name}",
                )
                logger.info("Scheduled port check %s:%s (%s) every 5m", name, port, host)

    # Daily model retraining at 02:00.
    _scheduler.add_job(
        _retrain_all,
        trigger="cron",
        hour=2,
        minute=0,
        id="retrain_all",
        replace_existing=True,
        name="Retrain anomaly models",
    )
    logger.info("Scheduled daily model retraining at 02:00")

    _scheduler.start()
    logger.info("Scheduler started — %d jobs registered", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    _scheduler.shutdown(wait=False)
