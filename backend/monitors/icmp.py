import datetime

from icmplib import ping, NameLookupError, SocketPermissionError


def ping_device(host: str, count: int = 4, timeout: float = 2.0) -> dict:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        result = ping(host, count=count, interval=0.2, timeout=timeout, privileged=False)
        return {
            "host": host,
            "is_alive": result.is_alive,
            "latency_ms": round(result.avg_rtt, 2) if result.is_alive else None,
            "packet_loss_pct": round(result.packet_loss * 100, 1),
            "timestamp": timestamp,
        }
    except NameLookupError:
        return {
            "host": host,
            "is_alive": False,
            "latency_ms": None,
            "packet_loss_pct": 100.0,
            "timestamp": timestamp,
            "error": "dns_lookup_failed",
        }
    except SocketPermissionError:
        # Windows requires Administrator; Linux requires root or CAP_NET_RAW
        return {
            "host": host,
            "is_alive": False,
            "latency_ms": None,
            "packet_loss_pct": 100.0,
            "timestamp": timestamp,
            "error": "insufficient_privileges_run_as_admin",
        }
    except Exception as e:
        return {
            "host": host,
            "is_alive": False,
            "latency_ms": None,
            "packet_loss_pct": 100.0,
            "timestamp": timestamp,
            "error": str(e),
        }
