import datetime
import socket
import time


# Common ports by device type — used as a reference; callers decide which to probe.
DEVICE_PORTS = {
    "mikrotik":      [8291, 22, 80],
    "unifi":         [8080, 8443, 22],
    "windows_server": [3389, 445, 80, 443],
    "linux_server":  [22, 80, 443],
    "cisco":         [22, 23, 161],
}


def check_port(host: str, port: int, timeout: float = 3.0) -> dict:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            response_time_ms = round((time.monotonic() - start) * 1000, 2)
            return {
                "host": host,
                "port": port,
                "is_open": True,
                "response_time_ms": response_time_ms,
                "timestamp": timestamp,
            }
    except socket.timeout:
        return {
            "host": host,
            "port": port,
            "is_open": False,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": "timeout",
        }
    except ConnectionRefusedError:
        return {
            "host": host,
            "port": port,
            "is_open": False,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": "connection_refused",
        }
    except OSError as e:
        return {
            "host": host,
            "port": port,
            "is_open": False,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": str(e),
        }
