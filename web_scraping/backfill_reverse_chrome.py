import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pandas as pd
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURATION
# ============================================================

PROVIDER_CONFIG = {
    "metlife": {
        "url": "https://www.trustpilot.com/review/metlifepetinsurance.com",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2026-07-05T00:00:00+00:00",
    },
    "nationwide": {
        "url": "https://www.trustpilot.com/review/www.petinsurance.com",
        "start_date": "2026-01-01T00:00:00+00:00",
        "end_date": "2026-03-24T00:00:00+00:00",
    },
}


# Change this to whichever provider you are backfilling.
PROVIDER = "nationwide"


PAGE_TRANSITION_WAIT = 5
NEXT_DATA_TIMEOUT = 60_000
NAVIGATION_TIMEOUT = 60_000


BASE_DIR = Path(
    "/Users/davidreynolds/projects/"
    "trustpilot_pet_insurance_reviews"
)

INCREMENTAL_DIR = (
    BASE_DIR / "web_scraping" / "incremental"
)


# ============================================================
# DATE CONFIGURATION
# ============================================================

config = PROVIDER_CONFIG[PROVIDER]

START_DATE = pd.Timestamp(
    config["start_date"],
    tz="UTC"
)

END_DATE = pd.Timestamp(
    config["end_date"],
    tz="UTC"
)


# ============================================================
# FILE PATH
# ============================================================

INCREMENTAL_FILE = (
    INCREMENTAL_DIR
    / f"{PROVIDER}_reviews_incremental.csv"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def build_page_url(base_url, page_number):
    """Build a Trustpilot URL for a specific page."""

    if page_number == 1:
        return base_url

    return f"{base_url}?page={page_number}"


def get_page_number_from_url(url):
    """Extract ?page=N from a Trustpilot URL."""

    parsed = urlparse(url)

    query = parse_qs(parsed.query)

    if "page" not in query:
        return 1

    try:
        return int(query["page"][0])
    except (ValueError, TypeError):
        return None


def get_page_number_from_title(title):
    """
    Extract the current page number from Trustpilot's title.

    Example:
        "... | 333 of 564"
    """

    match = re.search(
        r"\|\s*(\d+)\s+of\s+(\d+)",
        title
    )

    if not match:
        return None

    return int(match.group(1))


def get_max_page_from_title(title):
    """
    Extract maximum page from Trustpilot's title.

    Example:
        "... | 333 of 564"
    """

    match = re.search(
        r"\|\s*(\d+)\s+of\s+(\d+)",
        title
    )

    if not match:
        return None

    return int(match.group(2))


# ============================================================
# CONNECT TO EXISTING CHROME
# ============================================================

def connect_to_chrome(playwright):

    print("Connecting to existing Chrome...")

    browser = playwright.chromium.connect_over_cdp(
        "http://127.0.0.1:9222"
    )

    print("✓ Connected to Chrome")

    contexts = browser.contexts

    print(
        f"Open browser contexts: {len(contexts)}"
    )

    if not contexts:
        raise RuntimeError(
            "No browser contexts found."
        )

    pages = contexts[0].pages

    print(
        f"Open pages: {len(pages)}"
    )

    for p in pages:
        print(
            f"  Tab: {p.url}"
        )

    trustpilot_pages = [
        p for p in pages
        if "trustpilot.com/review/" in p.url
    ]

    if not trustpilot_pages:
        raise RuntimeError(
            "No Trustpilot tab found."
        )

    page = trustpilot_pages[0]

    print(
        "\n✓ Using Trustpilot tab:"
    )
    print(page.url)

    return browser, page


# ============================================================
# EXTRACT NEXT_DATA
# ============================================================

def extract_reviews(page):

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

        print(
            "⚠️ NEXT_DATA not found."
        )

        print(
            f"Page title: {page.title()}"
        )

        print(
            f"Current URL: {page.url}"
        )

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
            data["props"]
                ["pageProps"]
                ["reviews"]
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
# EXTRACT REVIEW DATE
# ============================================================

def get_review_published_date(review):

    """
    Extract the Trustpilot publication timestamp.

    IMPORTANT:
    This intentionally matches scrape_reviews_chrome.py.
    """

    try:

        published_raw = (
            review["dates"]["publishedDate"]
        )

        published_date = pd.to_datetime(
            published_raw,
            utc=True,
            errors="coerce"
        )

        return published_date

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return pd.NaT


# ============================================================
# REVIEW DIAGNOSTICS
# ============================================================

def get_review_id(review):

    return review.get("id")


def get_page_date_diagnostics(reviews):

    dates = []

    for review in reviews:

        published_date = (
            get_review_published_date(review)
        )

        if pd.notna(published_date):
            dates.append(published_date)

    if not dates:

        return {
            "oldest": None,
            "newest": None,
        }

    return {
        "oldest": min(dates),
        "newest": max(dates),
    }


# ============================================================
# FIND LAST SAVED PAGE
# ============================================================

def get_last_saved_page():

    if not INCREMENTAL_FILE.exists():

        print(
            f"⚠️ Incremental file not found:"
        )

        print(INCREMENTAL_FILE)

        raise RuntimeError(
            "Cannot determine starting page."
        )

    df = pd.read_csv(
        INCREMENTAL_FILE
    )

    if df.empty:

        raise RuntimeError(
            "Incremental file is empty."
        )

    if "source_url" not in df.columns:

        raise RuntimeError(
            "Incremental file does not contain "
            "'source_url'."
        )

    pages = []

    for url in df["source_url"].dropna():

        page_number = (
            get_page_number_from_url(url)
        )

        if page_number is not None:
            pages.append(page_number)

    if not pages:

        raise RuntimeError(
            "Could not determine page number "
            "from source_url."
        )

    last_page = max(pages)

    print(
        f"✓ Highest successfully saved page: "
        f"Page {last_page}"
    )

    return last_page, df


# ============================================================
# NAVIGATE TO PAGE
# ============================================================

def navigate_to_page(page, page_number):

    url = build_page_url(
        config["url"],
        page_number
    )

    print(
        f"\nNavigating to:"
    )

    print(url)

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=NAVIGATION_TIMEOUT,
    )

    print(
        f"Waiting {PAGE_TRANSITION_WAIT} "
        "seconds for Trustpilot..."
    )

    time.sleep(
        PAGE_TRANSITION_WAIT
    )

    print(
        f"Current URL: {page.url}"
    )

    print(
        f"Page title: {page.title()}"
    )


# ============================================================
# VALIDATE PAGE
# ============================================================

def validate_page_number(
    page,
    expected_page
):

    actual_page = (
        get_page_number_from_url(
            page.url
        )
    )

    if actual_page is None:

        actual_page = (
            get_page_number_from_title(
                page.title()
            )
        )

    print(
        f"Expected page: {expected_page}"
    )

    print(
        f"Actual page:   {actual_page}"
    )

    return actual_page == expected_page


# ============================================================
# CLICK NEXT PAGE
# ============================================================

def click_next_page(page):

    print(
        "Looking for 'Next page' control..."
    )

    next_control = page.locator(
        'a[aria-label="Next page"]'
    )

    if next_control.count() == 0:

        next_control = page.locator(
            'a[name="pagination-button-next"]'
        )

    if next_control.count() == 0:

        next_control = page.locator(
            'a[data-pagination-name="pagination-button-next"]'
        )

    if next_control.count() == 0:

        print(
            "⚠️ Next page control not found."
        )

        return False

    try:

        next_control.first.wait_for(
            state="visible",
            timeout=10_000
        )

    except Exception:

        print(
            "⚠️ Next page control is not visible."
        )

        return False

    print(
        "✓ Next page control found."
    )

    try:

        next_control.first.click(
            timeout=15_000
        )

        print(
            "✓ Click completed."
        )

        return True

    except Exception as e:

        print(
            f"⚠️ Could not click Next page: {e}"
        )

        return False


# ============================================================
# LOAD NEXT PAGE
# ============================================================

def load_next_page(
    page,
    current_page,
    previous_reviews
):

    expected_page = current_page + 1

    print(
        "\nClicking Next page..."
    )

    if not click_next_page(page):

        return None

    print(
        f"\nWaiting {PAGE_TRANSITION_WAIT} "
        "seconds..."
    )

    time.sleep(
        PAGE_TRANSITION_WAIT
    )

    print(
        f"URL after click: {page.url}"
    )

    print(
        f"Page title after click: "
        f"{page.title()}"
    )

    print(
        "\nRefreshing page..."
    )

    try:

        page.reload(
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT,
        )

    except Exception as e:

        print(
            f"⚠️ Refresh failed: {e}"
        )

        return None

    time.sleep(
        PAGE_TRANSITION_WAIT
    )

    print(
        f"URL after refresh: {page.url}"
    )

    print(
        f"Page title after refresh: "
        f"{page.title()}"
    )

    if not validate_page_number(
        page,
        expected_page
    ):

        print(
            "⚠️ Page validation failed."
        )

        return None

    print(
        "\nValidating pagination..."
    )

    new_reviews = extract_reviews(page)

    if not new_reviews:

        print(
            "⚠️ No reviews extracted."
        )

        return None

    previous_id = (
        get_review_id(
            previous_reviews[0]
        )
        if previous_reviews
        else None
    )

    new_id = (
        get_review_id(
            new_reviews[0]
        )
        if new_reviews
        else None
    )

    print(
        f"Previous first review ID: "
        f"{previous_id}"
    )

    print(
        f"New first review ID:      "
        f"{new_id}"
    )

    if previous_id == new_id:

        print(
            "⚠️ Pagination validation failed."
        )

        print(
            "The new page appears to contain "
            "the same reviews."
        )

        return None

    print(
        "✓ Pagination validated."
    )

    return new_reviews


# ============================================================
# PROCESS PAGE
# ============================================================

def process_page(
    reviews,
    existing_ids
):

    diagnostics = (
        get_page_date_diagnostics(
            reviews
        )
    )

    oldest = diagnostics["oldest"]
    newest = diagnostics["newest"]

    print(
        f"Reviews on page: {len(reviews)}"
    )

    print(
        f"Oldest review: {oldest}"
    )

    print(
        f"Newest review: {newest}"
    )

    in_range = []

    for review in reviews:

        review_id = get_review_id(review)

        if not review_id:
            continue

        published_date = (
            get_review_published_date(
                review
            )
        )

        if pd.isna(published_date):
            continue

        # ----------------------------------------------------
        # Requested backfill range:
        #
        # START_DATE <= published_date < END_DATE
        # ----------------------------------------------------

        if (
            published_date >= START_DATE
            and published_date < END_DATE
        ):

            if review_id not in existing_ids:

                in_range.append(
                    review
                )

    print(
        f"Reviews in backfill range: "
        f"{len(in_range)}"
    )

    return (
        in_range,
        oldest,
        newest
    )


# ============================================================
# CONVERT REVIEWS TO DATAFRAME
# ============================================================

def reviews_to_dataframe(reviews):

    rows = []

    for review in reviews:

        published_raw = (
            review["dates"]["publishedDate"]
        )

        published_date = pd.to_datetime(
            published_raw,
            utc=True,
            errors="coerce"
        )

        if pd.isna(published_date):
            continue

        rows.append(
            {
                "id": review.get("id"),
                "text": review.get("text"),
                "title": review.get("title"),
                "rating": review.get("rating"),

                "published_date":
                    published_date.isoformat(),

                "source_url":
                    review.get(
                        "links",
                        {}
                    ).get(
                        "permalink"
                    ),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# APPEND REVIEWS
# ============================================================

def append_reviews(new_reviews):

    if not new_reviews:

        return 0

    new_df = reviews_to_dataframe(
        new_reviews
    )

    if new_df.empty:

        return 0

    if INCREMENTAL_FILE.exists():

        existing_df = pd.read_csv(
            INCREMENTAL_FILE
        )

    else:

        existing_df = pd.DataFrame()

    # --------------------------------------------------------
    # Make sure source_url exists
    # --------------------------------------------------------

    if "source_url" not in new_df.columns:

        new_df["source_url"] = None

    # --------------------------------------------------------
    # Ensure existing IDs are respected
    # --------------------------------------------------------

    if (
        not existing_df.empty
        and "id" in existing_df.columns
    ):

        new_df = new_df[
            ~new_df["id"].isin(
                existing_df["id"]
            )
        ]

    if new_df.empty:

        return 0

    combined = pd.concat(
        [
            existing_df,
            new_df
        ],
        ignore_index=True
    )

    combined.drop_duplicates(
        subset=["id"],
        inplace=True
    )

    combined.to_csv(
        INCREMENTAL_FILE,
        index=False
    )

    return len(new_df)


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "\n============================================================"
    )

    print(
        f"ONE-TIME HISTORICAL BACKFILL: "
        f"{PROVIDER.upper()}"
    )

    print(
        "============================================================"
    )

    print(
        f"Start date: {START_DATE}"
    )

    print(
        f"End date:   {END_DATE}"
    )

    print(
        f"Incremental file:"
    )

    print(
        INCREMENTAL_FILE
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "providers.yaml will NOT be modified."
    )

    # --------------------------------------------------------
    # Find existing progress
    # --------------------------------------------------------

    last_page, existing_df = (
        get_last_saved_page()
    )

    existing_ids = set()

    if "id" in existing_df.columns:

        existing_ids = set(
            existing_df["id"]
            .dropna()
            .astype(str)
        )

    print(
        f"Existing review IDs: "
        f"{len(existing_ids):,}"
    )

    # --------------------------------------------------------
    # Connect to Chrome
    # --------------------------------------------------------

    with sync_playwright() as playwright:

        browser, page = (
            connect_to_chrome(
                playwright
            )
        )

        current_page = last_page

        # ----------------------------------------------------
        # Navigate to saved page
        # ----------------------------------------------------

        print(
            "\n============================================================"
        )

        print(
            f"RESUMING FROM PAGE {current_page}"
        )

        print(
            "============================================================"
        )

        navigate_to_page(
            page,
            current_page
        )

        if not validate_page_number(
            page,
            current_page
        ):

            raise RuntimeError(
                "Could not verify starting page."
            )

        current_reviews = extract_reviews(
            page
        )

        if not current_reviews:

            raise RuntimeError(
                "Could not extract reviews "
                "from starting page."
            )

        total_added = 0

        # ----------------------------------------------------
        # Process starting page
        # ----------------------------------------------------

        (
            new_reviews,
            oldest,
            newest
        ) = process_page(
            current_reviews,
            existing_ids
        )

        added = append_reviews(
            new_reviews
        )

        if added:

            total_added += added

            existing_ids.update(
                get_review_id(r)
                for r in new_reviews
                if get_review_id(r)
            )

        # ----------------------------------------------------
        # Determine whether starting page is already
        # older than our requested range.
        # ----------------------------------------------------

        if (
            oldest is not None
            and oldest < START_DATE
        ):

            print(
                "\n✓ Starting page already reaches "
                "the January 1 boundary."
            )

        # ----------------------------------------------------
        # Continue forward
        # ----------------------------------------------------

        while True:

            # ------------------------------------------------
            # If the entire current page is older than the
            # start boundary, we're done.
            # ------------------------------------------------

            if (
                oldest is not None
                and oldest < START_DATE
            ):

                print(
                    "\n✓ Reached the beginning "
                    "of the backfill range."
                )

                break

            # ------------------------------------------------
            # Check whether we're already at the final page.
            # ------------------------------------------------

            max_page = (
                get_max_page_from_title(
                    page.title()
                )
            )

            if (
                max_page is not None
                and current_page >= max_page
            ):

                print(
                    "\n✓ Reached the final Trustpilot page."
                )

                break

            # ------------------------------------------------
            # Move to next page
            # ------------------------------------------------

            print(
                "\n============================================================"
            )

            print(
                f"PAGE {current_page} → "
                f"{current_page + 1}"
            )

            print(
                "============================================================"
            )

            next_reviews = load_next_page(
                page,
                current_page,
                current_reviews
            )

            if next_reviews is None:

                print(
                    "\n⚠️ Pagination failed."
                )

                print(
                    "Stopping to avoid duplicate "
                    "or incorrect data."
                )

                break

            current_page += 1

            current_reviews = next_reviews

            # ------------------------------------------------
            # Process new page
            # ------------------------------------------------

            (
                new_reviews,
                oldest,
                newest
            ) = process_page(
                current_reviews,
                existing_ids
            )

            added = append_reviews(
                new_reviews
            )

            if added:

                total_added += added

                existing_ids.update(
                    get_review_id(r)
                    for r in new_reviews
                    if get_review_id(r)
                )

                print(
                    f"✓ Added {added} new reviews."
                )

            else:

                print(
                    "No new reviews added."
                )

            # ------------------------------------------------
            # Boundary diagnostics
            # ------------------------------------------------

            if oldest is not None:

                print(
                    f"Page {current_page} "
                    f"oldest review: {oldest}"
                )

            # ------------------------------------------------
            # Stop after processing the page that reaches
            # January 1, 2026.
            # ------------------------------------------------

            if (
                oldest is not None
                and oldest < START_DATE
            ):

                print(
                    "\n✓ January 1, 2026 boundary reached."
                )

                break

        # ----------------------------------------------------
        # Final summary
        # ----------------------------------------------------

        print(
            "\n============================================================"
        )

        print(
            "BACKFILL COMPLETE"
        )

        print(
            "============================================================"
        )

        print(
            f"Provider:          {PROVIDER}"
        )

        print(
            f"Pages processed:   through Page {current_page}"
        )

        print(
            f"Reviews added:     {total_added}"
        )

        print(
            f"Date range:        {START_DATE} → {END_DATE}"
        )

        print(
            f"Output file:       {INCREMENTAL_FILE}"
        )

        print(
            "\nproviders.yaml was NOT modified."
        )

        print(
            "============================================================"
        )


if __name__ == "__main__":
    main()