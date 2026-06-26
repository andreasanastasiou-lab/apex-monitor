import logging
import os

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)

# Lazy singleton — initialised on first use so load_dotenv() in main.py runs first.
_client: InfluxDBClient | None = None


def get_client() -> InfluxDBClient:
    global _client
    if _client is None:
        _client = InfluxDBClient(
            url=os.environ.get("INFLUXDB_URL", ""),
            token=os.environ.get("INFLUXDB_TOKEN", ""),
            org=os.environ.get("INFLUXDB_ORG", ""),
        )
    return _client


def write_metric(measurement: str, tags: dict, fields: dict) -> bool:
    try:
        client = get_client()
        point = Point(measurement)
        for key, value in tags.items():
            point = point.tag(key, value)
        for key, value in fields.items():
            point = point.field(key, value)

        write_api = client.write_api(write_options=SYNCHRONOUS)
        write_api.write(
            bucket=os.environ.get("INFLUXDB_BUCKET", ""),
            org=os.environ.get("INFLUXDB_ORG", ""),
            record=point,
        )
        return True
    except Exception as e:
        logger.error("InfluxDB write_metric failed for '%s': %s", measurement, e)
        return False


def test_connection() -> bool:
    try:
        return get_client().ping()
    except Exception as e:
        logger.error("InfluxDB connection test failed: %s", e)
        return False
