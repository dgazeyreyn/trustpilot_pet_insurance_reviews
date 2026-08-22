import json
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

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

# ------------------------------------------------------------
# Backfill configuration
# ------------------------------------------------------------
#
# Reviews are collected when:
#
#     START_DATE <= published_date <= END_DATE
#
# Dates are interpreted as UTC.
#
# ------------------------------------------------------------

BACKFILL_CONFIG = {
    "akc": {
        "start_date": pd.Timestamp(
    "2025-08-01T00:00:00+00:00"
)
    }
}


# Conservative settings — consistent with working scraper
WAIT_AFTER_CLICK = 5
WAIT_AFTER_REFRESH = 5
NEXT_DATA_TIMEOUT = 30_000

# Safety limit. Neither provider should come close to this.
MAX_PAGES_PER_PROVIDER = 1_000


# ============================================================
# DATE HELPERS
# ============================================================

def parse_iso_utc(ts):
    """
    Convert an ISO timestamp to a timezone-aware UTC datetime.
    """

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)

        return ts.astimezone(timezone.utc)

    return datetime.fromisoformat(
        str(ts).replace("Z", "+00:00")
    )


# ============================================================
# URL / PAGE HELPERS
# ============================================================

def extract_page_number(url):
    """
    Extract Trustpilot page number from a source URL.

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


def get_incremental_path(provider_key):
    """
    Return the provider's incremental CSV path.
    """

    return (
        DATA_DIR
        / f"{provider_key}_reviews_incremental.csv"
    )


def get_checkpoint_path(provider_key):
    """
    Temporary checkpoint file used to resume after an interruption.

    This is deliberately separate from the CSV because a page can
    be successfully processed even if it contains zero reviews in
    the requested backfill date range.
    """

    return (
        DATA_DIR
        / f"{provider_key}_backfill_checkpoint.json"
    )


# ============================================================
# LOAD EXISTING REVIEWS
# ============================================================

def load_existing_reviews(provider_key):
    """
    Load previously saved reviews.

    Existing rows are retained and used for deduplication.
    """

    output_path = get_incremental_path(provider_key)

    if not output_path.exists():

        print("\nNo existing incremental file found.")
        print("Starting with an empty review set.")

        return []

    print("\nExisting incremental file found:")
    print(output_path)

    try:

        df = pd.read_csv(output_path)

    except Exception as e:

        print(
            f"⚠️ Could not read existing CSV: {e}"
        )

        print(
            "Starting with an empty accumulated review set."
        )

        return []

    if df.empty:

        print("Existing CSV is empty.")

        return []

    print(
        f"✓ Loaded {len(df):,} previously saved reviews."
    )

    return df.to_dict("records")


# ============================================================
# CHECKPOINT MANAGEMENT
# ============================================================

def load_checkpoint(provider_key):
    """
    Load the last successfully processed page.

    Returns:
        int or None
    """

    checkpoint_path = get_checkpoint_path(
        provider_key
    )

    if not checkpoint_path.exists():
        return None

    try:

        with open(checkpoint_path, "r") as f:
            checkpoint = json.load(f)

        page = checkpoint.get("last_successful_page")

        if page is not None:
            print(
                f"✓ Backfill checkpoint found: "
                f"Page {page}"
            )

            return int(page)

    except Exception as e:

        print(
            f"⚠️ Could not read checkpoint: {e}"
        )

    return None


def save_checkpoint(
    provider_key,
    page_number,
):
    """
    Save the last successfully processed page.
    """

    checkpoint_path = get_checkpoint_path(
        provider_key
    )

    checkpoint = {
        "provider": provider_key,
        "last_successful_page": page_number,
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    with open(checkpoint_path, "w") as f:
        json.dump(
            checkpoint,
            f,
            indent=2,
        )


def clear_checkpoint(provider_key):
    """
    Remove checkpoint after successful completion.
    """

    checkpoint_path = get_checkpoint_path(
        provider_key
    )

    if checkpoint_path.exists():

        checkpoint_path.unlink()

        print(
            f"✓ Removed checkpoint: "
            f"{checkpoint_path}"
        )


# ============================================================
# DETERMINE RESUME PAGE
# ============================================================

def determine_resume_page(
    provider_key,
    rows,
):
    """
    Determine where to resume.

    Priority:

    1. Explicit checkpoint
    2. Highest page found in source_url
    3. Page 1

    We subtract nothing from the resume page because the current
    page will simply be reprocessed and review IDs will be
    deduplicated. This makes the resume logic safer.
    """

    checkpoint_page = load_checkpoint(
        provider_key
    )

    if checkpoint_page is not None:

        return checkpoint_page

    # --------------------------------------------------------
    # Fall back to source_url
    # --------------------------------------------------------

    pages = []

    for row in rows:

        source_url = row.get("source_url")

        if not source_url:
            continue

        try:
            pages.append(
                extract_page_number(source_url)
            )

        except Exception:
            continue

    if pages:

        highest_page = max(pages)

        print(
            f"✓ Highest page found in source_url: "
            f"Page {highest_page}"
        )

        return highest_page

    print(
        "✓ No usable checkpoint/source_url found."
    )

    print(
        "Starting from Page 1."
    )

    return 1


# ============================================================
# EXTRACT REVIEWS
# ============================================================

def extract_reviews(page):
    """
    Extract Trustpilot reviews from the currently loaded
    __NEXT_DATA__ element.

    This intentionally matches the working scraper.
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
        f"✓ NEXT_DATA found: "
        f"{len(text):,} characters"
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
            f"✓ Reviews found: "
            f"{len(reviews)}"
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
    Save accumulated reviews.

    Deduplicates on review_id.
    """

    if not rows:

        print(
            "No reviews to save."
        )

        return

    df = pd.DataFrame(rows)

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
        f"💾 Saved {len(df):,} accumulated "
        f"reviews → {output_path}"
    )


# ============================================================
# NAVIGATE TO SPECIFIC PAGE
# ============================================================

def navigate_to_page(
    page,
    base_url,
    page_number,
):
    """
    Navigate directly to a specific Trustpilot page.
    """

    if page_number == 1:
        url = base_url
    else:
        separator = "&" if "?" in base_url else "?"
        url = (
            f"{base_url}"
            f"{separator}page={page_number}"
        )

    print(
        "\n" + "=" * 70
    )

    print(
        f"NAVIGATING TO PAGE {page_number}"
    )

    print("=" * 70)

    print(
        f"URL: {url}"
    )

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

    except Exception as e:

        print(
            f"⚠️ Navigation error: {e}"
        )

        return False

    print(
        "\nWaiting for Trustpilot..."
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
        f"Expected page: {page_number}"
    )

    print(
        f"Actual page:   {actual_page}"
    )

    if actual_page != page_number:

        print(
            "\n⚠️ Trustpilot did not load "
            f"Page {page_number}."
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
    """
    Backfill one provider.
    """

    config = BACKFILL_CONFIG[
        provider_key
    ]

    start_date = parse_iso_utc(
        config["start_date"]
    )

    # end_date = parse_iso_utc(
    #     config["end_date"]
    # )

    base_url = provider_cfg["url"]

    print(
        "\n" + "=" * 70
    )

    print(
        f"BACKFILL PROVIDER: "
        f"{provider_cfg['name']}"
    )

    print(
        f"Base URL: {base_url}"
    )

    print(
        f"Backfill start: "
        f"{start_date.isoformat()}"
    )

    # print(
    #     f"Backfill end:   "
    #     f"{end_date.isoformat()}"
    # )

    print("=" * 70)

    # --------------------------------------------------------
    # Load existing rows
    # --------------------------------------------------------

    rows = load_existing_reviews(
        provider_key
    )

    # --------------------------------------------------------
    # Determine resume page
    # --------------------------------------------------------

    page_number = determine_resume_page(
        provider_key,
        rows,
    )

    print(
        "\n" + "=" * 70
    )

    print(
        f"BACKFILL STARTING POINT"
    )

    print("=" * 70)

    print(
        f"Provider: {provider_key}"
    )

    print(
        f"Starting page: {page_number}"
    )

    print(
        f"Target range:"
    )

    print(
        f"  {start_date.isoformat()}"
    )

    # print(
    #     f"  → {end_date.isoformat()}"
    # )

    print("=" * 70)

    # --------------------------------------------------------
    # Existing review IDs
    # --------------------------------------------------------

    existing_ids = {
        row["review_id"]
        for row in rows
        if row.get("review_id")
    }

    # --------------------------------------------------------
    # Main pagination loop
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # Navigate to page
        # ----------------------------------------------------

        if not navigate_to_page(
            page,
            base_url,
            page_number,
        ):

            print(
                "⚠️ Could not navigate "
                f"to Page {page_number}."
            )

            print(
                "Stopping so the script can "
                "be safely resumed later."
            )

            break

        # ----------------------------------------------------
        # Extract reviews
        # ----------------------------------------------------

        reviews = extract_reviews(
            page
        )

        if not reviews:

            print(
                f"⚠️ No reviews found on "
                f"Page {page_number}."
            )

            print(
                "Stopping so the script can "
                "be safely resumed later."
            )

            break

        # ----------------------------------------------------
        # Page diagnostics
        # ----------------------------------------------------

        print(
            f"\nReviews on page: "
            f"{len(reviews)}"
        )

        try:

            print(
                f"First review ID: "
                f"{reviews[0]['id']}"
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # Track date range on page
        # ----------------------------------------------------

        published_dates = []

        for review in reviews:

            try:

                # IMPORTANT:
                # Use the exact syntax from the
                # working scrape_reviews_chrome.py
                published_raw = (
                    review[
                        "dates"
                    ][
                        "publishedDate"
                    ]
                )

                published_dt = parse_iso_utc(
                    published_raw
                )

                published_dates.append(
                    published_dt
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

        if published_dates:

            oldest_on_page = min(
                published_dates
            )

            newest_on_page = max(
                published_dates
            )

            print(
                f"Oldest review: "
                f"{oldest_on_page.isoformat()}"
            )

            print(
                f"Newest review: "
                f"{newest_on_page.isoformat()}"
            )

        else:

            oldest_on_page = None
            newest_on_page = None

            print(
                "⚠️ Could not determine "
                "published dates on page."
            )

        # ----------------------------------------------------
        # Process reviews
        # ----------------------------------------------------

        new_reviews_this_page = 0

        qualifying_reviews_this_page = 0

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

                published_dt = parse_iso_utc(
                    published_raw
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ) as e:

                print(
                    f"⚠️ Could not read/parse "
                    f"published date for review "
                    f"{review.get('id')}: {e}"
                )

                continue

            # ------------------------------------------------
            # Determine whether review is in backfill range
            # ------------------------------------------------

            if (
                published_dt < start_date
                # or published_dt > end_date
            ):

                continue

            qualifying_reviews_this_page += 1

            review_id = review["id"]

            # ------------------------------------------------
            # Deduplicate
            # ------------------------------------------------

            if review_id in existing_ids:
                continue

            # ------------------------------------------------
            # Add review
            #
            # IMPORTANT:
            # This mirrors scrape_reviews_chrome.py.
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
                    
                "verification":
                    review[
                        "labels"
                    ][
                        "verification"
                    ][  
                        "isVerified"
                    ],
                    
                "review_source":
                    review[
                        "labels"
                    ][
                        "verification"
                    ][
                        "reviewSourceName"
                        
                    ],
                    
                "verification_source":
                    review[
                        "labels"
                    ][
                        "verification"
                    ][
                        "verificationSource"
                    ],
                    
                "verification_level":
                    review[
                        "labels"
                    ][
                        "verification"
                    ][
                        "verificationLevel"
                    ]

            })

            existing_ids.add(
                review_id
            )

            new_reviews_this_page += 1

        print(
            f"Reviews in backfill range: "
            f"{qualifying_reviews_this_page}"
        )

        print(
            f"New reviews added: "
            f"{new_reviews_this_page}"
        )

        # ----------------------------------------------------
        # SAVE AFTER EVERY PAGE
        # ----------------------------------------------------

        save_reviews(
            provider_key,
            rows,
        )

        # ----------------------------------------------------
        # CHECKPOINT AFTER SUCCESSFUL PAGE
        # ----------------------------------------------------

        save_checkpoint(
            provider_key,
            page_number,
        )

        print(
            f"✓ Page {page_number} "
            f"checkpoint saved."
        )

        # ----------------------------------------------------
        # Determine whether we've gone past the range
        # ----------------------------------------------------
        #
        # Trustpilot is newest → oldest.
        #
        # Once the oldest review on the page is older than
        # START_DATE, all subsequent pages should also be
        # older than START_DATE.
        #
        # Therefore we can safely stop.
        # ----------------------------------------------------

        if (
            oldest_on_page is not None
            and oldest_on_page < start_date
        ):

            print(
                "\n✓ Reached the beginning "
                "of the backfill range."
            )

            print(
                f"Oldest review on Page "
                f"{page_number}: "
                f"{oldest_on_page.isoformat()}"
            )

            print(
                f"Backfill start: "
                f"{start_date.isoformat()}"
            )

            print(
                "\n✓ Backfill complete."
            )

            clear_checkpoint(
                provider_key
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
                "\n✓ No visible Next page "
                "control found."
            )

            print(
                "✓ End of pagination."
            )

            clear_checkpoint(
                provider_key
            )

            break

        print(
            "✓ Next page control found."
        )

        previous_first_review_id = (
            reviews[0]["id"]
        )

        expected_page = (
            page_number + 1
        )

        # ----------------------------------------------------
        # Click Next
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
                f"⚠️ Could not click "
                f"Next page: {e}"
            )

            print(
                "Checkpoint retained."
            )

            break

        print(
            "✓ Click completed."
        )

        print(
            f"Waiting {WAIT_AFTER_CLICK} "
            "seconds..."
        )

        time.sleep(
            WAIT_AFTER_CLICK
        )

        print(
            f"URL after click: "
            f"{page.url}"
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

            print(
                "Checkpoint retained."
            )

            break

        print(
            "✓ Refresh completed."
        )

        print(
            f"Waiting {WAIT_AFTER_REFRESH} "
            "seconds for NEXT_DATA..."
        )

        time.sleep(
            WAIT_AFTER_REFRESH
        )

        print(
            f"URL after refresh: "
            f"{page.url}"
        )

        # ----------------------------------------------------
        # Validate page number
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
                "Checkpoint retained."
            )

            print(
                "Stopping rather than risking "
                "incorrect data."
            )

            break

        # ----------------------------------------------------
        # Validate NEXT_DATA contains different reviews
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
                f"from Page {actual_page}."
            )

            print(
                "Checkpoint retained."
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
                "The refreshed page still "
                "appears to contain the "
                "previous page's reviews."
            )

            print(
                "Checkpoint retained."
            )

            print(
                "Stopping rather than risking "
                "duplicate or incorrect data."
            )

            break

        print(
            "✓ Pagination validated."
        )

        # ----------------------------------------------------
        # Move to next page
        # ----------------------------------------------------

        page_number += 1

    else:

        print(
            "\n⚠️ Maximum page safety limit "
            "reached."
        )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print(
        "\n" + "=" * 70
    )

    print(
        f"BACKFILL SUMMARY: "
        f"{provider_cfg['name']}"
    )

    print("=" * 70)

    print(
        f"Last page processed: "
        f"{page_number}"
    )

    print(
        f"Total accumulated reviews: "
        f"{len(rows):,}"
    )

    print(
        f"Backfill range:"
    )

    print(
        f"  {start_date.isoformat()}"
    )

    # print(
    #     f"  → {end_date.isoformat()}"
    # )

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
        # Process providers
        # ----------------------------------------------------
        #
        # To run only one provider, change the list to:
        #
        #     providers_to_run = ["metlife"]
        #
        # or:
        #
        #     providers_to_run = ["nationwide"]
        #
        # ----------------------------------------------------

        providers_to_run = [
            "akc"
        ]

        for provider_key in providers_to_run:

            if provider_key not in BACKFILL_CONFIG:

                print(
                    f"\n⚠️ No backfill configuration "
                    f"for {provider_key}. Skipping."
                )

                continue

            if provider_key not in providers:

                print(
                    f"\n⚠️ Provider {provider_key} "
                    f"not found in providers.yaml."
                )

                continue

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

                print(
                    "The checkpoint, if available, "
                    "has been retained."
                )

                print(
                    "You can safely re-run the script."
                )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()