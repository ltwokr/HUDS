# Quick Setup Guide

## 1. Push to GitHub

```bash
# After creating repo on GitHub, run:
git remote add origin https://github.com/YOUR_USERNAME/HUDS.git
git branch -M main
git push -u origin main
```

## 2. Deploy to Vercel

1. Go to https://vercel.com/new
2. Import your GitHub repo
3. Add environment variables:
   - `RESEND_API_KEY`: Your Resend API key
   - `RECIPIENT_EMAILS`: Comma-separated email list
4. Deploy

## Updating Menus

**Option 1: Automatic**
- Cron job runs daily at 7 AM ET
- Re-scrapes all menus

**Option 2: Manual**
- Click "Refresh" button on website
- Immediately scrapes latest menus
- Data persists until next cold start (then reverts to committed data)

**Option 3: Commit Updated Data**
```bash
# Run scraper locally
python debug_full_pipeline.py

# Commit new data
git add api/data/week.json api/data/status.json
git commit -m "Update menu data"
git push

# Vercel auto-deploys with new data
```
