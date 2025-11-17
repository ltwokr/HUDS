from __future__ import annotations

import re
import datetime as dt
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup, Tag
from urllib.parse import quote_plus

from .week_utils import week_bounds_iso, week_date_list, format_dtdate_param, utc_now_iso, NY_TZ
from . import storage

HUDS_BASE_URL = (
    "https://www.foodpro.huds.harvard.edu/foodpro/shtmenu.aspx"
    "?sName=HARVARD+UNIVERSITY+DINING+SERVICES"
    "&locationNum=38&locationName=Dining+Hall&naFlag=1"
    "&WeeksMenus=This+Week%27s+Menus&myaction=read&dtdate={dtdate}"
)

# Fuzzy station mapping; keys are our normalized buckets
FUZZY_MAP = {
    "soups": {"soup", "soups"},
    "entrees": {"entrée", "entrees", "entrée(s)", "main entrée", "main entrees", "main course", "entrée(s)"},
    "starch_potatoes": {"starch and potatoes", "starch & potatoes", "starches", "potato", "potatoes"},
    "vegetables": {"vegetable", "vegetables", "veg"},
    "delish": {"delish"},
    "desserts": {"dessert", "desserts", "sweets"},
}
BUCKET_ORDER = ["soups", "entrees", "starch_potatoes", "vegetables", "delish", "desserts"]

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

class ScrapeError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind

def _normalize_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    # Remove allergens/calories/parentheticals like "(contains ...)" "(GF)" "(120 cal)"
    s = re.sub(r"\((?:contains|gf|v|vegan|vegetarian|halal|kosher|kcal|cal|soy|milk|egg|wheat|gluten|tree nuts|peanut|shellfish|fish|sesame)[^)]*\)", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip(" -•·,")
    return s

def _classify_category(cat_raw: str) -> Optional[str]:
    """Map a HUDS category label to one of our normalized buckets.
    The incoming text usually looks like "-- Salad Bar --". We strip dashes and lowercase.
    We only include main meal components (soups, entrees, sides, desserts).
    """
    if not cat_raw:
        return None
    cat = cat_raw.lower()
    # remove leading/trailing dashes and spaces
    cat = re.sub(r"^-+|-+$", "", cat).strip()
    cat = cat.replace("--", "").strip()
    
    # Only include these specific categories with exact matches:
    
    # Soups - only "Today's Soup"
    if cat == "today's soup":
        return "soups"
    
    # Entrees - main dishes only
    if cat in ["entrees", "entrée", "veg,vegan"]:
        return "entrees"
    
    # Starch & Potatoes - only the exact category name
    if cat == "starch and potatoes":
        return "starch_potatoes"
    
    # Vegetables - only the exact "Vegetables" category
    if cat == "vegetables":
        return "vegetables"
    
    # Desserts
    if cat == "desserts":
        return "desserts"
    
    # Delish smoothies (lunch only, filtered out for dinner elsewhere)
    if cat == "delish":
        return "delish"
    
    # Ignore everything else including:
    # - Brown Rice Station, Whole Grain Pasta Bar (separate stations)
    # - Plant Protein (separate category)
    # - Salad Bar, Deli, Grill, Halal, Breakfast items, etc.
    return None

def _init_meal_bucket(include_delish: bool) -> Dict[str, List[str]]:
    meal = {k: [] for k in BUCKET_ORDER}
    if not include_delish:
        meal["delish"] = []
    return meal

def _dedupe_preserve(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def fetch_day_html(day: dt.date) -> str:
    dtdate = format_dtdate_param(day)
    url = HUDS_BASE_URL.format(dtdate=quote_plus(dtdate))
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ScrapeError("fetch_failed", f"Failed to fetch HUDS page for {day}: {e}") from e
    storage.write_local_raw_html(r.text, date_key=dtdate.replace("/", "-"))
    return r.text

def _extract_recipe_flags(tr_tag: Tag) -> List[str]:
    flags: List[str] = []
    if not tr_tag:
        return flags
    for img in tr_tag.find_all("img"):
        src = (img.get("src") or "").lower()
        if "vgn" in src:
            flags.append("vegan")
        elif "veg" in src:
            flags.append("vegetarian")
        elif "hal" in src:
            flags.append("halal")
    # dedupe
    out = []
    for f in flags:
        if f not in out:
            out.append(f)
    return out

def _parse_meal_container(meal_td: Tag, meal_name: str) -> Dict[str, List[str]]:
    """Parse one <td> column that corresponds to a meal (Breakfast/Lunch/Dinner)."""
    meal_data = {k: [] for k in BUCKET_ORDER}
    
    # Find all category headers and recipe divs
    all_elements = meal_td.find_all("div", class_=["shortmenucats", "shortmenurecipes"])
    
    current_bucket = None
    for elem in all_elements:
        classes = elem.get("class", [])
        if "shortmenucats" in classes:
            # This is a category header
            cat_text = elem.get_text(" ", strip=True)
            current_bucket = _classify_category(cat_text)
        elif "shortmenurecipes" in classes and current_bucket:
            # This is a recipe under the current category
            dish_raw = _normalize_text(elem.get_text(" ", strip=True))
            if not dish_raw:
                continue
                
            # Find parent tr for flags
            tr_parent = elem
            for _ in range(6):
                if tr_parent and isinstance(tr_parent, Tag) and tr_parent.name == "tr":
                    break
                tr_parent = tr_parent.parent if tr_parent else None
            flags = _extract_recipe_flags(tr_parent)
            
            # Don't append dietary flags - just use the dish name as-is
            dish = dish_raw
            meal_data[current_bucket].append(dish)
    
    # Dedupe & clean
    for k in meal_data:
        meal_data[k] = _dedupe_preserve(meal_data[k])
    # Dinner should not include delish bucket items per original interface
    if meal_name.lower() == "dinner":
        meal_data["delish"] = []
    return meal_data

def parse_day(html: str) -> Dict[str, Dict[str, List[str]]]:
    """Parse a single day's HTML (containing Breakfast/Lunch/Dinner columns)."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Find all <td valign="top" width="30%"> which are the main meal columns
    meal_columns = soup.find_all("td", {"valign": "top", "width": "30%"})
    
    meal_tds: Dict[str, Tag] = {}
    for td in meal_columns:
        # Look for the meal name anchor inside this column
        meal_anchor = td.find("a", string=lambda text: text and text.strip().lower() in ["breakfast", "lunch", "dinner"])
        if meal_anchor:
            meal_name = meal_anchor.get_text(strip=True).lower()
            meal_tds[meal_name] = td
    
    # Build structure (we only persist lunch/dinner to stay compatible)
    lunch = _parse_meal_container(meal_tds.get("lunch", Tag(name="div")), "Lunch") if meal_tds.get("lunch") else _init_meal_bucket(True)
    dinner = _parse_meal_container(meal_tds.get("dinner", Tag(name="div")), "Dinner") if meal_tds.get("dinner") else _init_meal_bucket(False)
    return {"lunch": lunch, "dinner": dinner}

def parse_week(fetch_html_for_day=fetch_day_html) -> dict:
    """Fetch and parse each day of the current week individually.
    We no longer rely on a single weekly HTML; HUDS daily pages are more stable.
    """
    dates = week_date_list()
    s_iso, e_iso = week_bounds_iso()
    out = {
        "week_start": s_iso,
        "week_end": e_iso,
        "generated_at": utc_now_iso(),
        "meals": {}
    }
    any_item = False
    for d in dates:
        try:
            html = fetch_html_for_day(d)
            day_data = parse_day(html)
        except ScrapeError:
            day_data = {"lunch": _init_meal_bucket(True), "dinner": _init_meal_bucket(False)}
        # Track if we have at least one dish
        if any(day_data[meal][bucket] for meal in ("lunch", "dinner") for bucket in BUCKET_ORDER):
            any_item = True
        out["meals"][d.isoformat()] = day_data
    if not any_item:
        raise ScrapeError("parse_failed", "HUDS menu format changed (no dishes found)")
    return out

def scrape_and_store() -> dict:
    """Fetch all daily HUDS pages for the current week, parse, persist JSON + status."""
    try:
        data = parse_week()
        storage.write_week(data)
        storage.write_status({
            "last_scrape_ok": True,
            "error": None,
            "updated_at": utc_now_iso()
        })
        return data
    except ScrapeError as e:
        storage.write_status({
            "last_scrape_ok": False,
            "error": e.kind,
            "updated_at": utc_now_iso()
        })
        raise
