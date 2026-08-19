import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(
    "/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews"
)

INCREMENTAL_DIR = BASE_DIR / "web_scraping" / "incremental"


# ------------------------------------------------------------
# One-off backfill configuration
# ------------------------------------------------------------

BACKFILL_CONFIG = {
    "metlife": {
        "name": "MetLife Pet Insurance",
        "url": "https://www.trustpilot.com/review/metlifepetinsurance.com",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2026-07-05T23:59:59.999999+00:00",
    },
    "nationwide": {
        "name": "Nationwide Pet Insurance",
        "url": "https://www.trustpilot.com/review/www.petinsurance.com",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2026-03-24T23:59:59.999999+00:00",
    },
}


# ------------------------------------------------------------
# Choose provider here
# ------------------------------------------------------------

PROVIDER = "metlife"

# Change to:
# PROVIDER = "nationwide"
# when running the Nationwide backfill.


# ------------------------------------------------------------
# Timing
# ------------------------------------------------------------

PAGE_TRANSITION_WAIT = 5
NEXT_DATA_TIMEOUT = 60_000
NAVIGATION_TIMEOUT = 60_000


# ============================================================
# HELPERS
# ============================================================

def parse_datetime(value):
    """Parse a Trustpilot timestamp into UTC datetime."""

    if value is None:
        return None

    try:
        timestamp = pd.to_datetime(
            value,
            errors="coerce",
            utc=True,
        )

        if pd.isna(timestamp):
            return None

        return timestamp.to_pydatetime()

    except Exception:
        return None


def extract_page_number(url):
    """Extract ?page=N from a Trustpilot URL."""

    if not url:
        return None

    match = re.search(r"[?&]page=(\d+)", url)

    if match:
        return int(match.group(1))

    # Base URL is Page 1
    return 1


def build_page_url(base_url, page_number):
    """Build a Trustpilot page URL."""

    if page_number <= 1:
        return base_url

    return f"{base_url}?page={page_number}"


# ============================================================
# CHROME CONNECTION
# ============================================================

def connect_to_chrome(playwright):
    print("Connecting to existing Chrome...")

    browser = playwright.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    print("✓ Connected to Chrome")

    contexts = browser.contexts

    print(f"Open browser contexts: {len(contexts)}")

    for context in contexts:
        print(f"  Pages: {len(context.pages)}")

    if not contexts:
        raise RuntimeError("No Chrome browser contexts found.")

    context = contexts[0]

    trustpilot_pages = [
        p
        for p in context.pages
        if "trustpilot.com/review/" in p.url
    ]

    if not trustpilot_pages:
        raise RuntimeError(
            "No Trustpilot tab found in the existing Chrome session."
        )

    page = trustpilot_pages[0]

    print("\n✓ Using Trustpilot tab:")
    print(page.url)

    return browser, context, page


# ============================================================
# NEXT_DATA
# ============================================================

def get_next_data(page):
    """
    Retrieve and parse Trustpilot's __NEXT_DATA__ element.

    Uses the same structure that worked in
    scrape_reviews_chrome.py.
    """

    print("Looking for NEXT_DATA...")

    next_data = page.locator(
        "script#__NEXT_DATA__"
    )

    try:
        next_data.wait_for(
            state="attached",
            timeout=NEXT_DATA_TIMEOUT,
        )

    except Exception:
        print("⚠️ NEXT_DATA not found.")

        try:
            print(f"Page title: {page.title()}")
            print(f"Current URL: {page.url}")
        except Exception:
            pass

        return None

    try:
        text = next_data.text_content()

    except Exception as e:
        print(
            f"⚠️ Could not read NEXT_DATA: {e}"
        )
        return None

    if not text:
        print("⚠️ NEXT_DATA is empty.")
        return None

    print(
        f"✓ NEXT_DATA found: {len(text):,} characters"
    )

    try:
        return json.loads(text)

    except json.JSONDecodeError as e:
        print(
            f"⚠️ Could not parse NEXT_DATA JSON: {e}"
        )
        return None


def extract_reviews(page):
    """
    Extract reviews using the known Trustpilot NEXT_DATA
    structure used by scrape_reviews_chrome.py.
    """

    data = get_next_data(page)

    if data is None:
        return []

    try:
        reviews = data[
            "props"
        ][
            "pageProps"
        ][
            "reviews"
        ]

        print(
            f"✓ Reviews found: {len(reviews)}"
        )

        return reviews

    except (
        KeyError,
        TypeError,
    ) as e:

        print(
            f"⚠️ Could not locate reviews in NEXT_DATA: {e}"
        )

        return []


# ============================================================
# PAGE DIAGNOSTICS
# ============================================================

def get_page_diagnostics(page):
    """Extract reviews and basic page diagnostics."""

    reviews = extract_reviews(page)

    diagnostics = {
        "reviews": reviews,
        "count": len(reviews),
        "first_id": None,
        "first_date": None,
        "oldest_date": None,
        "newest_date": None,
        "page_number": extract_page_number(page.url),
    }

    if not reviews:
        return diagnostics

    first = reviews[0]

    diagnostics["first_id"] = first.get("id")

    diagnostics["first_date"] = (
        first.get("published")
        or first.get("publishedDate")
        or first.get("datePublished")
    )

    dates = []

    for review in reviews:

        published = (
            review.get("published")
            or review.get("publishedDate")
            or review.get("datePublished")
        )

        parsed = parse_datetime(published)

        if parsed is not None:
            dates.append(parsed)

    if dates:
        diagnostics["oldest_date"] = min(dates)
        diagnostics["newest_date"] = max(dates)

    return diagnostics


# ============================================================
# EXISTING INCREMENTAL DATA
# ============================================================

def load_existing_reviews(provider):
    """
    Load the provider's existing incremental file.

    Returns:
        dataframe
        highest page represented by source_url
    """

    incremental_file = (
        INCREMENTAL_DIR
        / f"{provider}_reviews_incremental.csv"
    )

    if incremental_file.exists():

        print(
            f"\nLoading existing incremental file:"
        )
        print(incremental_file)

        df = pd.read_csv(incremental_file)

        print(
            f"Existing rows: {len(df):,}"
        )

    else:

        print(
            f"\n⚠️ Existing incremental file not found:"
        )
        print(incremental_file)

        df = pd.DataFrame()

    highest_page = 1

    if (
        not df.empty
        and "source_url" in df.columns
    ):

        pages = (
            df["source_url"]
            .dropna()
            .apply(extract_page_number)
            .dropna()
        )

        if len(pages):
            highest_page = int(pages.max())

    print(
        f"Highest page represented in existing file: "
        f"{highest_page}"
    )

    return df, highest_page, incremental_file


# ============================================================
# NAVIGATION
# ============================================================

def navigate_to_page(page, page_number, base_url):
    """Navigate to a specific Trustpilot page."""

    url = build_page_url(
        base_url,
        page_number,
    )

    print(
        f"\nNavigating to Page {page_number}:"
    )
    print(url)

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=NAVIGATION_TIMEOUT,
    )

    print(
        f"Waiting {PAGE_TRANSITION_WAIT} seconds..."
    )

    time.sleep(PAGE_TRANSITION_WAIT)

    print(
        f"Current URL: {page.url}"
    )

    print(
        f"Page title: {page.title()}"
    )

    return url


def click_previous(page):
    """
    Not used by this forward backfill.

    Kept here intentionally as a reminder that Trustpilot's
    page navigation is controlled through the pagination links.
    """

    previous = page.locator(
        'a[name="pagination-button-previous"]'
    )

    if previous.count() == 0:
        return False

    return True


def click_next_and_refresh(
    page,
    expected_next_page,
    previous_first_id,
):
    """
    Click Trustpilot's Next page button.

    Trustpilot updates the page state after the click but
    frequently requires a refresh before NEXT_DATA reflects
    the new page. This mirrors the working scraper logic.
    """

    print(
        "\nLooking for 'Next page' control..."
    )

    next_control = page.locator(
        'a[name="pagination-button-next"]'
    )

    if next_control.count() == 0:

        # Fallback to the text-based selector.
        next_control = page.get_by_text(
            "Next page",
            exact=True,
        )

    if next_control.count() == 0:

        print(
            "⚠️ Next page control not found."
        )

        return False

    print(
        "✓ Next page control found."
    )

    try:
        next_control.first.click(
            timeout=30_000
        )

    except Exception as e:

        print(
            f"⚠️ Could not click Next page: {e}"
        )

        return False

    print("✓ Click completed.")

    print(
        f"Waiting {PAGE_TRANSITION_WAIT} seconds..."
    )

    time.sleep(PAGE_TRANSITION_WAIT)

    print(
        f"URL after click: {page.url}"
    )

    print(
        f"Page title after click: {page.title()}"
    )

    print("\nRefreshing page...")

    try:
        page.reload(
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT,
        )

    except Exception as e:

        print(
            f"⚠️ Page refresh raised: {e}"
        )

        return False

    time.sleep(PAGE_TRANSITION_WAIT)

    print(
        f"URL after refresh: {page.url}"
    )

    print(
        f"Page title after refresh: {page.title()}"
    )

    actual_page = extract_page_number(
        page.url
    )

    print(
        f"\nExpected page: {expected_next_page}"
    )

    print(
        f"Actual page:   {actual_page}"
    )

    if actual_page != expected_next_page:

        print(
            "⚠️ Pagination validation failed."
        )

        return False

    diagnostics = get_page_diagnostics(
        page
    )

    new_first_id = diagnostics[
        "first_id"
    ]

    print(
        "\nValidating pagination..."
    )

    print(
        f"Previous first review ID: "
        f"{previous_first_id}"
    )

    print(
        f"New first review ID:      "
        f"{new_first_id}"
    )

    if (
        previous_first_id
        and new_first_id
        and previous_first_id == new_first_id
    ):

        print(
            "⚠️ Review IDs did not change."
        )

        return False

    print(
        "✓ Pagination validated."
    )

    return True


# ============================================================
# REVIEW FILTERING
# ============================================================

def filter_reviews(
    reviews,
    start_date,
    end_date,
):
    """
    Keep only reviews within the requested backfill window.
    """

    selected = []

    for review in reviews:

        published = (
            review.get("published")
            or review.get("publishedDate")
            or review.get("datePublished")
        )

        published_dt = parse_datetime(
            published
        )

        if published_dt is None:
            continue

        if (
            start_date
            <= published_dt
            <= end_date
        ):
            selected.append(review)

    return selected


def review_is_older_than_start(
    reviews,
    start_date,
):
    """
    Because Trustpilot pages run newest → oldest, once the
    oldest review on a page is before the backfill start date,
    we can stop after processing that page.
    """

    dates = []

    for review in reviews:

        published = (
            review.get("published")
            or review.get("publishedDate")
            or review.get("datePublished")
        )

        parsed = parse_datetime(
            published
        )

        if parsed is not None:
            dates.append(parsed)

    if not dates:
        return False

    return min(dates) < start_date


# ============================================================
# CONVERT REVIEWS TO DATAFRAME
# ============================================================

def reviews_to_dataframe(
    reviews,
    source_url,
):
    """
    Convert Trustpilot review dictionaries into a dataframe.

    We preserve the raw review fields and add source_url.
    """

    if not reviews:
        return pd.DataFrame()

    df = pd.DataFrame(reviews)

    df["source_url"] = source_url

    return df


# ============================================================
# SAVE
# ============================================================

def append_and_deduplicate(
    existing_df,
    new_df,
    output_file,
):
    """
    Append new reviews to the existing incremental file and
    deduplicate using review ID.
    """

    if new_df.empty:
        print(
            "No new reviews to save."
        )
        return existing_df

    combined = pd.concat(
        [
            existing_df,
            new_df,
        ],
        ignore_index=True,
    )

    if "id" in combined.columns:

        before = len(combined)

        combined = combined.drop_duplicates(
            subset=["id"],
            keep="first",
        )

        duplicates = (
            before - len(combined)
        )

        if duplicates:
            print(
                f"Removed {duplicates:,} duplicate review(s)."
            )

    combined.to_csv(
        output_file,
        index=False,
    )

    print(
        f"💾 Saved {len(combined):,} total reviews → "
        f"{output_file}"
    )

    return combined


# ============================================================
# MAIN BACKFILL
# ============================================================

def main():

    if PROVIDER not in BACKFILL_CONFIG:

        raise ValueError(
            f"Unknown provider: {PROVIDER}"
        )

    config = BACKFILL_CONFIG[
        PROVIDER
    ]

    provider_name = config["name"]
    base_url = config["url"]

    start_date = parse_datetime(
        config["start_date"]
    )

    end_date = parse_datetime(
        config["end_date"]
    )

    print(
        "\n============================================================"
    )
    print(
        "ONE-OFF TRUSTPILOT HISTORICAL BACKFILL"
    )
    print(
        "============================================================"
    )

    print(
        f"Provider:    {provider_name}"
    )

    print(
        f"Start date:  {start_date.isoformat()}"
    )

    print(
        f"End date:    {end_date.isoformat()}"
    )

    print(
        "\n⚠️ providers.yaml will NOT be modified."
    )

    # --------------------------------------------------------
    # Existing data
    # --------------------------------------------------------

    (
        existing_df,
        highest_existing_page,
        incremental_file,
    ) = load_existing_reviews(
        PROVIDER
    )

    # --------------------------------------------------------
    # Important:
    #
    # We start one page AFTER the highest page represented
    # in the existing incremental file.
    #
    # This assumes the existing incremental scrape progressed
    # sequentially through Trustpilot pages.
    # --------------------------------------------------------

    start_page = (
        highest_existing_page + 1
    )

    print(
        "\n============================================================"
    )

    print(
        f"Existing data through Page "
        f"{highest_existing_page}"
    )

    print(
        f"Backfill will begin at Page "
        f"{start_page}"
    )

    print(
        "============================================================"
    )

    accumulated = []

    current_page_number = start_page

    previous_first_id = None

    # --------------------------------------------------------
    # Connect to Chrome
    # --------------------------------------------------------

    with sync_playwright() as playwright:

        browser, context, page = (
            connect_to_chrome(
                playwright
            )
        )

        # ----------------------------------------------------
        # Navigate to first page
        # ----------------------------------------------------

        navigate_to_page(
            page,
            current_page_number,
            base_url,
        )

        while True:

            print(
                "\n------------------------------------------------------------"
            )

            print(
                f"PAGE {current_page_number}"
            )

            print(
                "------------------------------------------------------------"
            )

            print(
                f"Current URL: {page.url}"
            )

            print(
                f"Page title: {page.title()}"
            )

            diagnostics = (
                get_page_diagnostics(
                    page
                )
            )

            reviews = diagnostics[
                "reviews"
            ]

            if not reviews:

                print(
                    "⚠️ No reviews found."
                )

                print(
                    "Stopping to avoid risking "
                    "incorrect data."
                )

                break

            print(
                f"Reviews on page: "
                f"{len(reviews)}"
            )

            print(
                f"First review ID: "
                f"{diagnostics['first_id']}"
            )

            print(
                f"Oldest review: "
                f"{diagnostics['oldest_date']}"
            )

            print(
                f"Newest review: "
                f"{diagnostics['newest_date']}"
            )

            # ------------------------------------------------
            # Filter to requested date range
            # ------------------------------------------------

            matching = filter_reviews(
                reviews,
                start_date,
                end_date,
            )

            print(
                f"Reviews in backfill range: "
                f"{len(matching)}"
            )

            if matching:

                page_url = page.url

                page_df = (
                    reviews_to_dataframe(
                        matching,
                        page_url,
                    )
                )

                accumulated.append(
                    page_df
                )

                print(
                    f"✓ Added {len(page_df)} "
                    f"backfill reviews."
                )

            # ------------------------------------------------
            # Stop once we've reached reviews older than the
            # beginning of the requested range.
            # ------------------------------------------------

            if review_is_older_than_start(
                reviews,
                start_date,
            ):

                print(
                    "\n✓ Reached reviews older than "
                    f"{start_date.date()}."
                )

                print(
                    "Backfill range has been covered."
                )

                break

            # ------------------------------------------------
            # Prepare next page
            # ------------------------------------------------

            next_page = (
                current_page_number + 1
            )

            print(
                f"\nMoving to Page {next_page}..."
            )

            previous_first_id = (
                diagnostics["first_id"]
            )

            success = (
                click_next_and_refresh(
                    page,
                    next_page,
                    previous_first_id,
                )
            )

            if not success:

                print(
                    "\n⚠️ Pagination failed."
                )

                print(
                    "Stopping rather than risking "
                    "duplicate or incorrect data."
                )

                break

            current_page_number = (
                next_page
            )

        # ----------------------------------------------------
        # Close browser connection
        # ----------------------------------------------------

        try:
            browser.close()
        except Exception:
            pass

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    if accumulated:

        backfill_df = pd.concat(
            accumulated,
            ignore_index=True,
        )

        print(
            "\n============================================================"
        )

        print(
            "BACKFILL RESULTS"
        )

        print(
            "============================================================"
        )

        print(
            f"New reviews collected: "
            f"{len(backfill_df):,}"
        )

        # ----------------------------------------------------
        # Deduplicate against existing reviews
        # ----------------------------------------------------

        if (
            "id" in backfill_df.columns
            and "id" in existing_df.columns
        ):

            existing_ids = set(
                existing_df["id"]
                .dropna()
                .astype(str)
            )

            before = len(
                backfill_df
            )

            backfill_df = (
                backfill_df[
                    ~backfill_df["id"]
                    .astype(str)
                    .isin(existing_ids)
                ]
            )

            already_existing = (
                before
                - len(backfill_df)
            )

            if already_existing:

                print(
                    f"Excluded {already_existing:,} "
                    "reviews already present in incremental file."
                )

        print(
            f"New unique reviews to append: "
            f"{len(backfill_df):,}"
        )

        if not backfill_df.empty:

            final_df = (
                append_and_deduplicate(
                    existing_df,
                    backfill_df,
                    incremental_file,
                )
            )

            # ------------------------------------------------
            # Date diagnostics
            # ------------------------------------------------

            if "published" in backfill_df.columns:

                dates = pd.to_datetime(
                    backfill_df["published"],
                    errors="coerce",
                    utc=True,
                )

                print(
                    "\nBackfilled date range:"
                )

                print(
                    f"  Min: {dates.min()}"
                )

                print(
                    f"  Max: {dates.max()}"
                )

        else:

            print(
                "\nNo new unique reviews needed "
                "to be added."
            )

    else:

        print(
            "\n============================================================"
        )

        print(
            "NO BACKFILL REVIEWS FOUND"
        )

        print(
            "============================================================"
        )

    print(
        "\n✓ Backfill script complete."
    )

    print(
        "providers.yaml was not modified."
    )


if __name__ == "__main__":
    main()