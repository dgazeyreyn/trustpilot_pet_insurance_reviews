import json
import time
from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
TRUSTPILOT_URL = "https://www.trustpilot.com/review/trupanion.com"

WAIT_AFTER_CLICK = 5
WAIT_AFTER_REFRESH = 5


def extract_reviews(page):
    """Extract reviews from the current page's NEXT_DATA."""
    print("Looking for NEXT_DATA...")

    next_data = page.locator('script#__NEXT_DATA__')

    try:
        next_data.wait_for(state="attached", timeout=30_000)
    except Exception:
        print("⚠️ NEXT_DATA not found after waiting.")
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


def main():
    with sync_playwright() as p:
        print("Connecting to existing Chrome...")

        browser = p.chromium.connect_over_cdp(CDP_URL)

        print("✓ Connected to Chrome")

        context = browser.contexts[0]
        pages = context.pages

        print(f"Open pages: {len(pages)}")

        # Find the Trustpilot tab
        trustpilot_page = None

        for page in pages:
            print(f"Tab: {page.url}")

            if "trustpilot.com/review/" in page.url:
                trustpilot_page = page
                break

        if not trustpilot_page:
            raise RuntimeError("No Trustpilot review tab found.")

        page = trustpilot_page

        print("\n✓ Using Trustpilot tab:")
        print(page.url)

        # ---------------------------------------------------------
        # PAGE 1
        # ---------------------------------------------------------

        print("\n" + "=" * 60)
        print("PAGE 1")
        print("=" * 60)

        print(f"Current URL: {page.url}")
        print(f"Page title: {page.title()}")

        reviews_page_1 = extract_reviews(page)

        if not reviews_page_1:
            raise RuntimeError("Could not extract Page 1 reviews.")

        first_id_page_1 = reviews_page_1[0]["id"]

        print(f"Page 1 first review ID: {first_id_page_1}")
        print(
            f"Page 1 first review date: "
            f"{reviews_page_1[0]['dates']['publishedDate']}"
        )

        # ---------------------------------------------------------
        # FIND NEXT PAGE
        # ---------------------------------------------------------

        print("\nLooking for 'Next page' control...")

        matches = page.get_by_text("Next page", exact=True)

        count = matches.count()

        print(f"Elements containing 'Next page': {count}")

        if count == 0:
            raise RuntimeError("Could not find the Next page control.")

        next_button = matches.first

        if not next_button.is_visible():
            raise RuntimeError("Next page control is not visible.")

        print("✓ Next page control found and visible.")

        # ---------------------------------------------------------
        # CLICK NEXT PAGE
        # ---------------------------------------------------------

        print("\nClicking Next page...")

        url_before_click = page.url

        next_button.click()

        print("✓ Click completed.")

        print(
            f"Waiting {WAIT_AFTER_CLICK} seconds for "
            "Trustpilot's page transition..."
        )

        time.sleep(WAIT_AFTER_CLICK)

        print(f"URL after click: {page.url}")

        if page.url == url_before_click:
            print(
                "ℹ️ URL did not change — this is expected based on "
                "our previous testing."
            )
        else:
            print("✓ URL changed.")

        # ---------------------------------------------------------
        # REFRESH
        # ---------------------------------------------------------

        print("\nRefreshing the page...")

        page.reload(wait_until="domcontentloaded")

        print("✓ Refresh completed.")

        print(
            f"Waiting {WAIT_AFTER_REFRESH} seconds for "
            "NEXT_DATA to become available..."
        )

        time.sleep(WAIT_AFTER_REFRESH)

        print(f"URL after refresh: {page.url}")
        print(f"Page title: {page.title()}")

        # ---------------------------------------------------------
        # PAGE 2
        # ---------------------------------------------------------

        print("\n" + "=" * 60)
        print("PAGE 2")
        print("=" * 60)

        reviews_page_2 = extract_reviews(page)

        if not reviews_page_2:
            raise RuntimeError("Could not extract Page 2 reviews.")

        first_id_page_2 = reviews_page_2[0]["id"]

        print(f"Page 2 first review ID: {first_id_page_2}")
        print(
            f"Page 2 first review date: "
            f"{reviews_page_2[0]['dates']['publishedDate']}"
        )

        # ---------------------------------------------------------
        # VALIDATE
        # ---------------------------------------------------------

        print("\n" + "=" * 60)
        print("VALIDATION")
        print("=" * 60)

        if first_id_page_1 == first_id_page_2:
            print("❌ Page 2 still contains Page 1 reviews.")
            print(f"   Page 1 first ID: {first_id_page_1}")
            print(f"   Page 2 first ID: {first_id_page_2}")
        else:
            print("✓ SUCCESS — Page 2 contains different reviews!")
            print(f"   Page 1 first ID: {first_id_page_1}")
            print(f"   Page 2 first ID: {first_id_page_2}")

        print("\nTest complete.")


if __name__ == "__main__":
    main()
