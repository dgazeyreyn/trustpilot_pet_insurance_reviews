import json
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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


def extract_page_number(url: str) -> int:
    """
    Extract the Trustpilot page number from a source URL.

    Examples:

        https://www.trustpilot.com/review/example.com
            -> 1

        https://www.trustpilot.com/review/example.com?page=58
            -> 58
    """

    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        if "page" in params:
            return int(params["page"][0])

    except (ValueError, TypeError):
        pass

    return 1


def get_incremental_path(provider_key: str) -> Path:
    """Return the provider's incremental CSV path."""

    return (
        DATA_DIR
        / f"{provider_key}_reviews_incremental.csv"
    )


def load_existing_reviews(provider_key: str):
    """
    Load previously saved reviews for a provider.

    Returns:
        rows: list of review dictionaries
        last_page: highest page number successfully saved
    """

    output_path = get_incremental_path(provider_key)

    if not output_path.exists():
        print("\nNo existing incremental file found.")
        print("Starting from Page 1.")

        return [], 0

    print("\nExisting incremental file found:")
    print(output_path)

    try:
        df = pd.read_csv(output_path)

    except Exception as e:
        print(f"⚠️ Could not read existing CSV: {e}")
        print("Starting from Page 1.")

        return [], 0

    if df.empty:
        print("Existing CSV is empty.")
        print("Starting from Page 1.")

        return [], 0

    print(
        f"✓ Loaded {len(df):,} previously saved reviews."
    )

    # --------------------------------------------------------
    # Determine highest successfully saved page
    # --------------------------------------------------------

    if "source_url" not in df.columns:
        print(
            "⚠️ Existing CSV does not contain source_url."
        )
        print("Starting from Page 1.")

        return df.to_dict("records"), 0

    page_numbers = (
        df["source_url"]
        .dropna()
        .apply(extract_page_number)
    )

    if page_numbers.empty:
        print(
            "⚠️ Could not determine saved page number."
        )
        print("Starting from Page 1.")

        return df.to_dict("records"), 0

    last_page = int(page_numbers.max())

    print(
        f"✓ Highest successfully saved page: "
        f"Page {last_page}"
    )

    return df.to_dict("records"), last_page


def extract_reviews(page):
    """
    Extract Trustpilot reviews from the currently loaded
    __NEXT_DATA__ element.
    """

    print("Looking for NEXT_DATA...")

    next_data = page.locator(
        'script#__NEXT_DATA__'
    )

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

    print(
        f"✓ NEXT_DATA found: {len(text):,} characters"
    )

    try:
        data = json.loads(text)

        reviews = data["props"]["pageProps"]["reviews"]

        print(
            f"✓ Reviews found: {len(reviews)}"
        )

        return reviews

    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as e:

        print(
            f"⚠️ Could not parse NEXT_DATA: {e}"
        )

        return []


def find_next_page_control(page):
    """
    Find the visible Trustpilot 'Next page' control.
    """

    matches = page.get_by_text(
        "Next page",
        exact=True,
    )

    count = matches.count()

    print(
        f"Elements containing 'Next page': {count}"
    )

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
    Save accumulated reviews to the provider's
    incremental CSV.
    """

    if not rows:
        print("No reviews to save.")
        return

    df = pd.DataFrame(rows)

    df.drop_duplicates(
        subset=["review_id"],
        inplace=True,
    )

    output_path = get_incremental_path(
        provider_key
    )

    df.to_csv(
        output_path,
        index=False,
    )

    print(
        f"💾 Saved {len(df):,} accumulated reviews → "
        f"{output_path}"
    )


def navigate_to_resume_page(
    page,
    resume_url,
    resume_page_number,
):
    """
    Navigate Chrome to the last successfully saved page.

    We use the actual saved source URL rather than
    constructing a URL ourselves.
    """

    if resume_page_number <= 0:
        return True

    print("\n" + "=" * 60)
    print(
        f"Resuming from previously saved Page "
        f"{resume_page_number}"
    )
    print("=" * 60)

    print("\nNavigating to saved page:")
    print(resume_url)

    try:

        page.goto(
            resume_url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

    except Exception as e:

        print(
            f"⚠️ Navigation error: {e}"
        )

        return False

    print(
        f"Waiting {WAIT_AFTER_REFRESH} seconds "
        "for Trustpilot page..."
    )

    time.sleep(WAIT_AFTER_REFRESH)

    print(
        f"Current URL: {page.url}"
    )

    # --------------------------------------------------------
    # Verify that Chrome actually landed on the expected page
    # --------------------------------------------------------

    actual_page = extract_page_number(
        page.url
    )

    print(
        f"Expected page: {resume_page_number}"
    )

    print(
        f"Detected page: {actual_page}"
    )

    if actual_page != resume_page_number:

        print(
            "\n⚠️ Could not navigate to the "
            "expected resume page."
        )

        print(
            "Stopping rather than risking "
            "duplicate or incorrect data."
        )

        return False

    # --------------------------------------------------------
    # Verify NEXT_DATA belongs to this page
    # --------------------------------------------------------

    reviews = extract_reviews(page)

    if not reviews:

        print(
            "⚠️ Could not extract reviews from "
            "the resume page."
        )

        return False

    print(
        f"✓ Resume page verified: "
        f"Page {resume_page_number}"
    )

    print(
        f"✓ Reviews found: {len(reviews)}"
    )

    return True


# ============================================================
# SCRAPE ONE PROVIDER
# ============================================================

def scrape_provider(
    page,
    provider_key,
    provider_cfg,
):

    base_url = provider_cfg["url"]

    last_collected = parse_iso_utc(
        provider_cfg["last_collected"]
    )

    print("\n" + "=" * 70)
    print(
        f"Provider: {provider_cfg['name']}"
    )
    print(
        f"Base URL: {base_url}"
    )
    print(
        f"Last collected: "
        f"{last_collected.isoformat()}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Load previously saved progress
    # --------------------------------------------------------

    rows, last_saved_page = load_existing_reviews(
        provider_key
    )

    # --------------------------------------------------------
    # Determine where to start
    # --------------------------------------------------------

    if last_saved_page > 0:

        next_page_number = (
            last_saved_page + 1
        )

        # Find the source URL associated with
        # the highest saved page.
        existing_df = pd.DataFrame(rows)

        page_rows = existing_df[
            existing_df["source_url"].apply(
                extract_page_number
            ) == last_saved_page
        ]

        if page_rows.empty:

            print(
                "⚠️ Could not find source URL for "
                f"Page {last_saved_page}."
            )

            return rows

        resume_url = page_rows.iloc[0][
            "source_url"
        ]

        print("\n" + "=" * 70)
        print(
            f"Previously saved through Page "
            f"{last_saved_page}"
        )
        print(
            f"Next page to scrape: "
            f"{next_page_number}"
        )
        print("=" * 70)

        # ----------------------------------------------------
        # Navigate to the last saved page
        # ----------------------------------------------------

        if not navigate_to_resume_page(
            page,
            resume_url,
            last_saved_page,
        ):

            print(
                "\n⚠️ Could not safely resume."
            )

            return rows

        page_number = last_saved_page

    else:

        # ----------------------------------------------------
        # No previous data — start from Page 1
        # ----------------------------------------------------

        print("\nNo previous progress found.")
        print("Starting from Page 1.")

        print("\nNavigating to provider page:")
        print(base_url)

        try:

            page.goto(
                base_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

        except Exception as e:

            print(
                f"⚠️ Navigation error: {e}"
            )

            return rows

        print(
            "Waiting for Trustpilot page..."
        )

        time.sleep(WAIT_AFTER_REFRESH)

        page_number = 1

    # ========================================================
    # MAIN PAGINATION LOOP
    # ========================================================

    while page_number <= MAX_PAGES_PER_PROVIDER:

        print("\n" + "-" * 60)
        print(
            f"## PAGE {page_number}"
        )
        print("-" * 60)

        print(
            f"Current URL: {page.url}"
        )

        print(
            f"Page title: {page.title()}"
        )

        # ----------------------------------------------------
        # If resuming, we're currently sitting on the last
        # successfully saved page. We need to move forward
        # before extracting anything new.
        # ----------------------------------------------------

        if (
            last_saved_page > 0
            and page_number == last_saved_page
        ):

            print(
                f"\nPage {page_number} was already "
                "successfully saved."
            )

            print(
                f"Moving to Page "
                f"{page_number + 1}..."
            )

            next_button = find_next_page_control(
                page
            )

            if not next_button:

                print(
                    "⚠️ Could not find Next page."
                )

                break

            previous_first_review_id = None

            try:

                current_reviews = extract_reviews(
                    page
                )

                if current_reviews:

                    previous_first_review_id = (
                        current_reviews[0]["id"]
                    )

            except Exception:
                pass

            print(
                "\nClicking Next page..."
            )

            try:

                next_button.click(
                    timeout=30_000
                )

            except Exception as e:

                print(
                    f"⚠️ Could not click Next page: "
                    f"{e}"
                )

                break

            print("✓ Click completed.")

            print(
                f"Waiting {WAIT_AFTER_CLICK} seconds..."
            )

            time.sleep(WAIT_AFTER_CLICK)

            print(
                f"URL after click: {page.url}"
            )

            # ------------------------------------------------
            # Refresh to force NEXT_DATA to update
            # ------------------------------------------------

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

            print(
                f"URL after refresh: {page.url}"
            )

            # ------------------------------------------------
            # Validate pagination
            # ------------------------------------------------

            new_reviews = extract_reviews(
                page
            )

            if not new_reviews:

                print(
                    "⚠️ Could not extract reviews "
                    "after pagination."
                )

                break

            new_first_review_id = (
                new_reviews[0]["id"]
            )

            print(
                f"Previous first review ID: "
                f"{previous_first_review_id}"
            )

            print(
                f"New first review ID:      "
                f"{new_first_review_id}"
            )

            if (
                previous_first_review_id
                == new_first_review_id
            ):

                print(
                    "\n⚠️ Pagination validation failed."
                )

                print(
                    "The new page appears to contain "
                    "the previous page's reviews."
                )

                print(
                    "Stopping rather than risking "
                    "duplicate or incorrect data."
                )

                break

            print(
                "✓ Pagination validated."
            )

            page_number += 1

            # We already have the next page's reviews.
            reviews = new_reviews

        else:

            # ------------------------------------------------
            # Normal page extraction
            # ------------------------------------------------

            reviews = extract_reviews(
                page
            )

        if not reviews:

            print(
                "⚠️ No reviews returned. "
                "Stopping provider."
            )

            break

        first_review_id = reviews[0]["id"]

        print(
            f"First review ID: "
            f"{first_review_id}"
        )

        # ----------------------------------------------------
        # Process reviews
        # ----------------------------------------------------

        new_reviews_this_page = 0
        reached_last_collected = False

        # Keep track of IDs already saved.
        existing_ids = {
            row["review_id"]
            for row in rows
        }

        for review in reviews:

            published_raw = (
                review["dates"]["publishedDate"]
            )

            published_dt = parse_iso_utc(
                published_raw
            )

            # ------------------------------------------------
            # Stop when we reach previously collected data
            # ------------------------------------------------

            if published_dt <= last_collected:

                reached_last_collected = True

                break

            review_id = review["id"]

            # ------------------------------------------------
            # Avoid duplicate review IDs
            # ------------------------------------------------

            if review_id in existing_ids:

                continue

            rows.append({

                "provider": provider_key,

                "review_id": review_id,

                "rating": review["rating"],

                "title": review["title"],

                "text": review["text"],

                "likes": review["likes"],

                "filtered": review["filtered"],

                "pending": review["isPending"],

                "experienced_date": (
                    review["dates"]
                    ["experiencedDate"]
                ),

                "published_date": published_raw,

                "source_url": page.url,

            })

            existing_ids.add(
                review_id
            )

            new_reviews_this_page += 1

        print(
            f"New reviews from page "
            f"{page_number}: "
            f"{new_reviews_this_page}"
        )

        # ----------------------------------------------------
        # Save after EVERY successfully processed page
        # ----------------------------------------------------

        save_reviews(
            provider_key,
            rows,
        )

        # ----------------------------------------------------
        # Determine whether we're finished
        # ----------------------------------------------------

        if reached_last_collected:

            print(
                "\n✓ Reached previously "
                "collected reviews."
            )

            break

        # ----------------------------------------------------
        # Find Next Page
        # ----------------------------------------------------

        print(
            "\nLooking for 'Next page' control..."
        )

        next_button = find_next_page_control(
            page
        )

        if not next_button:

            print(
                "✓ No visible Next page control found."
            )

            print(
                "✓ End of pagination."
            )

            break

        print(
            "✓ Next page control found."
        )

        previous_first_review_id = (
            first_review_id
        )

        # ----------------------------------------------------
        # Click Next Page
        # ----------------------------------------------------

        print(
            "\nClicking Next page..."
        )

        try:

            next_button.click(
                timeout=30_000
            )

        except Exception as e:

            print(
                f"⚠️ Could not click Next page: "
                f"{e}"
            )

            break

        print(
            "✓ Click completed."
        )

        print(
            f"Waiting {WAIT_AFTER_CLICK} seconds "
            "for Trustpilot's pagination state..."
        )

        time.sleep(
            WAIT_AFTER_CLICK
        )

        print(
            f"URL after click: {page.url}"
        )

        # ----------------------------------------------------
        # Refresh
        # ----------------------------------------------------

        print(
            "\nRefreshing page..."
        )

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

        print(
            "✓ Refresh completed."
        )

        print(
            f"Waiting {WAIT_AFTER_REFRESH} seconds "
            "for NEXT_DATA..."
        )

        time.sleep(
            WAIT_AFTER_REFRESH
        )

        print(
            f"URL after refresh: {page.url}"
        )

        # ----------------------------------------------------
        # Validate pagination
        # ----------------------------------------------------

        print(
            "\nValidating that the new page "
            "contains different reviews..."
        )

        new_reviews = extract_reviews(
            page
        )

        if not new_reviews:

            print(
                "⚠️ Could not extract reviews "
                "after pagination refresh."
            )

            break

        new_first_review_id = (
            new_reviews[0]["id"]
        )

        print(
            f"Previous first review ID: "
            f"{previous_first_review_id}"
        )

        print(
            f"New first review ID:      "
            f"{new_first_review_id}"
        )

        if (
            new_first_review_id
            == previous_first_review_id
        ):

            print(
                "\n⚠️ Pagination validation failed."
            )

            print(
                "The refreshed page still appears "
                "to contain the previous page's reviews."
            )

            print(
                "Stopping rather than risking "
                "duplicate or incorrect data."
            )

            break

        print(
            "✓ Pagination validated — "
            "new reviews found."
        )

        # ----------------------------------------------------
        # We already extracted the next page.
        # ----------------------------------------------------

        reviews = new_reviews

        page_number += 1

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n" + "=" * 70)

    print(
        f"Provider complete: "
        f"{provider_cfg['name']}"
    )

    print(
        f"Last page reached: "
        f"{page_number}"
    )

    print(
        f"Total accumulated reviews: "
        f"{len(rows):,}"
    )

    print("=" * 70)

    return rows


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Connecting to existing Chrome..."
    )

    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(
            CDP_URL
        )

        print(
            "✓ Connected to Chrome"
        )

        contexts = browser.contexts

        if not contexts:

            raise RuntimeError(
                "No Chrome browser contexts found."
            )

        context = contexts[0]

        pages = context.pages

        print(
            f"Open pages: {len(pages)}"
        )

        # ----------------------------------------------------
        # Find Trustpilot tab
        # ----------------------------------------------------

        trustpilot_page = None

        for page in pages:

            print(
                f"Tab: {page.url}"
            )

            if (
                "trustpilot.com/review/"
                in page.url
            ):

                trustpilot_page = page

                break

        if not trustpilot_page:

            raise RuntimeError(
                "No Trustpilot review tab found."
            )

        page = trustpilot_page

        print(
            "\n✓ Using Trustpilot tab:"
        )

        print(
            page.url
        )

        # ----------------------------------------------------
        # Load provider configuration
        # ----------------------------------------------------

        with open(
            PROVIDERS_FILE,
            "r",
        ) as f:

            providers = yaml.safe_load(f)

        # ----------------------------------------------------
        # Process ONE provider for testing
        # ----------------------------------------------------

        provider_key = "petsbest"

        provider_cfg = providers[
            provider_key
        ]

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