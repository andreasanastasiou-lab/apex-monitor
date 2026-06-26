import datetime
import socket
import time

import paramiko


def ssh_check(
    host: str,
    username: str,
    password: str = None,
    key_path: str = None,
    command: str = "echo ok",
) -> dict:
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start = time.monotonic()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "username": username,
            "timeout": 10,
            "look_for_keys": False,
            "allow_agent": False,
        }

        if key_path:
            connect_kwargs["key_filename"] = key_path
        elif password:
            connect_kwargs["password"] = password
        else:
            raise ValueError("Either key_path or password must be provided")

        client.connect(**connect_kwargs)

        _, stdout, _ = client.exec_command(command, timeout=10)
        response = stdout.read().decode().strip()
        response_time_ms = round((time.monotonic() - start) * 1000, 2)

        return {
            "host": host,
            "is_accessible": True,
            "response": response,
            "response_time_ms": response_time_ms,
            "timestamp": timestamp,
        }

    except paramiko.AuthenticationException:
        return {
            "host": host,
            "is_accessible": False,
            "response": None,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": "authentication_failed",
        }
    except paramiko.SSHException as e:
        return {
            "host": host,
            "is_accessible": False,
            "response": None,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": f"ssh_error: {e}",
        }
    except socket.timeout:
        return {
            "host": host,
            "is_accessible": False,
            "response": None,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": "timeout",
        }
    except OSError as e:
        return {
            "host": host,
            "is_accessible": False,
            "response": None,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": str(e),
        }
    finally:
        client.close()
