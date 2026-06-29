import os

import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")


def load_config() -> dict:
    from auth.db import get_all_devices
    devices = get_all_devices()
    if devices:
        return {"devices": devices}
    # Fallback: DB has no devices yet (first run before migration)
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {"devices": []}
