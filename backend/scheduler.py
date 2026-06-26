import logging

from apscheduler.schedulers.background import BackgroundScheduler

from config import load_config
from monitors.icmp import ping_device
from monitors.port_check import check_port

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _run_ping(host: str) -> None:
    ping_device(host)


def _run_port_check(host: str, port: int) -> None:
    check_port(host, port)


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
                args=[host],
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
                    args=[host, port],
                    id=f"port_{host}_{port}",
                    replace_existing=True,
                    name=f"Port {port} {name}",
                )
                logger.info("Scheduled port check %s:%s (%s) every 5m", name, port, host)

    _scheduler.start()
    logger.info("Scheduler started — %d jobs registered", len(_scheduler.get_jobs()))


def stop_scheduler() -> None:
    _scheduler.shutdown(wait=False)
