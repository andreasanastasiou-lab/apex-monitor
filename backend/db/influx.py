import os
from influxdb_client import InfluxDBClient

# All connection details come from environment variables — never hardcoded
_client: InfluxDBClient | None = None


def get_client() -> InfluxDBClient:
    global _client
    if _client is None:
        _client = InfluxDBClient(
            url=os.environ["INFLUXDB_URL"],
            token=os.environ["INFLUXDB_TOKEN"],
            org=os.environ["INFLUXDB_ORG"],
        )
    return _client


def write_point(measurement: str, tags: dict, fields: dict):
    # TODO: implement point write using write_api
    raise NotImplementedError


def query(flux_query: str):
    # TODO: implement Flux query execution
    raise NotImplementedError
