import json
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime

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
    """
    Convert ISO timestamp to timezone-aware datetime.
    """
    return datetime.fromisoformat(
        ts.replace("Z", "+00:00")
    )


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
    """
    Return the provider's incremental CSV path.
    """

    return (
        DATA_DIR
        / f"{provider_key}_reviews_incremental.csv"
    )


# ============================================================
# LOAD EXISTING REVIEWS
# ============================================================

def load_existing_reviews(provider_key: str):
    """
    Load previously saved reviews for a provider.

    IMPORTANT:
    This function intentionally does NOT determine a
    resume page.

    The incremental scraper always starts from Page 1 because
    new Trustpilot reviews appear at the beginning of the
    pagination sequence.

    Returns:
        list of previously saved review dictionaries
    """

    output_path = get_incremental_path(
        provider_key
    )

    if not output_path.exists():

        print("\nNo existing incremental file found.")
        print("Starting from Page 1.")

        return []

    print("\nExisting incremental file found:")
    print(output_path)

    try:

        df = pd.read_csv(
            output_path
        )

    except Exception as e:

        print(
            f"⚠️ Could not read existing CSV: {e}"
        )

        print(
            "Starting with an empty accumulated review set."
        )

        return []

    if df.empty:

        print(
            "Existing CSV is empty."
        )

        print(
            "Starting from Page 1."
        )

        return []

    print(
        f"✓ Loaded {len(df):,} previously saved reviews."
    )

    return df.to_dict(
        "records"
    )


# ============================================================
# EXTRACT REVIEWS
# ============================================================

def extract_reviews(page):
    """
    Extract Trustpilot reviews from the currently loaded
    __NEXT_DATA__ element.

    This is the same extraction approach used by the
    working scraper.
    """

    print(
        "Looking for NEXT_DATA..."
    )

    next_data = page.locator(
        "script#__NEXT_DATA__"
    )

    try:

        next_data.wait_for(
            state="attached",
            timeout=NEXT_DATA_TIMEOUT,
        )

    except Exception:

        print(
            "⚠️ NEXT_DATA not found."
        )

        try:
            print(
                f"Page title: {page.title()}"
            )
        except Exception:
            pass

        try:
            print(
                f"Current URL: {page.url}"
            )
        except Exception:
            pass

        return []

    try:

        text = next_data.text_content()

    except Exception as e:

        print(
            f"⚠️ Could not read NEXT_DATA: {e}"
        )

        return []

    if not text:

        print(
            "⚠️ NEXT_DATA element is empty."
        )

        return []

    print(
        f"✓ NEXT_DATA found: {len(text):,} characters"
    )

    try:

        data = json.loads(text)

        reviews = (
            data[
                "props"
            ][
                "pageProps"
            ][
                "reviews"
            ]
        )

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


# ============================================================
# FIND NEXT PAGE CONTROL
# ============================================================

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


# ============================================================
# SAVE REVIEWS
# ============================================================

def save_reviews(
    provider_key,
    rows,
):
    """
    Save accumulated reviews to the provider's
    incremental CSV.

    Deduplicates on review_id before saving.
    """

    if not rows:

        print(
            "No reviews to save."
        )

        return

    df = pd.DataFrame(
        rows
    )

    if "review_id" in df.columns:

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


# ============================================================
# NAVIGATE TO PAGE 1
# ============================================================

def navigate_to_page_one(
    page,
    base_url,
):
    """
    Always begin incremental collection at Page 1.

    This is intentional.

    We do NOT resume from the highest page found in the
    incremental CSV because new reviews appear on Page 1.
    """

    print("\n" + "=" * 70)

    print(
        "STARTING INCREMENTAL COLLECTION FROM PAGE 1"
    )

    print("=" * 70)

    print(
        "\nNavigating to provider page:"
    )

    print(
        base_url
    )

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

        return False

    print(
        "\nWaiting for Trustpilot page..."
    )

    time.sleep(
        WAIT_AFTER_REFRESH
    )

    print(
        f"Current URL: {page.url}"
    )

    try:

        print(
            f"Page title: {page.title()}"
        )

    except Exception:
        pass

    actual_page = extract_page_number(
        page.url
    )

    print(
        f"Detected page: {actual_page}"
    )

    if actual_page != 1:

        print(
            "\n⚠️ Trustpilot did not load Page 1."
        )

        print(
            "Stopping rather than risking "
            "incorrect incremental collection."
        )

        return False

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
    # Load previously saved reviews
    #
    # IMPORTANT:
    # We retain these rows, but they are NOT used to determine
    # which page we should start on.
    # --------------------------------------------------------

    rows = load_existing_reviews(
        provider_key
    )

    print(
        "\nIncremental collection strategy:"
    )

    print(
        "  • Always start at Page 1"
    )

    print(
        "  • Collect reviews newer than last_collected"
    )

    print(
        "  • Stop when last_collected is reached"
    )

    print(
        "  • Deduplicate by review_id"
    )

    # --------------------------------------------------------
    # Navigate to Page 1
    # --------------------------------------------------------

    if not navigate_to_page_one(
        page,
        base_url,
    ):

        return rows

    page_number = 1

    # ========================================================
    # MAIN PAGINATION LOOP
    # ========================================================

    while (
        page_number
        <= MAX_PAGES_PER_PROVIDER
    ):

        print(
            "\n" + "-" * 60
        )

        print(
            f"## PAGE {page_number}"
        )

        print(
            "-" * 60
        )

        print(
            f"Current URL: {page.url}"
        )

        try:

            print(
                f"Page title: {page.title()}"
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # Extract current page
        # ----------------------------------------------------

        reviews = extract_reviews(
            page
        )

        if not reviews:

            print(
                "⚠️ No reviews returned."
            )

            print(
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
            if "review_id" in row
        }

        for review in reviews:

            # ------------------------------------------------
            # Published timestamp
            # ------------------------------------------------

            try:

                published_raw = (
                    review[
                        "dates"
                    ][
                        "publishedDate"
                    ]
                )

            except (
                KeyError,
                TypeError,
            ) as e:

                print(
                    f"⚠️ Could not read published "
                    f"date for review "
                    f"{review.get('id')}: {e}"
                )

                continue

            try:

                published_dt = parse_iso_utc(
                    published_raw
                )

            except (
                ValueError,
                TypeError,
            ) as e:

                print(
                    f"⚠️ Could not parse published "
                    f"date '{published_raw}': {e}"
                )

                continue

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Stop once we reach a review that was already
            # collected as of providers.yaml last_collected.
            #
            # Trustpilot pages are ordered newest -> oldest,
            # so once this threshold is reached we don't need
            # to inspect later pages.
            # ------------------------------------------------

            if published_dt <= last_collected:

                reached_last_collected = True

                print(
                    "\n✓ Reached last_collected cutoff."
                )

                print(
                    f"Review published: "
                    f"{published_dt.isoformat()}"
                )

                print(
                    f"Last collected:   "
                    f"{last_collected.isoformat()}"
                )

                break

            review_id = review["id"]

            # ------------------------------------------------
            # Avoid duplicate review IDs
            # ------------------------------------------------

            if review_id in existing_ids:

                continue

            # ------------------------------------------------
            # Add new review
            # ------------------------------------------------

            rows.append({

                "provider":
                    provider_key,

                "review_id":
                    review_id,

                "rating":
                    review["rating"],

                "title":
                    review["title"],

                "text":
                    review["text"],

                "likes":
                    review["likes"],

                "filtered":
                    review["filtered"],

                "pending":
                    review["isPending"],

                "experienced_date":
                    review[
                        "dates"
                    ][
                        "experiencedDate"
                    ],

                "published_date":
                    published_raw,

                "source_url":
                    page.url,

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

            print(
                "✓ Incremental collection complete."
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

        expected_page = (
            page_number + 1
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
        #
        # Trustpilot's client-side pagination can change the
        # visible page without immediately updating
        # NEXT_DATA. Refreshing forces the correct page data
        # into __NEXT_DATA__.
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
        # Validate actual page number
        # ----------------------------------------------------

        actual_page = extract_page_number(
            page.url
        )

        print(
            f"Expected page: {expected_page}"
        )

        print(
            f"Actual page:   {actual_page}"
        )

        if actual_page != expected_page:

            print(
                "\n⚠️ Pagination page-number "
                "validation failed."
            )

            print(
                "Stopping rather than risking "
                "duplicate or incorrect data."
            )

            break

        # ----------------------------------------------------
        # Validate NEXT_DATA contains a different page
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

            print(
                "Stopping rather than risking "
                "duplicate or incorrect data."
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
        # Move to next page
        # ----------------------------------------------------

        reviews = new_reviews

        page_number += 1

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print(
        "\n" + "=" * 70
    )

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

    print(
        "=" * 70
    )

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

            providers = yaml.safe_load(
                f
            )

        # ----------------------------------------------------
        # Process ONE provider for testing
        #
        # Change this value to the provider you want to run.
        # ----------------------------------------------------

        provider_key = "trupanion"

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