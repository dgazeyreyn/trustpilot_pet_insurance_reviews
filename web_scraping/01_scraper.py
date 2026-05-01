import json
import yaml
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime
from pathlib import Path
import time
import random

DATA_DIR = Path("incremental")
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/json",
    "Connection": "keep-alive",
}

BASE_DELAY = (2, 5)  # randomized delay range

# ---------------------------
# SESSION
# ---------------------------
session = requests.Session()
session.headers.update(HEADERS)

# ---------------------------
# HELPERS
# ---------------------------
def parse_iso_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def fetch_with_retries(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=15)

            if response.status_code == 200:
                return response

            elif response.status_code in (403, 429):
                wait = (attempt + 1) * random.uniform(5, 15)
                print(f"  ⚠️ Blocked ({response.status_code}). Retrying in {wait:.1f}s")
                time.sleep(wait)

            else:
                response.raise_for_status()

        except requests.RequestException as e:
            wait = (attempt + 1) * 5
            print(f"  ⚠️ Request error: {e}. Retrying in {wait}s")
            time.sleep(wait)

    return None

def get_reviews_from_page(url: str) -> list:
    response = fetch_with_retries(url)

    if not response:
        return []

    soup = bs(response.content, "html.parser")
    results = soup.find(id="__NEXT_DATA__")

    if not results:
        return []

    json_object = json.loads(results.contents[0])

    try:
        return json_object["props"]["pageProps"]["reviews"]
    except KeyError:
        return []

# ---------------------------
# SCRAPE ONE PROVIDER
# ---------------------------
def scrape_provider(provider_key, provider_cfg):
    base_url = provider_cfg["url"]
    last_collected = parse_iso_utc(provider_cfg["last_collected"])

    print(f"\n▶ Scraping {provider_cfg['name']}")

    page = 1
    rows = []
    stop_scraping = False

    while True:
        page_url = f"{base_url}?page={page}"
        print(f"  Page {page}")

        reviews = get_reviews_from_page(page_url)
        if not reviews:
            print("  ⚠️ No reviews returned (possible block or end).")
            break

        for r in reviews:
            published_raw = r["dates"]["publishedDate"]
            published_dt = parse_iso_utc(published_raw)

            if published_dt <= last_collected:
                stop_scraping = True
                break

            rows.append({
                "provider": provider_key,
                "review_id": r["id"],
                "rating": r["rating"],
                "title": r["title"],
                "text": r["text"],
                "likes": r["likes"],
                "filtered": r["filtered"],
                "pending": r["isPending"],
                "experienced_date": r["dates"]["experiencedDate"],
                "published_date": published_raw,
                "source_url": page_url,
            })

        if stop_scraping:
            print("  Reached previously collected reviews.")
            break

        page += 1

        # Random delay between requests
        delay = random.uniform(*BASE_DELAY)
        print(f"  Sleeping {delay:.2f}s")
        time.sleep(delay)

        # Occasional longer pause (every ~5 pages)
        if page % 5 == 0:
            long_pause = random.uniform(10, 20)
            print(f"  Taking a longer pause: {long_pause:.1f}s")
            time.sleep(long_pause)

    if not rows:
        print("  No new reviews found.")
        return None

    df = pd.DataFrame(rows)
    df.drop_duplicates(subset=["review_id"], inplace=True)

    output_path = DATA_DIR / f"{provider_key}_reviews_incremental.csv"
    df.to_csv(output_path, index=False)

    print(f"  Saved {len(df)} new reviews → {output_path}")
    return df

# ---------------------------
# MAIN
# ---------------------------
def main():
    with open("web_scraping/providers.yaml", "r") as f:
        providers = yaml.safe_load(f)

    for provider_key, provider_cfg in providers.items():
        try:
            scrape_provider(provider_key, provider_cfg)
        except Exception as e:
            print(f"✖ Error scraping {provider_key}: {e}")

if __name__ == "__main__":
    main()