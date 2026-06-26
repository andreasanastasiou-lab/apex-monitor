import datetime

from icmplib import ping, NameLookupError, SocketPermissionError

from db.influx import write_metric


def ping_device(host: str, count: int = 4, timeout: float = 2.0) -> dict:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        raw = ping(host, count=count, interval=0.2, timeout=timeout, privileged=False)
        result = {
            "host": host,
            "is_alive": raw.is_alive,
            "latency_ms": round(raw.avg_rtt, 2) if raw.is_alive else None,
            "packet_loss_pct": round(raw.packet_loss * 100, 1),
            "timestamp": timestamp,
        }
    except NameLookupError:
        result = {
            "host": host,
            "is_alive": False,
            "latency_ms": None,
            "packet_loss_pct": 100.0,
            "timestamp": timestamp,
            "error": "dns_lookup_failed",
        }
    except SocketPermissionError:
        # Windows requires Administrator; Linux requires root or CAP_NET_RAW
        result = {
            "host": host,
            "is_alive": False,
            "latency_ms": None,
            "packet_loss_pct": 100.0,
            "timestamp": timestamp,
            "error": "insufficient_privileges_run_as_admin",
        }
    except Exception as e:
        result = {
            "host": host,
            "is_alive": False,
            "latency_ms": None,
            "packet_loss_pct": 100.0,
            "timestamp": timestamp,
            "error": str(e),
        }

    write_metric(
        measurement="icmp",
        tags={"host": host},
        fields={
            "is_alive": int(result["is_alive"]),
            "latency_ms": result.get("latency_ms") or 0.0,
            "packet_loss_pct": result.get("packet_loss_pct", 100.0),
        },
    )

    return result
