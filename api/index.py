from __future__ import annotations

import os
from fastapi import FastAPI, Response, Request, status
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Any, Dict
import json

from .common import storage
from .common import huds_scraper as scraper
from .common.week_utils import week_bounds_iso, iso_today, now_ny

app = FastAPI()
templates = Jinja2Templates(directory="api/templates")

ALLOWED_ORDER = ["soups", "entrees", "starch_potatoes", "vegetables", "delish", "desserts"]
LABELS = {
    "soups": "Soups",
    "entrees": "Entrées",
    "starch_potatoes": "Starch & Potatoes",
    "vegetables": "Vegetables",
    "delish": "Delish",
    "desserts": "Dessert",
}

class ErrorOut(BaseModel):
    error: str

def _render_day_cell(day_iso: str, day_data: Dict[str, Any]) -> str:
    # Two sections: Lunch and Dinner
    def render_meal(title: str, meal: Dict[str, Any], include_delish: bool) -> str:
        parts = [f"<div class='mb-3'><div class='text-lg font-semibold mb-2'>{title}</div>"]
        for key in ALLOWED_ORDER:
            if key == "delish" and not include_delish:
                continue
            items = meal.get(key) or []
            # Sunday entree override (Lunch only)
            if key == "entrees":
                try:
                    from datetime import date
                    if date.fromisoformat(day_iso).weekday() == 6 and title.lower() == "lunch":
                        items = ["Sunday Brunch"]
                except Exception:
                    pass
            # Dessert customization: show only first item.
            # Sunday override applies ONLY to Dinner.
            if key == "desserts":
                is_sunday = False
                try:
                    from datetime import date
                    is_sunday = date.fromisoformat(day_iso).weekday() == 6  # Monday=0 ... Sunday=6
                except Exception:
                    pass
                if is_sunday and title.lower() == "dinner":
                    items = ["Sunday Sundae!"]
                elif items:
                    items = items[:1]
            if not items:
                continue
            parts.append(f"<div class='text-sm text-gray-500 mb-1'>{LABELS[key]}</div>")
            parts.append("<div class='mb-2'>")
            # Choose very light pastel background per category
            bg_cls = {
                "soups": "bg-blue-50",
                "entrees": "bg-red-50",
                "starch_potatoes": "bg-yellow-50",
                "vegetables": "bg-green-50",
                "desserts": "bg-purple-50",
            }.get(key, "bg-gray-100")
            for it in items:
                # Use block-level divs so each item is on its own line
                parts.append(f"<div class='px-2 py-1 text-sm {bg_cls} rounded-lg mb-2'>{it}</div>")
            parts.append("</div>")
        if all(not (meal.get(k) or []) for k in (["soups","entrees","starch_potatoes","vegetables","desserts"] + (["delish"] if include_delish else []))):
            parts.append("<div class='text-sm text-gray-400'>No items.</div>")
        parts.append("</div>")
        return "\n".join(parts)

    lunch = day_data.get("lunch", {})
    dinner = day_data.get("dinner", {})

    dt_title = day_iso
    try:
        dt_disp = day_iso
        dt_obj = __import__("datetime").date.fromisoformat(day_iso)
        dt_title = dt_obj.strftime("%A %b %-d") if os.name != "nt" else dt_obj.strftime("%A %b %d").lstrip("0")
    except Exception:
        pass

    inner = [
        f"<div class='text-xl font-bold mb-4'>{dt_title}</div>",
        render_meal("Lunch", lunch, include_delish=True),
        render_meal("Dinner", dinner, include_delish=False),
    ]
    return f"<div class='border rounded-2xl p-3'>{''.join(inner)}</div>"

def _render_week_grid(data: Dict[str, Any]) -> str:
    # Grid Monday->Sunday
    days = list(data.get("meals", {}).keys())
    days_sorted = sorted(days)  # ISO sorts ascending Mon..Sun
    cells = []
    for d in days_sorted:
        cells.append(_render_day_cell(d, data["meals"][d]))
    # Responsive grid: 1col on mobile, 2 cols sm, 3 cols md, 4 lg
    return f"""
    <div id="grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      {''.join(cells)}
    </div>
    """

def _status_banner():
    status_json = storage.read_status() or {}
    last_ok = status_json.get("last_scrape_ok", False)
    err = status_json.get("error")
    if err == "parse_failed":
        return {"kind": "error", "text": "HUDS menu format changed—scrape failed today."}
    if not last_ok and err:
        return {"kind": "error", "text": "HUDS fetch failed—showing last known menu (may be stale)."}
    # Subtle stale banner if week is old
    week_json = storage.read_week()
    if week_json:
        # If generated_at older than 48h, show stale
        try:
            from dateutil import parser
            gen = parser.isoparse(week_json.get("generated_at"))
            age_hours = (now_ny() - gen.astimezone(now_ny().tzinfo)).total_seconds() / 3600
            if age_hours > 48:
                return {"kind": "warn", "text": "Data may be stale—last successful scrape was >48h ago."}
        except Exception:
            pass
    return None

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    # On first load, attempt to use cached week; if none, try scrape
    week_json = storage.read_week()
    if not week_json:
        try:
            week_json = scraper.scrape_and_store()
        except Exception:
            week_json = {
                "week_start": week_bounds_iso()[0],
                "week_end": week_bounds_iso()[1],
                "generated_at": "",
                "meals": {}
            }
    grid_html = _render_week_grid(week_json)
    banner = _status_banner()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "grid": grid_html, "banner": banner}
    )

@app.get("/api/week")
def api_week():
    week_json = storage.read_week()
    if not week_json:
        return JSONResponse({"error": "parse_failed"}, status_code=500)
    return JSONResponse(week_json)

@app.get("/api/today")
def api_today():
    week_json = storage.read_week()
    if not week_json:
        return JSONResponse({"error": "parse_failed"}, status_code=500)
    today = iso_today()
    day = week_json.get("meals", {}).get(today)
    if not day:
        # Return empty structure for today
        day = {"lunch": {k: [] for k in ["soups","entrees","starch_potatoes","vegetables","delish","desserts"]},
               "dinner": {k: [] for k in ["soups","entrees","starch_potatoes","vegetables","desserts"]}}
    return JSONResponse(day)

@app.post("/api/refresh")
def api_refresh():
    try:
        data = scraper.scrape_and_store()
        return JSONResponse({"ok": True, "updated_at": data.get("generated_at")})
    except scraper.ScrapeError as e:
        code = 503 if e.kind == "fetch_failed" else 500
        return JSONResponse({"error": e.kind}, status_code=code)

@app.get("/api/health")
def api_health():
    st = storage.read_status() or {}
    ok = bool(st.get("last_scrape_ok"))
    return JSONResponse({"ok": ok})

# HTML fragment to refresh the grid via HTMX after a successful scrape
@app.get("/api/week_fragment", response_class=HTMLResponse)
def api_week_fragment():
    week_json = storage.read_week()
    if not week_json:
        # return an error banner grid
        return HTMLResponse("<div id='grid' class='text-red-700'>Failed to load week.</div>", status_code=500)
    return HTMLResponse(_render_week_grid(week_json))

@app.get("/api/cron")
def api_cron():
    """Triggered by Vercel Cron at 12:00 UTC (7:00 AM America/New_York standard time)."""
    # Ensure we have the latest week cached
    try:
        if not storage.read_week():
            scraper.scrape_and_store()
    except Exception:
        pass
    # Send email
    from .common.emailer import send_daily_email
    day = api_today().body
    day_json = json.loads(day.decode("utf-8"))
    res = send_daily_email(day_json)
    return JSONResponse({"ok": True, "email": res})
