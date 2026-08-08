from playwright.sync_api import sync_playwright


TEST_URL = (
    "https://www.trustpilot.com/review/"
    "www.akcpetinsurance.com?page=1"
)


def main():

    print("\n" + "=" * 70)
    print("Testing Trustpilot with Playwright")
    print(f"URL: {TEST_URL}")
    print("=" * 70)

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        try:
            response = page.goto(
                TEST_URL,
                wait_until="domcontentloaded",
                timeout=30_000
            )

            print("\n--- RESPONSE ---")

            if response:
                print(f"Status code: {response.status}")
                print(f"Final URL:   {page.url}")
            else:
                print("No HTTP response returned.")

            print("\n--- PAGE ---")

            print(f"Page title: {page.title()}")

            next_data = page.locator("#__NEXT_DATA__")

            if next_data.count() > 0:
                print("✓ __NEXT_DATA__ found.")

                text = next_data.text_content()

                if text:
                    print(f"__NEXT_DATA__ size: {len(text):,} characters")

            else:
                print("⚠ __NEXT_DATA__ was not found.")

            print("\n--- HTML PREVIEW ---")
            print(page.content()[:1500])

        except Exception as e:
            print(f"\n✖ Playwright request failed:")
            print(e)

        finally:
            browser.close()


if __name__ == "__main__":
    main()