import hashlib
import json
import os
from src.config import CACHE_DIR

os.makedirs(CACHE_DIR, exist_ok=True)


def make_key(*parts) -> str:
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str):
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def set(key: str, value: dict) -> None:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    with open(path, "w") as f:
        json.dump(value, f, indent=2)
