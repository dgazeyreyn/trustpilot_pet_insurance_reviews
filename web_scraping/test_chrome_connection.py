from playwright.sync_api import sync_playwright


TEST_URL = (
    "https://www.trustpilot.com/review/"
    "www.akcpetinsurance.com?page=1"
)


def main():

    print("\nConnecting to existing Chrome...")

    with sync_playwright() as p:

        browser = p.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        print("✓ Connected to Chrome")

        print(f"Open browser contexts: {len(browser.contexts)}")

        if not browser.contexts:
            print("✖ No browser contexts found.")
            return

        context = browser.contexts[0]

        print(f"Open pages: {len(context.pages)}")

        # Find an existing Trustpilot tab.
        trustpilot_page = None

        for page in context.pages:
            print(f"  Tab: {page.url}")

            if "trustpilot.com" in page.url:
                trustpilot_page = page
                break

        if trustpilot_page is None:
            print("\nNo Trustpilot tab found.")
            print(f"Navigating to: {TEST_URL}")

            trustpilot_page = context.new_page()
            trustpilot_page.goto(
                TEST_URL,
                wait_until="domcontentloaded",
                timeout=30_000,
            )

        print("\n--- TRUSTPILOT PAGE ---")
        print(f"URL: {trustpilot_page.url}")
        print(f"Title: {trustpilot_page.title()}")

        # Look for __NEXT_DATA__
        next_data = trustpilot_page.locator(
            "#__NEXT_DATA__"
        )

        count = next_data.count()

        print(f"\n__NEXT_DATA__ elements found: {count}")

        if count == 0:
            print("✖ __NEXT_DATA__ was not found.")
            return

        print("✓ __NEXT_DATA__ found")

        # Extract the JSON directly from the DOM.
        json_text = next_data.text_content()

        if not json_text:
            print("✖ __NEXT_DATA__ is empty.")
            return

        print(
            f"✓ __NEXT_DATA__ size: "
            f"{len(json_text):,} characters"
        )

        # Parse the JSON.
        import json

        data = json.loads(json_text)

        reviews = (
            data
            ["props"]
            ["pageProps"]
            ["reviews"]
        )

        print(f"✓ Reviews found: {len(reviews)}")

        if reviews:
            first = reviews[0]

            print("\n--- FIRST REVIEW ---")
            print(f"ID: {first.get('id')}")
            print(f"Rating: {first.get('rating')}")
            print(f"Title: {first.get('title')}")
            print(
                "Published: "
                f"{first['dates']['publishedDate']}"
            )

        print("\n✓ SUCCESS")
        print(
            "Python successfully read the "
            "Trustpilot data from your Chrome session."
        )


if __name__ == "__main__":
    main()