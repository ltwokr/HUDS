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
4. Deploy!

## How It Works (No Storage Issues!)

### The Solution
- **Pre-scraped data**: `api/data/week.json` is committed to git
- **Deployed with code**: Data files deploy alongside your app
- **Always readable**: Serverless functions can read the JSON files
- **Cron updates**: Daily job at 7 AM ET keeps data fresh
- **No database needed**: Simple file-based storage

### What Happens on Vercel

1. **Deploy**: Your code + data files go live
2. **Page load**: Reads `api/data/week.json` (always works!)
3. **Cron job**: Runs daily, scrapes fresh data
4. **Cron writes**: New data goes to `/tmp` (ephemeral)
5. **Manual refresh**: Click button to scrape immediately

### Why This Works

- ✅ Read operations: Always work (data in git repo)
- ✅ Write operations: Use `/tmp` (write succeeds, data lost on cold start)
- ✅ Fresh data: Cron job re-scrapes daily anyway
- ✅ No databases: No Postgres, Redis, or Blob Storage needed
- ✅ Simple deployment: Just git push and Vercel handles the rest

### Updating Menus

**Option 1: Automatic (Recommended)**
- Cron job runs daily at 7 AM ET
- Re-scrapes all menus
- You don't need to do anything!

**Option 2: Manual**
- Click "Refresh now" button on website
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

## Future Improvements (Optional)

If you want persistent writes without cron:
1. Add Vercel Postgres (free tier)
2. Update `storage.py` to use database
3. Remove data files from git

But current setup works great as-is! 🎉
