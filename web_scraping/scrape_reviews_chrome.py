import json
import random
import time

import pandas as pd
import yaml

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

PROVIDERS_FILE = SCRIPT_DIR / "providers.yaml"
DATA_DIR = SCRIPT_DIR / "incremental"

DATA_DIR.mkdir(exist_ok=True)

CDP_URL = "http://127.0.0.1:9222"

# Conservative delays between page navigations.
PAGE_DELAY = (3, 6)

# Longer pause every few pages.
LONG_PAUSE_EVERY = 5
LONG_PAUSE = (15, 30)

# Maximum time to wait for NEXT_DATA after navigation.
NEXT_DATA_TIMEOUT = 60_000


# ============================================================
# HELPERS
# ============================================================

def parse_iso_utc(ts: str) -> datetime:
    """Convert Trustpilot ISO timestamp to datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def extract_reviews(page) -> list:
    """
    Extract reviews directly from the browser DOM.

    We intentionally use page.evaluate() rather than
    Playwright's locator/wait_for_selector methods because
    test_chrome_connection.py has already demonstrated that
    NEXT_DATA exists in the Chrome session.
    """

    print("  Looking for NEXT_DATA in browser DOM...")

    # --------------------------------------------------------
    # Wait for NEXT_DATA to actually exist in the DOM.
    # --------------------------------------------------------

    try:
        page.wait_for_function(
            """
            () => document.getElementById("__NEXT_DATA__") !== null
            """,
            timeout=NEXT_DATA_TIMEOUT,
        )

    except Exception:
        print("  ⚠️ NEXT_DATA was not found.")
        print(f"  Page title: {page.title()}")
        print(f"  Current URL: {page.url}")

        # Additional diagnostic information.
        try:
            result = page.evaluate(
                """
                () => ({
                    readyState: document.readyState,
                    htmlLength: document.documentElement.outerHTML.length,
                    nextDataCount:
                        document.querySelectorAll("#__NEXT_DATA__").length
                })
                """
            )

            print(
                f"  Document readyState: "
                f"{result['readyState']}"
            )

            print(
                f"  HTML size: "
                f"{result['htmlLength']:,} characters"
            )

            print(
                f"  NEXT_DATA count: "
                f"{result['nextDataCount']}"
            )

        except Exception as e:
            print(
                f"  ⚠️ Could not collect diagnostics: {e}"
            )

        return []

    # --------------------------------------------------------
    # Extract the script contents directly from the DOM.
    # --------------------------------------------------------

    try:
        json_text = page.evaluate(
            """
            () => {
                const element =
                    document.getElementById("__NEXT_DATA__");

                return element
                    ? element.textContent
                    : null;
            }
            """
        )

    except Exception as e:
        print(
            f"  ⚠️ Could not read NEXT_DATA: {e}"
        )
        return []

    if not json_text:
        print("  ⚠️ NEXT_DATA exists but is empty.")
        return []

    print(
        f"  ✓ NEXT_DATA found: "
        f"{len(json_text):,} characters"
    )

    # --------------------------------------------------------
    # Parse JSON.
    # --------------------------------------------------------

    try:
        json_object = json.loads(json_text)

    except json.JSONDecodeError as e:
        print(
            f"  ⚠️ NEXT_DATA is not valid JSON: {e}"
        )
        return []

    # --------------------------------------------------------
    # Extract reviews.
    # --------------------------------------------------------

    try:
        reviews = (
            json_object
            ["props"]
            ["pageProps"]
            ["reviews"]
        )

    except KeyError as e:
        print(
            f"  ⚠️ Expected Trustpilot data structure "
            f"was not found. Missing key: {e}"
        )
        return []

    print(
        f"  ✓ Reviews found: {len(reviews)}"
    )

    return reviews

def save_reviews(
    rows: list,
    provider_key: str,
):
    """
    Save accumulated reviews to CSV.

    This is intentionally called after every successful page
    so progress is preserved if the scraper stops unexpectedly.
    """

    if not rows:
        return

    df = pd.DataFrame(rows)

    df.drop_duplicates(
        subset=["review_id"],
        inplace=True,
    )

    df.sort_values(
        by="published_date",
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
        f"  💾 Saved {len(df)} accumulated reviews "
        f"→ {output_path}"
    )


def navigate_with_chrome(page, url: str):
    """
    Ask the existing Chrome tab to navigate normally.

    We intentionally avoid Playwright's page.goto().
    """

    print(f"  Navigating Chrome to:")
    print(f"  {url}")

    page.evaluate(
        """url => {
            window.location.href = url;
        }""",
        url,
    )


# ============================================================
# SCRAPE f"{provider_key}
# ============================================================

def scrape_provider(page, provider_key, provider_cfg):

    base_url = provider_cfg["url"]

    last_collected = parse_iso_utc(
        provider_cfg["last_collected"]
    )

    print("\n" + "=" * 65)
    print("PROVIDER CONSERVATIVE SCRAPE")
    print("=" * 65)

    print(f"Provider: {provider_cfg['name']}")
    print(f"Base URL: {base_url}")
    print(
        f"Last collected: "
        f"{last_collected.isoformat()}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # The user must have already opened and verified the
    # Trustpilot page in Chrome.
    # --------------------------------------------------------

    print("\nChecking current Chrome tab...")

    print(f"Current URL: {page.url}")
    print(f"Page title: {page.title()}")

    if "trustpilot.com" not in page.url:
        raise RuntimeError(
            "The active Chrome tab is not a Trustpilot page.\n"
            "Please manually open the Trustpilot page in "
            "the dedicated Chrome session and wait until the "
            "actual reviews are visible."
        )

    print("✓ Trustpilot page detected.")

    # --------------------------------------------------------
    # PAGE 1
    # --------------------------------------------------------

    page_number = 1

    print("\n" + "-" * 65)
    print("PAGE 1")
    print("-" * 65)

    reviews = extract_reviews(page)

    if not reviews:
        raise RuntimeError(
            "Could not extract reviews from the currently "
            "displayed Trustpilot page."
        )

    rows = []

    stop_scraping = False

    for review in reviews:

        published_raw = (
            review["dates"]["publishedDate"]
        )

        published_dt = parse_iso_utc(
            published_raw
        )

        if published_dt <= last_collected:
            stop_scraping = True
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

    print(
        f"  New reviews from page 1: {len(rows)}"
    )

    save_reviews(rows, provider_key)

    if stop_scraping:
        print(
            "\n✓ Page 1 already reached "
            "the last collected date."
        )
        return

    # --------------------------------------------------------
    # SUBSEQUENT PAGES
    # --------------------------------------------------------

    while True:

        page_number += 1

        print("\n" + "-" * 65)
        print(f"PAGE {page_number}")
        print("-" * 65)

        page_url = (
            f"{base_url}?page={page_number}"
        )

        # Remember the current URL before navigating.
        previous_url = page.url

        navigate_with_chrome(
            page,
            page_url,
        )

        # Wait for Chrome to actually navigate.
        try:
            page.wait_for_function(
                """
                previousUrl => window.location.href !== previousUrl
                """,
                previous_url,
                timeout=NEXT_DATA_TIMEOUT,
            )

        except Exception:
            print(
                "  ⚠️ URL did not change within "
                f"{NEXT_DATA_TIMEOUT / 1000:.0f} seconds."
            )
            print(
                "  Current URL:",
                page.url,
            )
            break

        print(
            f"  Current URL: {page.url}"
        )

        # Extract reviews from the newly loaded page.
        reviews = extract_reviews(page)

        if not reviews:
            print(
                "  ⚠️ No reviews found. "
                "Stopping safely."
            )
            break

        page_rows = []

        for review in reviews:

            published_raw = (
                review["dates"]["publishedDate"]
            )

            published_dt = parse_iso_utc(
                published_raw
            )

            if published_dt <= last_collected:
                stop_scraping = True
                break

            page_rows.append({
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

        print(
            f"  New reviews from page {page_number}: "
            f"{len(page_rows)}"
        )

        rows.extend(page_rows)

        # Save immediately after every successful page.
        save_reviews(
            rows,
            provider_key,
        )

        if stop_scraping:
            print(
                "\n✓ Reached previously collected "
                "reviews."
            )
            break

        # ----------------------------------------------------
        # CONSERVATIVE DELAY
        # ----------------------------------------------------

        delay = random.uniform(*PAGE_DELAY)

        print(
            f"\n  Sleeping {delay:.1f}s..."
        )

        time.sleep(delay)

        if page_number % LONG_PAUSE_EVERY == 0:

            long_pause = random.uniform(
                *LONG_PAUSE
            )

            print(
                f"  Taking longer pause: "
                f"{long_pause:.1f}s..."
            )

            time.sleep(long_pause)

    print("\n" + "=" * 65)
    print(f"{provider_key} SCRAPE FINISHED")
    print("=" * 65)

    print(
        f"Total accumulated reviews: "
        f"{len(rows)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Load providers
    # --------------------------------------------------------

    with open(PROVIDERS_FILE, "r") as f:
        providers = yaml.safe_load(f)

    # --------------------------------------------------------
    # f"{provider_key} ONLY
    #
    # We intentionally do NOT loop through all providers yet.
    # --------------------------------------------------------

    provider_key = "trupanion"

    if provider_key not in providers:
        raise KeyError(
            f"Provider '{provider_key}' was not found "
            "in providers.yaml."
        )

    provider_cfg = providers[provider_key]

    # --------------------------------------------------------
    # Connect to existing Chrome
    # --------------------------------------------------------

    print("Connecting to existing Chrome...")

    with sync_playwright() as playwright:

        browser = playwright.chromium.connect_over_cdp(
            CDP_URL
        )

        print("✓ Connected to Chrome")

        if not browser.contexts:
            raise RuntimeError(
                "No Chrome browser contexts found."
            )

        context = browser.contexts[0]

        print(
            f"Open pages: {len(context.pages)}"
        )

        # ----------------------------------------------------
        # Find Trustpilot tab
        # ----------------------------------------------------

        trustpilot_page = None

        for existing_page in context.pages:

            print(
                f"  Tab: {existing_page.url}"
            )

            if "trustpilot.com" in existing_page.url:

                trustpilot_page = existing_page

                break

        if trustpilot_page is None:
            raise RuntimeError(
                "\nNo Trustpilot tab was found.\n\n"
                "Please:\n"
                "1. Open the dedicated Chrome session.\n"
                "2. Navigate to the Trustpilot page.\n"
                "3. Wait until the actual reviews are visible.\n"
                "4. Run this script again."
            )

        print(
            "\n✓ Using Trustpilot tab:"
        )

        print(
            f"  {trustpilot_page.url}"
        )

        # ----------------------------------------------------
        # Run f"{provider_key} scrape
        # ----------------------------------------------------

        scrape_provider(
            trustpilot_page,
            provider_key,
            provider_cfg,
        )

        print(
            "\n✓ Script complete."
        )


if __name__ == "__main__":
    main()
