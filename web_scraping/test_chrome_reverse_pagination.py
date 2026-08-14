import re
import time
import json
from playwright.sync_api import sync_playwright


# ============================================================
# CONFIG
# ============================================================

CDP_URL = "http://127.0.0.1:9222"

BASE_URL = "https://www.trustpilot.com/review/trupanion.com"

WAIT_AFTER_NAVIGATION = 5
WAIT_AFTER_CLICK = 5
WAIT_AFTER_REFRESH = 5


# ============================================================
# HELPERS
# ============================================================

def get_next_data(page):
    """
    Extract and parse the __NEXT_DATA__ element from the
    currently displayed Trustpilot page.
    """

    print("Looking for NEXT_DATA...")

    try:
        next_data_text = page.locator(
            'script#__NEXT_DATA__'
        ).text_content(timeout=10000)

    except Exception as e:
        print(f"⚠️ Could not locate NEXT_DATA: {e}")
        return None

    if not next_data_text:
        print("⚠️ NEXT_DATA element was empty.")
        return None

    print(f"✓ NEXT_DATA found: {len(next_data_text):,} characters")

    try:
        data = json.loads(next_data_text)
    except json.JSONDecodeError as e:
        print(f"⚠️ Could not parse NEXT_DATA JSON: {e}")
        return None

    return data


def extract_reviews(data):
    """
    Extract reviews from NEXT_DATA.

    This function searches recursively for a list containing
    review-like dictionaries so it is less dependent on the
    exact Trustpilot NEXT_DATA structure.
    """

    candidates = []

    def walk(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            if obj:
                review_like = 0

                for item in obj:
                    if isinstance(item, dict):
                        if (
                            "id" in item
                            and (
                                "published" in item
                                or "publishedDate" in item
                                or "datePublished" in item
                            )
                        ):
                            review_like += 1

                if review_like >= 2:
                    candidates.append(obj)

            for item in obj:
                walk(item)

    walk(data)

    if not candidates:
        print("⚠️ No review list found in NEXT_DATA.")
        return []

    reviews = max(candidates, key=len)

    print(f"✓ Reviews found: {len(reviews)}")

    return reviews


def get_review_id(review):
    """
    Extract review ID from a review dictionary.
    """

    return (
        review.get("id")
        or review.get("reviewId")
        or review.get("review_id")
    )


def get_review_date(review):
    """
    Attempt to extract a published date from a review.
    """

    return (
        review.get("published")
        or review.get("publishedDate")
        or review.get("datePublished")
        or review.get("published_date")
    )


def get_page_diagnostics(page):
    """
    Extract NEXT_DATA and return useful diagnostics about
    the reviews currently displayed.
    """

    data = get_next_data(page)

    if data is None:
        return None

    reviews = extract_reviews(data)

    if not reviews:
        return {
            "reviews": [],
            "first_id": None,
            "first_date": None,
            "oldest_date": None,
            "newest_date": None,
        }

    review_dates = [
        get_review_date(review)
        for review in reviews
        if get_review_date(review)
    ]

    first_review = reviews[0]

    print(
        f"First review ID: {get_review_id(first_review)}"
    )

    print(
        f"First review date: {get_review_date(first_review)}"
    )

    if review_dates:
        print(f"Oldest date:      {min(review_dates)}")
        print(f"Newest date:      {max(review_dates)}")

    return {
        "reviews": reviews,
        "first_id": get_review_id(first_review),
        "first_date": get_review_date(first_review),
        "oldest_date": min(review_dates) if review_dates else None,
        "newest_date": max(review_dates) if review_dates else None,
    }


def get_page_numbers_from_title(title):
    """
    Extract current page and maximum page from a Trustpilot
    page title such as:

        Trupanion Reviews | ... | 579 of 579
    """

    match = re.search(
        r"\|\s*(\d+)\s+of\s+(\d+)\s*$",
        title
    )

    if not match:
        return None, None

    current_page = int(match.group(1))
    maximum_page = int(match.group(2))

    return current_page, maximum_page


def find_previous_button(page):
    """
    Locate Trustpilot's Previous pagination control.

    Trustpilot exposes this very clearly via:

        data-pagination-name="pagination-button-previous"
    """

    print("Looking for 'Previous' control...")

    selector = (
        'a[data-pagination-name="pagination-button-previous"]'
    )

    button = page.locator(selector)

    count = button.count()

    print(f"Previous controls found: {count}")

    if count == 0:
        print("⚠️ Previous page control not found.")
        return None

    button = button.first

    try:
        visible = button.is_visible()
    except Exception:
        visible = False

    print(f"✓ Previous page control found.")
    print(f"  Visible: {visible}")

    try:
        href = button.get_attribute("href")
        print(f"  href: {href}")
    except Exception:
        href = None

    try:
        aria_label = button.get_attribute("aria-label")
        print(f"  aria-label: {aria_label}")
    except Exception:
        pass

    try:
        name = button.get_attribute("name")
        print(f"  name: {name}")
    except Exception:
        pass

    return button


# ============================================================
# MAIN
# ============================================================

def main():

    print("Connecting to existing Chrome...")

    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(CDP_URL)

        print("✓ Connected to Chrome")

        contexts = browser.contexts

        if not contexts:
            raise RuntimeError(
                "No browser contexts found."
            )

        pages = contexts[0].pages

        print(f"Open pages: {len(pages)}")

        if not pages:
            raise RuntimeError(
                "No open Chrome tabs found."
            )

        # ----------------------------------------------------
        # Find Trustpilot tab
        # ----------------------------------------------------

        trustpilot_page = None

        for candidate in pages:
            print(f"Tab: {candidate.url}")

            if "trustpilot.com/review/" in candidate.url:
                trustpilot_page = candidate
                break

        if trustpilot_page is None:
            raise RuntimeError(
                "Could not find an open Trustpilot tab."
            )

        page = trustpilot_page

        print()
        print("✓ Using Trustpilot tab:")
        print(page.url)

        # ----------------------------------------------------
        # Current page diagnostics
        # ----------------------------------------------------

        print()
        print("Current URL:")
        print(page.url)

        title = page.title()

        print(f"Page title: {title}")

        current_page, maximum_page = (
            get_page_numbers_from_title(title)
        )

        if maximum_page is None:

            print(
                "⚠️ Could not determine maximum page "
                "from page title."
            )

            raise RuntimeError(
                "Could not determine Trustpilot maximum page."
            )

        print()
        print("Current page diagnostics:")
        print(f"  Current page: {current_page}")
        print(f"  Maximum page: {maximum_page}")

        # ----------------------------------------------------
        # Navigate directly to final page
        # ----------------------------------------------------

        final_url = (
            f"{BASE_URL}?page={maximum_page}"
        )

        print()
        print("=" * 60)
        print(
            f"NAVIGATING TO FINAL PAGE: {maximum_page}"
        )
        print("=" * 60)

        print(f"URL: {final_url}")

        page.goto(
            final_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("Waiting for Trustpilot...")
        time.sleep(WAIT_AFTER_NAVIGATION)

        print()
        print("URL immediately after navigation:")
        print(page.url)

        print()
        print("Page title:")
        print(page.title())

        # ----------------------------------------------------
        # Refresh final page
        # ----------------------------------------------------

        print()
        print("Refreshing final page...")

        page.reload(
            wait_until="domcontentloaded",
            timeout=60000
        )

        time.sleep(WAIT_AFTER_REFRESH)

        print(f"URL after refresh:")
        print(page.url)

        print()
        print("Page title after refresh:")
        print(page.title())

        # ----------------------------------------------------
        # Extract final page reviews
        # ----------------------------------------------------

        print()
        print("-" * 60)
        print(f"FINAL PAGE: {maximum_page}")
        print("-" * 60)

        final_diagnostics = get_page_diagnostics(page)

        if final_diagnostics is None:
            raise RuntimeError(
                "Could not extract reviews from final page."
            )

        print()
        print(
            f"Reviews:       "
            f"{len(final_diagnostics['reviews'])}"
        )

        print(
            f"First ID:      "
            f"{final_diagnostics['first_id']}"
        )

        print(
            f"First date:    "
            f"{final_diagnostics['first_date']}"
        )

        print(
            f"Oldest date:   "
            f"{final_diagnostics['oldest_date']}"
        )

        print(
            f"Newest date:   "
            f"{final_diagnostics['newest_date']}"
        )

        # ----------------------------------------------------
        # Find Previous button
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print(
            f"TESTING PREVIOUS PAGE: "
            f"{maximum_page} → {maximum_page - 1}"
        )
        print("=" * 60)

        previous_button = find_previous_button(page)

        if previous_button is None:

            print()
            print("⚠️ Could not find Previous page.")
            print("Stopping test.")

            return

        # ----------------------------------------------------
        # Save current page's first review ID
        # ----------------------------------------------------

        previous_first_id = final_diagnostics["first_id"]

        # ----------------------------------------------------
        # Click Previous
        # ----------------------------------------------------

        print()
        print("Clicking Previous page...")

        try:
            previous_button.click(
                timeout=30000
            )

            print("✓ Click completed.")

        except Exception as e:

            print(
                f"⚠️ Click failed: {e}"
            )

            return

        # ----------------------------------------------------
        # Wait for pagination transition
        # ----------------------------------------------------

        print()
        print(
            f"Waiting {WAIT_AFTER_CLICK} seconds "
            "for Trustpilot's pagination state to update..."
        )

        time.sleep(WAIT_AFTER_CLICK)

        print()
        print("URL after click:")
        print(page.url)

        print()
        print("Page title after click:")
        print(page.title())

        # ----------------------------------------------------
        # Refresh
        # ----------------------------------------------------

        print()
        print("Refreshing page after Previous click...")

        try:

            page.reload(
                wait_until="domcontentloaded",
                timeout=60000
            )

            print("✓ Refresh completed.")

        except Exception as e:

            print(
                f"⚠️ Refresh failed: {e}"
            )

            return

        time.sleep(WAIT_AFTER_REFRESH)

        print()
        print("URL after refresh:")
        print(page.url)

        print()
        print("Page title after refresh:")
        print(page.title())

        # ----------------------------------------------------
        # Validate resulting page
        # ----------------------------------------------------

        print()
        print(
            "Validating that the new page contains "
            "different reviews..."
        )

        new_diagnostics = get_page_diagnostics(page)

        if new_diagnostics is None:

            print(
                "⚠️ Could not extract reviews "
                "after pagination."
            )

            return

        new_first_id = new_diagnostics["first_id"]

        print()
        print(
            f"Previous page first review ID: "
            f"{previous_first_id}"
        )

        print(
            f"New page first review ID:      "
            f"{new_first_id}"
        )

        # ----------------------------------------------------
        # Success / failure
        # ----------------------------------------------------

        if (
            new_first_id
            and previous_first_id
            and new_first_id != previous_first_id
        ):

            print()
            print("=" * 60)
            print("✓ SUCCESS — REVERSE PAGINATION WORKS")
            print("=" * 60)

            print(
                f"Page {maximum_page} successfully "
                f"transitioned to Page {maximum_page - 1}."
            )

            print(
                "The refreshed page contains different reviews."
            )

        else:

            print()
            print("=" * 60)
            print("⚠️ REVERSE PAGINATION VALIDATION FAILED")
            print("=" * 60)

            print(
                "The refreshed page still appears to "
                "contain the previous page's reviews."
            )

        print()
        print("=" * 60)
        print("REVERSE PAGINATION TEST COMPLETE")
        print("=" * 60)

        print(f"Provider:       Trupanion")
        print(f"Maximum page:   {maximum_page}")
        print(
            f"Pages tested:   "
            f"{maximum_page} → {maximum_page - 1}"
        )

        print()
        print("No CSV or YAML files were modified.")


if __name__ == "__main__":
    main()