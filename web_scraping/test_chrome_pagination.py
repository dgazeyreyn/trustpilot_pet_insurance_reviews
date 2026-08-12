import json
import time

from playwright.sync_api import sync_playwright


CDP_URL = "http://127.0.0.1:9222"

EXPECTED_PAGE = 10

WAIT_AFTER_CLICK = 20
WAIT_AFTER_REFRESH = 10


def extract_reviews(page):
    """Extract reviews from the current page's NEXT_DATA."""

    print("\nLooking for NEXT_DATA...")

    next_data = page.locator('script#__NEXT_DATA__')

    try:
        next_data.wait_for(
            state="attached",
            timeout=30_000,
        )
    except Exception:
        print("⚠️ NEXT_DATA not found.")
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


def print_review_summary(reviews, label):
    """Print useful information about the first review."""

    if not reviews:
        print(f"⚠️ No reviews available for {label}.")
        return None

    first = reviews[0]

    print(f"\n--- {label} ---")
    print(f"First review ID: {first.get('id')}")
    print(
        f"First review date: "
        f"{first.get('dates', {}).get('publishedDate')}"
    )
    print(f"First review title: {first.get('title')}")

    return first.get("id")


def inspect_next_page_control(page):
    """Inspect the Next page control without clicking it."""

    print("\n" + "=" * 60)
    print("INSPECTING NEXT PAGE CONTROL")
    print("=" * 60)

    matches = page.get_by_text(
        "Next page",
        exact=True,
    )

    count = matches.count()

    print(f"Elements containing 'Next page': {count}")

    if count == 0:
        print("❌ No Next page control found.")
        return None

    for i in range(count):

        candidate = matches.nth(i)

        try:
            visible = candidate.is_visible()
        except Exception:
            visible = False

        print(f"\nCandidate {i + 1}:")
        print(f"  Visible: {visible}")

        if not visible:
            continue

        print("  ✓ Using this visible candidate.")

        try:
            box = candidate.bounding_box()

            if box:
                print("\n  Bounding box:")
                print(f"    x:      {box['x']}")
                print(f"    y:      {box['y']}")
                print(f"    width:  {box['width']}")
                print(f"    height: {box['height']}")
            else:
                print("  ⚠️ No bounding box available.")

        except Exception as e:
            print(f"  ⚠️ Could not get bounding box: {e}")

        try:
            print("\n  Tag:", candidate.evaluate(
                "(el) => el.tagName"
            ))
        except Exception as e:
            print(f"  ⚠️ Could not get tag: {e}")

        try:
            print("  Text:", repr(candidate.inner_text()))
        except Exception as e:
            print(f"  ⚠️ Could not get text: {e}")

        try:
            print(
                "  Outer HTML:",
                candidate.evaluate(
                    "(el) => el.outerHTML"
                ),
            )
        except Exception as e:
            print(f"  ⚠️ Could not get outer HTML: {e}")

        try:
            print(
                "  Parent HTML:",
                candidate.evaluate(
                    "(el) => el.parentElement?.outerHTML"
                ),
            )
        except Exception as e:
            print(f"  ⚠️ Could not get parent HTML: {e}")

        try:
            print(
                "  Grandparent HTML:",
                candidate.evaluate(
                    "(el) => el.parentElement?.parentElement?.outerHTML"
                ),
            )
        except Exception as e:
            print(f"  ⚠️ Could not get grandparent HTML: {e}")

        return candidate

    print("❌ No visible Next page control found.")

    return None


def inspect_page_state(page, label):
    """Print URL, title, and review information."""

    print("\n" + "=" * 60)
    print(label)
    print("=" * 60)

    print("Current URL:")
    print(page.url)

    print("\nPage title:")
    print(page.title())

    reviews = extract_reviews(page)

    first_id = print_review_summary(
        reviews,
        label,
    )

    return first_id


def main():

    with sync_playwright() as p:

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        print("Connecting to existing Chrome...")

        browser = p.chromium.connect_over_cdp(
            CDP_URL
        )

        print("✓ Connected to Chrome")

        context = browser.contexts[0]

        pages = context.pages

        print(f"Open pages: {len(pages)}")

        # ----------------------------------------------------
        # FIND TRUSTPILOT TAB
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
        # VERIFY STARTING PAGE
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("STARTING STATE")
        print("=" * 60)

        print("Current URL:")
        print(page.url)

        print("Page title:")
        print(page.title())

        if f"page={EXPECTED_PAGE}" not in page.url:
            print(
                f"\n⚠️ WARNING: URL does not contain "
                f"page={EXPECTED_PAGE}."
            )
            print(
                "Please make sure Chrome is currently "
                f"showing Page {EXPECTED_PAGE}."
            )

        # ----------------------------------------------------
        # PAGE 10 BEFORE CLICK
        # ----------------------------------------------------

        page_10_first_id = inspect_page_state(
            page,
            "PAGE 10 — BEFORE CLICK",
        )

        if not page_10_first_id:

            raise RuntimeError(
                "Could not identify the first review on Page 10."
            )

        # ----------------------------------------------------
        # INSPECT NEXT PAGE
        # ----------------------------------------------------

        next_button = inspect_next_page_control(page)

        if not next_button:

            raise RuntimeError(
                "Could not find a visible Next page control."
            )

        # ----------------------------------------------------
        # CAPTURE URL BEFORE CLICK
        # ----------------------------------------------------

        url_before_click = page.url

        print("\n" + "=" * 60)
        print("CLICKING NEXT PAGE")
        print("=" * 60)

        print("URL before click:")
        print(url_before_click)

        # ----------------------------------------------------
        # CLICK
        # ----------------------------------------------------

        try:

            next_button.click(
                timeout=30_000
            )

            print("✓ Click completed.")

        except Exception as e:

            print(
                f"❌ Click failed: {e}"
            )

            return

        # ----------------------------------------------------
        # WAIT AFTER CLICK
        # ----------------------------------------------------

        print(
            f"\nWaiting {WAIT_AFTER_CLICK} seconds "
            "after click..."
        )

        for remaining in range(
            WAIT_AFTER_CLICK,
            0,
            -1,
        ):

            print(
                f"  {remaining} seconds remaining...",
                end="\r",
            )

            time.sleep(1)

        print()

        # ----------------------------------------------------
        # INSPECT PAGE BEFORE REFRESH
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("STATE AFTER CLICK — BEFORE REFRESH")
        print("=" * 60)

        print("URL after click:")
        print(page.url)

        print("\nPage title after click:")
        print(page.title())

        page_after_click_first_id = (
            inspect_page_state(
                page,
                "AFTER CLICK — BEFORE REFRESH",
            )
        )

        # ----------------------------------------------------
        # COMPARE BEFORE REFRESH
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("PRE-REFRESH VALIDATION")
        print("=" * 60)

        print(
            f"Page 10 first review ID: "
            f"{page_10_first_id}"
        )

        print(
            f"First review ID after click: "
            f"{page_after_click_first_id}"
        )

        if (
            page_after_click_first_id
            == page_10_first_id
        ):

            print(
                "\nℹ️ NEXT_DATA still contains "
                "Page 10 after the click."
            )

            print(
                "This is consistent with what we've "
                "observed previously."
            )

        else:

            print(
                "\n✓ NEXT_DATA changed after the click!"
            )

        # ----------------------------------------------------
        # REFRESH
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("REFRESHING PAGE")
        print("=" * 60)

        try:

            page.reload(
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            print("✓ Refresh completed.")

        except Exception as e:

            print(
                f"❌ Refresh failed: {e}"
            )

            return

        # ----------------------------------------------------
        # WAIT AFTER REFRESH
        # ----------------------------------------------------

        print(
            f"\nWaiting {WAIT_AFTER_REFRESH} seconds "
            "after refresh..."
        )

        time.sleep(WAIT_AFTER_REFRESH)

        # ----------------------------------------------------
        # PAGE AFTER REFRESH
        # ----------------------------------------------------

        page_after_refresh_first_id = (
            inspect_page_state(
                page,
                "AFTER REFRESH",
            )
        )

        # ----------------------------------------------------
        # FINAL VALIDATION
        # ----------------------------------------------------

        print("\n" + "=" * 60)
        print("FINAL VALIDATION")
        print("=" * 60)

        print(
            f"URL before click:   {url_before_click}"
        )

        print(
            f"URL after click:    {page.url}"
        )

        print(
            f"Page 10 first ID:   {page_10_first_id}"
        )

        print(
            f"After click ID:     {page_after_click_first_id}"
        )

        print(
            f"After refresh ID:   {page_after_refresh_first_id}"
        )

        if (
            page_after_refresh_first_id
            and
            page_after_refresh_first_id
            != page_10_first_id
        ):

            print(
                "\n✓ SUCCESS!"
            )

            print(
                "The page after refresh contains "
                "different reviews from Page 10."
            )

            if "?page=11" in page.url:

                print(
                    "✓ URL confirms Page 11."
                )

            else:

                print(
                    "⚠️ Reviews changed, but URL does "
                    "not explicitly show page=11."
                )

        else:

            print(
                "\n❌ Pagination did NOT advance."
            )

            print(
                "The refreshed page still contains "
                "the Page 10 first review."
            )

        print("\nTest complete.")


if __name__ == "__main__":
    main()
