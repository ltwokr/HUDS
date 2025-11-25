# HUDS Weekly Menu App

A minimal FastAPI app that scrapes Harvard Undergraduate Dining Services (HUDS) lunch and dinner menus and displays offerings in a simple, clean format. 

## Features

- Source: HUDS “This Week’s Menus” for upperclassmen houses.
- Meals: Lunch & Dinner.
- Categories included:
  1. Entrées
  2. Vegetables
  3. Starch & Potatoes
  4. Soups
  5. Desserts
- Minimal, responsive weekly grid (Mon → Sun) using Tailwind (CDN) and HTMX.
- Manual “Refresh” button to re-scrape.
- JSON APIs for week and today.
- Vercel Cron triggers daily email notification.

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
