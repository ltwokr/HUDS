from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

# Simple storage approach:
# - Store data in the api directory as static JSON files
# - These files are deployed with the app and readable by serverless functions
# - Writes go to /tmp (ephemeral) but that's fine since we re-scrape daily via cron

# Path to store JSON files
API_DIR = Path(__file__).parent.parent  # /api directory
DATA_DIR = API_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

WEEK_FILE = DATA_DIR / "week.json"
STATUS_FILE = DATA_DIR / "status.json"

def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def read_json_file(filepath: Path) -> Optional[dict]:
    if not filepath.exists():
        return None
    try:
        with filepath.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json_file(filepath: Path, data: dict) -> None:
    _ensure_dir(filepath)
    try:
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # If we can't write to the api/data directory (on Vercel), write to /tmp
        tmp_path = Path("/tmp") / filepath.name
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def write_local_raw_html(html: str, date_key: str) -> None:
    """For local debugging only; keeps a small cache of raw HTML."""
    try:
        path = DATA_DIR / "raw" / f"{date_key}.html"
        _ensure_dir(path)
        with path.open("w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass  # Ignore errors writing debug HTML

def read_week() -> Optional[dict]:
    return read_json_file(WEEK_FILE)

def write_week(data: dict) -> None:
    write_json_file(WEEK_FILE, data)

def read_status() -> Optional[dict]:
    return read_json_file(STATUS_FILE)

def write_status(data: dict) -> None:
    write_json_file(STATUS_FILE, data)
