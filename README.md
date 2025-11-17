# HUDS Weekly (Non-Quincy) — Lunch & Dinner Dashboard + Daily Email

A minimal FastAPI app that scrapes Harvard Undergraduate Dining Services (HUDS) “This Week’s Menus” for all **non-Quincy houses** (which share the same menu), **ignores breakfast**, and renders a clean, mobile-first weekly dashboard (Lunch + Dinner only) focused on selected stations. It also sends a **daily 7:00 AM America/New_York** email via **Resend** with today’s Lunch & Dinner.

## Features

- Source: HUDS “This Week’s Menus” for non-Quincy houses (Annenberg & Quincy excluded by URL/scope).
- Meals: Lunch & Dinner only (Breakfast ignored).
- Stations included (and order):
  1. **Soups**
  2. **Entrées**
  3. **Starch & Potatoes**
  4. **Vegetables**
  5. **Delish** (Lunch only)
  6. **Desserts**
- Minimal, responsive weekly grid (Mon → Sun) using Tailwind (CDN) and a touch of HTMX.
- Manual “Refresh now” button to re-scrape.
- JSON APIs for week and today.
- Vercel Cron triggers daily email at **12:00 UTC** (7:00 AM America/New_York in standard time).

## Quick Start (Local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set env vars (example)
export RESEND_API_KEY=your_resend_key
export RECIPIENT_EMAILS="you@example.com,roommate@example.com"

# Optional: enable local data directory (default /data)
mkdir -p ./data && export DATA_DIR=$PWD/data

# Run
uvicorn api.index:app --reload
