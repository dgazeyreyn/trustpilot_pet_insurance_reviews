import json
import pandas as pd
import requests
from bs4 import BeautifulSoup as bs
from datetime import datetime, timezone

# ---------------------------
# CONFIG
# ---------------------------
BASE_URL = "https://www.trustpilot.com/review/www.akcpetinsurance.com"
LAST_COLLECTED = "2024-03-08T05:40:39.000Z"

last_collected_dt = datetime.fromisoformat(
    LAST_COLLECTED.replace("Z", "+00:00")
)

# ---------------------------
# HELPERS
# ---------------------------
def get_reviews_from_page(url):
    response = requests.get(url, timeout=15)
    response.raise_for_status()

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
# SCRAPING LOOP
# ---------------------------
page = 1
all_rows = []
stop_scraping = False

while True:
    url = f"{BASE_URL}?page={page}"
    print(f"Scraping page {page}")

    reviews = get_reviews_from_page(url)

    if not reviews:
        break

    for r in reviews:
        published_raw = r["dates"]["publishedDate"]
        published_dt = datetime.fromisoformat(
            published_raw.replace("Z", "+00:00")
        )

        # STOP CONDITION
        if published_dt <= last_collected_dt:
            stop_scraping = True
            break

        all_rows.append(
            {
                "id": r["id"],
                "filtered": r["filtered"],
                "pending": r["isPending"],
                "text": r["text"],
                "rating": r["rating"],
                "title": r["title"],
                "likes": r["likes"],
                "experienced": r["dates"]["experiencedDate"],
                "published": published_raw,
                "source": url,
            }
        )

    if stop_scraping:
        print("Reached previously collected reviews. Stopping.")
        break

    page += 1

# ---------------------------
# SAVE RESULTS
# ---------------------------
if all_rows:
    df_new = pd.DataFrame(all_rows)
    df_new.to_csv("akc_reviews_incremental.csv", index=False)
    print(f"Saved {len(df_new)} new reviews.")
else:
    print("No new reviews found.")
