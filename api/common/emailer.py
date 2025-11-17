from __future__ import annotations

import os
from typing import Dict, List
from .week_utils import iso_today
import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RECIPIENT_EMAILS = [e.strip() for e in os.getenv("RECIPIENT_EMAILS", "").split(",") if e.strip()]

def _render_meal_section(title: str, meal: Dict[str, List[str]], include_delish: bool) -> str:
    order = ["soups", "entrees", "starch_potatoes", "vegetables"]
    if include_delish:
        order.append("delish")
    order.append("desserts")

    parts = [f"<h3 style='margin:12px 0 6px 0;'>{title}</h3>"]
    for key in order:
        items = meal.get(key) or []
        if not items:
            continue
        label = {
            "soups": "Soups",
            "entrees": "Entrées",
            "starch_potatoes": "Starch & Potatoes",
            "vegetables": "Vegetables",
            "delish": "Delish",
            "desserts": "Desserts",
        }[key]
        parts.append(f"<div style='font-weight:600;margin-top:6px'>{label}</div>")
        parts.append("<ul style='margin:4px 0 10px 18px;padding:0'>")
        for it in items:
            parts.append(f"<li>{it}</li>")
        parts.append("</ul>")
    return "\n".join(parts)

def send_daily_email(today_json: Dict) -> Dict:
    """Send HUDS Today email via Resend."""
    if not RESEND_API_KEY or not RECIPIENT_EMAILS:
        return {"sent": False, "reason": "missing_config"}

    resend.api_key = RESEND_API_KEY

    lunch = today_json.get("lunch", {})
    dinner = today_json.get("dinner", {})
    date_title = iso_today()

    html_parts = [
        f"<div style='font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;max-width:640px;margin:0 auto;padding:16px'>",
        f"<h2 style='margin:0 0 12px 0'>HUDS Today (Lunch & Dinner)</h2>",
        f"<div style='color:#666;margin-bottom:12px'>{date_title}</div>",
        _render_meal_section("Lunch", lunch, include_delish=True),
        _render_meal_section("Dinner", dinner, include_delish=False),
        "<div style='margin-top:16px;color:#888;font-size:12px'>Sent automatically at 7:00 AM America/New_York.</div>",
        "</div>"
    ]
    html = "\n".join(html_parts)

    payload = {
        "from": "HUDS Bot <noreply@huds-bot.example>",
        "to": RECIPIENT_EMAILS,
        "subject": "HUDS Today (Lunch & Dinner)",
        "html": html,
    }

    # Use resend python sdk
    try:
        sent = resend.Emails.send(payload)
        return {"sent": True, "res": sent}
    except Exception as e:
        return {"sent": False, "error": str(e)}
