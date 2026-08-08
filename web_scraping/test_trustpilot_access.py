import json
import yaml
import requests
from bs4 import BeautifulSoup as bs


# ---------------------------
# CONFIGURATION
# ---------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/json",
    "Connection": "keep-alive",
}


# ---------------------------
# SESSION
# ---------------------------

session = requests.Session()
session.headers.update(HEADERS)


# ---------------------------
# TEST REQUEST
# ---------------------------

def test_provider(provider_key, provider_cfg):
    base_url = provider_cfg["url"]
    page_url = f"{base_url}?page=1"

    print("\n" + "=" * 70)
    print(f"Testing provider: {provider_cfg['name']}")
    print(f"Provider key:     {provider_key}")
    print(f"URL:              {page_url}")
    print("=" * 70)

    try:
        response = session.get(
            page_url,
            timeout=15
        )

        # ---------------------------
        # BASIC RESPONSE INFORMATION
        # ---------------------------

        print("\n--- RESPONSE ---")
        print(f"Status code:  {response.status_code}")
        print(f"Final URL:    {response.url}")
        print(f"Content type: {response.headers.get('Content-Type')}")
        print(f"Server:       {response.headers.get('Server')}")
        print(f"Content size: {len(response.content):,} bytes")

        # ---------------------------
        # RESPONSE HEADERS
        # ---------------------------

        print("\n--- RESPONSE HEADERS ---")

        for key, value in response.headers.items():
            print(f"{key}: {value}")

        # ---------------------------
        # RESPONSE BODY
        # ---------------------------

        print("\n--- RESPONSE BODY (first 1,500 characters) ---")

        body = response.text

        if body:
            print(body[:1500])
        else:
            print("[Response body is empty]")

        # ---------------------------
        # STATUS-SPECIFIC HANDLING
        # ---------------------------

        if response.status_code == 200:
            print("\n✓ Request succeeded.")

            soup = bs(response.content, "html.parser")
            results = soup.find(id="__NEXT_DATA__")

            if results:
                print("✓ __NEXT_DATA__ element found.")

                try:
                    json_object = json.loads(results.contents[0])
                    reviews = json_object["props"]["pageProps"]["reviews"]

                    print(f"✓ Reviews found: {len(reviews)}")

                    if reviews:
                        print("\nFirst review:")
                        print(json.dumps(reviews[0], indent=2)[:2000])

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"⚠ Could not parse review data: {e}")

            else:
                print("⚠ __NEXT_DATA__ element was not found.")

        elif response.status_code == 403:
            print("\n✖ 403 Forbidden.")
            print(
                "The server is refusing this request. "
                "The response body/headers above should help identify why."
            )

        elif response.status_code == 429:
            print("\n✖ 429 Too Many Requests.")
            print("The server appears to be rate limiting this client.")

        else:
            print(f"\n⚠ Unexpected HTTP status: {response.status_code}")

    except requests.RequestException as e:
        print(f"\n✖ Request failed: {e}")


# ---------------------------
# MAIN
# ---------------------------

def main():

    with open("web_scraping/providers.yaml", "r") as f:
        providers = yaml.safe_load(f)

    if not providers:
        print("No providers found in providers.yaml.")
        return

    # Only test ONE provider: the first provider in providers.yaml
    provider_key, provider_cfg = next(iter(providers.items()))

    test_provider(provider_key, provider_cfg)


if __name__ == "__main__":
    main()