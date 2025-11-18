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

def _render_day_cell(day_iso: str, day_data: Dict[str, Any], is_today: bool = False) -> str:
    """Render a single day card with 3-column layout: Entrees, Veg+Starch, Soups+Dessert."""
    from datetime import date
    
    lunch = day_data.get("lunch", {})
    dinner = day_data.get("dinner", {})
    
    # Get day title
    dt_title = day_iso
    day_name = ""
    try:
        dt_obj = date.fromisoformat(day_iso)
        day_name = dt_obj.strftime("%A")
        dt_title = dt_obj.strftime("%b %-d") if os.name != "nt" else dt_obj.strftime("%b %d").lstrip("0")
    except Exception:
        pass
    
    # Check if Sunday for special overrides
    is_sunday = False
    try:
        is_sunday = date.fromisoformat(day_iso).weekday() == 6
    except Exception:
        pass
    
    # Helper to render a column section
    def render_column(title: str, categories: list, meal_type: str) -> str:
        col_parts = [f"<div class='text-sm font-semibold text-gray-700 mb-2'>{title}</div>"]
        has_content = False
        
        for cat in categories:
            items = lunch.get(cat, []) if meal_type == "lunch" else dinner.get(cat, [])
            
            # Filter out Grilled Chicken Breast from lunch entrees (always available)
            if cat == "entrees" and meal_type == "lunch":
                items = [it for it in items if "grilled chicken breast" not in it.lower()]
            
            # Apply overrides
            if cat == "entrees" and is_sunday and meal_type == "lunch":
                items = ["Sunday Brunch"]
            if cat == "desserts":
                if is_sunday and meal_type == "dinner":
                    items = ["Sunday Sundae!"]
                elif items:
                    items = items[:1]
            
            if not items:
                continue
            
            has_content = True
            bg_cls = {
                "soups": "bg-blue-50",
                "entrees": "bg-red-50",
                "starch_potatoes": "bg-yellow-50",
                "vegetables": "bg-green-50",
                "desserts": "bg-purple-50",
            }.get(cat, "bg-gray-100")
            
            for it in items:
                col_parts.append(f"<div class='px-2 py-1 text-xs {bg_cls} rounded mb-1'>{it}</div>")
        
        if not has_content:
            col_parts.append("<div class='text-xs text-gray-400'>—</div>")
        
        return "".join(col_parts)
    
    # Build 3 columns for Lunch
    lunch_col1 = render_column("Entrées", ["entrees"], "lunch")
    lunch_col2 = render_column("Veg/Starch", ["vegetables", "starch_potatoes"], "lunch")
    lunch_col3 = render_column("Soup/Dessert", ["soups", "desserts"], "lunch")
    
    # Build 3 columns for Dinner
    dinner_col1 = render_column("Entrées", ["entrees"], "dinner")
    dinner_col2 = render_column("Veg/Starch", ["vegetables", "starch_potatoes"], "dinner")
    dinner_col3 = render_column("Soup/Dessert", ["soups", "desserts"], "dinner")
    
    # Today indicator styling
    today_ring = "ring-4 ring-blue-400" if is_today else ""
    today_badge = "<div class='absolute top-2 right-2 bg-blue-500 text-white text-xs px-2 py-1 rounded-full'>Today</div>" if is_today else ""
    
    return f"""
    <div class='snap-start md:snap-none shrink-0 w-full md:w-full h-auto md:h-full relative {today_ring} rounded-2xl bg-white border p-4 flex flex-col mb-4 md:mb-0'>
      {today_badge}
      <div class='text-center mb-4'>
        <div class='text-2xl font-bold'>{day_name}</div>
        <div class='text-sm text-gray-500'>{dt_title}</div>
      </div>
      
      <div class='flex-1 grid grid-rows-2 gap-4'>
        <!-- Lunch Row -->
        <div class='border-b pb-2'>
          <div class='text-base font-semibold mb-2'>Lunch</div>
          <div class='grid grid-cols-3 gap-2 text-xs items-start'>
            <div>{lunch_col1}</div>
            <div>{lunch_col2}</div>
            <div>{lunch_col3}</div>
          </div>
        </div>
        
        <!-- Dinner Row -->
        <div>
          <div class='text-base font-semibold mb-2'>Dinner</div>
          <div class='grid grid-cols-3 gap-2 text-xs items-start'>
            <div>{dinner_col1}</div>
            <div>{dinner_col2}</div>
            <div>{dinner_col3}</div>
          </div>
        </div>
      </div>
    </div>
    """

def _render_week_grid(data: Dict[str, Any]) -> str:
    """Horizontal scrollable week view with snap-to-scroll on desktop, vertical stack on mobile."""
    days = list(data.get("meals", {}).keys())
    days_sorted = sorted(days)
    today = iso_today()
    
    cells = []
    for d in days_sorted:
        is_today = (d == today)
        cells.append(_render_day_cell(d, data["meals"][d], is_today))
    
    return f"""
    <div id="grid" class="flex flex-col md:flex-row overflow-y-auto md:overflow-x-auto md:overflow-y-hidden snap-y md:snap-x snap-mandatory gap-4 md:h-[calc(100vh-12rem)] pb-4" style="scroll-behavior: smooth;">
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
