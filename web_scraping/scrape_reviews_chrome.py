import json
import time
from pathlib import Path

import pandas as pd
import yaml
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURATION
# ============================================================

CDP_URL = "http://127.0.0.1:9222"

DATA_DIR = Path("web_scraping/incremental")
DATA_DIR.mkdir(parents=True, exist_ok=True)

PROVIDERS_FILE = Path("web_scraping/providers.yaml")

# Conservative settings — reliability is more important than speed
WAIT_AFTER_CLICK = 5
WAIT_AFTER_REFRESH = 5
NEXT_DATA_TIMEOUT = 30_000
MAX_PAGES_PER_PROVIDER = 100


# ============================================================
# HELPERS
# ============================================================

def parse_iso_utc(ts: str):
    """Convert ISO timestamp to timezone-aware datetime."""
    from datetime import datetime

    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def extract_reviews(page):
    """
    Extract Trustpilot reviews from the currently loaded
    __NEXT_DATA__ element.
    """

    print("Looking for NEXT_DATA...")

    next_data = page.locator('script#__NEXT_DATA__')

    try:
        next_data.wait_for(
            state="attached",
            timeout=NEXT_DATA_TIMEOUT,
        )
    except Exception:
        print("⚠️ NEXT_DATA not found.")
        print(f"Page title: {page.title()}")
        print(f"Current URL: {page.url}")
        return []

    text = next_data.text_content()

    if not text:
        print("⚠️ NEXT_DATA element is empty.")
        return []

    print(f"✓ NEXT_DATA found: {len(text):,} characters")

    try:
        data = json.loads(text)

        reviews = data["props"]["pageProps"]["reviews"]

        print(f"✓ Reviews found: {len(reviews)}")

        return reviews

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"⚠️ Could not parse NEXT_DATA: {e}")
        return []


def find_next_page_control(page):
    """
    Find the visible Trustpilot 'Next page' control.
    """

    matches = page.get_by_text("Next page", exact=True)

    count = matches.count()

    print(f"Elements containing 'Next page': {count}")

    if count == 0:
        return None

    for i in range(count):
        candidate = matches.nth(i)

        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue

    return None


def save_reviews(provider_key, rows):
    """
    Save accumulated reviews to the provider's incremental CSV.
    """

    if not rows:
        print("No new reviews to save.")
        return

    df = pd.DataFrame(rows)

    df.drop_duplicates(
        subset=["review_id"],
        inplace=True,
    )

    output_path = (
        DATA_DIR
        / f"{provider_key}_reviews_incremental.csv"
    )

    df.to_csv(
        output_path,
        index=False,
    )

    print(
        f"💾 Saved {len(df)} accumulated reviews → "
        f"{output_path}"
    )


# ============================================================
# SCRAPE ONE PROVIDER
# ============================================================

def scrape_provider(page, provider_key, provider_cfg):
    """
    Scrape a provider using the existing Chrome session.

    Pagination strategy:

        Page 1
          ↓
        Extract NEXT_DATA
          ↓
        Click Next page
          ↓
        Wait
          ↓
        Refresh
          ↓
        Extract NEXT_DATA for next page
          ↓
        Repeat
    """

    base_url = provider_cfg["url"]

    last_collected = parse_iso_utc(
        provider_cfg["last_collected"]
    )

    print("\n" + "=" * 70)
    print(f"Provider: {provider_cfg['name']}")
    print(f"Base URL: {base_url}")
    print(f"Last collected: {last_collected.isoformat()}")
    print("=" * 70)

    # --------------------------------------------------------
    # Make sure we're on the provider's first page
    # --------------------------------------------------------

    print("\nNavigating to provider page:")
    print(base_url)

    page.goto(
        base_url,
        wait_until="domcontentloaded",
        timeout=60_000,
    )

    print("Waiting for Trustpilot page...")
    time.sleep(WAIT_AFTER_REFRESH)

    rows = []
    page_number = 1

    while page_number <= MAX_PAGES_PER_PROVIDER:

        print("\n" + "-" * 60)
        print(f"## PAGE {page_number}")
        print("-" * 60)

        print(f"Current URL: {page.url}")
        print(f"Page title: {page.title()}")

        # ----------------------------------------------------
        # Extract current page
        # ----------------------------------------------------

        reviews = extract_reviews(page)

        if not reviews:
            print(
                "⚠️ No reviews returned. "
                "Stopping provider."
            )
            break

        first_review_id = reviews[0]["id"]

        print(
            f"First review ID: {first_review_id}"
        )

        # ----------------------------------------------------
        # Process reviews
        # ----------------------------------------------------

        new_reviews_this_page = 0
        reached_last_collected = False

        for review in reviews:

            published_raw = (
                review["dates"]["publishedDate"]
            )

            published_dt = parse_iso_utc(
                published_raw
            )

            # Reviews are ordered newest → oldest.
            #
            # Once we reach the previously collected date,
            # everything after this point is already known.
            if published_dt <= last_collected:
                reached_last_collected = True
                break

            rows.append({
                "provider": provider_key,
                "review_id": review["id"],
                "rating": review["rating"],
                "title": review["title"],
                "text": review["text"],
                "likes": review["likes"],
                "filtered": review["filtered"],
                "pending": review["isPending"],
                "experienced_date": (
                    review["dates"]["experiencedDate"]
                ),
                "published_date": published_raw,
                "source_url": page.url,
            })

            new_reviews_this_page += 1

        print(
            f"New reviews from page {page_number}: "
            f"{new_reviews_this_page}"
        )

        # Save after every page so that progress isn't lost
        # if a later page encounters an issue.
        save_reviews(
            provider_key,
            rows,
        )

        # ----------------------------------------------------
        # Determine whether we're finished
        # ----------------------------------------------------

        if reached_last_collected:
            print(
                "\n✓ Reached previously collected reviews."
            )
            break

        # ----------------------------------------------------
        # Find Next Page
        # ----------------------------------------------------

        print("\nLooking for 'Next page' control...")

        next_button = find_next_page_control(page)

        if not next_button:
            print(
                "✓ No visible Next page control found."
            )
            print("✓ End of pagination.")
            break

        print("✓ Next page control found.")

        # Capture current first review ID so we can verify
        # that the next page actually contains different data.
        previous_first_review_id = first_review_id

        # ----------------------------------------------------
        # Click Next Page
        # ----------------------------------------------------

        print("\nClicking Next page...")

        try:
            next_button.click(
                timeout=30_000
            )
        except Exception as e:
            print(
                f"⚠️ Could not click Next page: {e}"
            )
            break

        print("✓ Click completed.")

        print(
            f"Waiting {WAIT_AFTER_CLICK} seconds "
            "for Trustpilot's pagination state to update..."
        )

        time.sleep(WAIT_AFTER_CLICK)

        print(f"URL after click: {page.url}")

        # ----------------------------------------------------
        # Refresh
        # ----------------------------------------------------

        print("\nRefreshing page...")

        try:
            page.reload(
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception as e:
            print(
                f"⚠️ Page refresh error: {e}"
            )
            break

        print("✓ Refresh completed.")

        print(
            f"Waiting {WAIT_AFTER_REFRESH} seconds "
            "for NEXT_DATA..."
        )

        time.sleep(WAIT_AFTER_REFRESH)

        print(f"URL after refresh: {page.url}")

        # ----------------------------------------------------
        # Validate that pagination actually advanced
        # ----------------------------------------------------

        print(
            "\nValidating that the new page contains "
            "different reviews..."
        )

        new_reviews = extract_reviews(page)

        if not new_reviews:
            print(
                "⚠️ Could not extract reviews after "
                "pagination refresh."
            )
            break

        new_first_review_id = new_reviews[0]["id"]

        print(
            f"Previous first review ID: "
            f"{previous_first_review_id}"
        )

        print(
            f"New first review ID:      "
            f"{new_first_review_id}"
        )

        if new_first_review_id == previous_first_review_id:

            print(
                "\n⚠️ Pagination validation failed."
            )
            print(
                "The refreshed page still appears to "
                "contain the previous page's reviews."
            )
            print(
                "Stopping rather than risking duplicate "
                "or incorrect data."
            )
            break

        print(
            "✓ Pagination validated — new reviews found."
        )

        # We've already extracted the next page above.
        # Keep those reviews in memory so we don't need
        # another extraction call at the top of the loop.
        reviews = new_reviews

        page_number += 1

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print(f"Provider complete: {provider_cfg['name']}")
    print(f"Pages processed: {page_number}")
    print(f"Total accumulated reviews: {len(rows)}")
    print("=" * 70)

    return rows


# ============================================================
# MAIN
# ============================================================

def main():

    print("Connecting to existing Chrome...")

    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(
            CDP_URL
        )

        print("✓ Connected to Chrome")

        contexts = browser.contexts

        if not contexts:
            raise RuntimeError(
                "No Chrome browser contexts found."
            )

        context = contexts[0]

        pages = context.pages

        print(f"Open pages: {len(pages)}")

        # ----------------------------------------------------
        # Find Trustpilot tab
        # ----------------------------------------------------

        trustpilot_page = None

        for page in pages:

            print(f"Tab: {page.url}")

            if "trustpilot.com/review/" in page.url:
                trustpilot_page = page
                break

        if not trustpilot_page:
            raise RuntimeError(
                "No Trustpilot review tab found."
            )

        page = trustpilot_page

        print("\n✓ Using Trustpilot tab:")
        print(page.url)

        # ----------------------------------------------------
        # Load provider configuration
        # ----------------------------------------------------

        with open(PROVIDERS_FILE, "r") as f:
            providers = yaml.safe_load(f)

        # ----------------------------------------------------
        # Process providers
        # ----------------------------------------------------

        # for provider_key, provider_cfg in providers.items():

        #     try:

        #         scrape_provider(
        #             page,
        #             provider_key,
        #             provider_cfg,
        #         )

        #     except Exception as e:

        #         print(
        #             f"\n✖ Error scraping "
        #             f"{provider_key}: {e}"
        #         )

        #         print(
        #             "Continuing to next provider..."
        #         )

        # print("\n✓ All providers processed.")
        
        # ----------------------------------------------------
        # Process ONE provider for initial testing
        # ----------------------------------------------------

        provider_key = "trupanion"
        provider_cfg = providers[provider_key]

        try:
            scrape_provider(
                page,
                provider_key,
                provider_cfg,
            )

        except Exception as e:

            print(
                f"\n✖ Error scraping "
                f"{provider_key}: {e}"
            )


if __name__ == "__main__":
    main()
