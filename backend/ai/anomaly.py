import logging
import os

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from config import load_config
from db.influx import run_query

logger = logging.getLogger(__name__)

# Resolved once at import time: backend/ai/../models → backend/models/
_MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))

# Minimum historical points required before training a model.
_MIN_POINTS = 100

# Metrics that live in the "icmp" measurement vs "port_check".
_ICMP_METRICS = {"latency_ms", "packet_loss_pct", "is_alive"}


def _model_path(device_name: str, metric: str) -> str:
    safe = lambda s: s.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return os.path.join(_MODELS_DIR, f"{safe(device_name)}_{safe(metric)}.pkl")


def _host_for_device(device_name: str) -> str | None:
    for device in load_config().get("devices", []):
        if device.get("name") == device_name:
            return device.get("ip")
    return None


def train_baseline(device_name: str, metric: str) -> bool:
    """Query 7 days of InfluxDB data, fit an IsolationForest, save to disk.

    Returns True on success, False if there is not enough data or on any error.
    Never raises.
    """
    try:
        host = _host_for_device(device_name)
        if not host:
            logger.warning("train_baseline: device '%s' not found in config.yaml", device_name)
            return False

        measurement = "icmp" if metric in _ICMP_METRICS else "port_check"
        bucket = os.environ.get("INFLUXDB_BUCKET", "")

        flux = f"""
from(bucket: "{bucket}")
  |> range(start: -7d)
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => r["host"] == "{host}")
  |> filter(fn: (r) => r._field == "{metric}")
  |> keep(columns: ["_value"])
"""
        rows = run_query(flux)
        values = [r["_value"] for r in rows if r.get("_value") is not None]

        if len(values) < _MIN_POINTS:
            logger.info(
                "train_baseline: not enough data for %s/%s — %d points (need %d)",
                device_name, metric, len(values), _MIN_POINTS,
            )
            return False

        X = np.array(values, dtype=float).reshape(-1, 1)
        model = IsolationForest(contamination=0.05, random_state=42)
        model.fit(X)

        os.makedirs(_MODELS_DIR, exist_ok=True)
        joblib.dump(model, _model_path(device_name, metric))
        logger.info(
            "train_baseline: model saved for %s/%s (%d points)",
            device_name, metric, len(values),
        )
        return True

    except Exception as e:
        logger.error("train_baseline failed for %s/%s: %s", device_name, metric, e)
        return False


def detect_anomaly(device_name: str, metric: str, value: float) -> dict:
    """Score a single observation against the stored model.

    Returns a dict with is_anomaly, confidence, message.
    Returns a safe 'learning' dict if no model exists yet.
    Never raises.
    """
    path = _model_path(device_name, metric)

    if not os.path.exists(path):
        return {"is_anomaly": False, "confidence": 0.0, "message": "learning"}

    try:
        model = joblib.load(path)
        X = np.array([[float(value)]])
        prediction = model.predict(X)[0]   # 1 = normal, -1 = anomaly
        score = model.decision_function(X)[0]

        is_anomaly = prediction == -1
        # decision_function returns values roughly in [-0.5, 0.5].
        # Map abs(score) * 2 → [0, 1] so -0.5 ≈ confidence 1.0.
        confidence = round(min(1.0, abs(score) * 2.0), 3) if is_anomaly else 0.0
        message = f"anomaly (score {score:.3f})" if is_anomaly else "normal"

        return {
            "is_anomaly": bool(is_anomaly),
            "confidence": confidence,
            "message": message,
        }

    except Exception as e:
        logger.error("detect_anomaly failed for %s/%s: %s", device_name, metric, e)
        return {"is_anomaly": False, "confidence": 0.0, "message": f"error: {e}"}


def get_anomaly_status(device_name: str) -> dict:
    """Return which models exist for a device and whether it is still learning."""
    try:
        os.makedirs(_MODELS_DIR, exist_ok=True)
        safe_name = device_name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        prefix = safe_name + "_"
        files = [
            f for f in os.listdir(_MODELS_DIR)
            if f.startswith(prefix) and f.endswith(".pkl")
        ]
        metrics = [f[len(prefix):-4] for f in files]
        return {
            "has_model": bool(metrics),
            "metrics_monitored": metrics,
            "learning": not bool(metrics),
        }
    except Exception as e:
        logger.error("get_anomaly_status failed for %s: %s", device_name, e)
        return {"has_model": False, "metrics_monitored": [], "learning": True}
