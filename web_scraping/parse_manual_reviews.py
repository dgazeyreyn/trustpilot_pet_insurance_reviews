import json
import re
import yaml
import pandas as pd

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from striprtf.striprtf import rtf_to_text


# ---------------------------
# CONFIGURATION
# ---------------------------

MANUAL_DIR = Path("manual")
DATA_DIR = Path("incremental")

MANUAL_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


# ---------------------------
# HELPERS
# ---------------------------

def parse_iso_utc(ts: str) -> datetime:
    """Convert Trustpilot ISO timestamp to datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def normalize_domain(domain: str) -> str:
    """Normalize a domain for comparison."""
    domain = domain.lower().strip()
    return domain.removeprefix("www.")


def get_provider_domain(provider_cfg: dict) -> str:
    """
    Extract the Trustpilot business domain from the provider URL.

    Example:
    https://www.trustpilot.com/review/www.akcpetinsurance.com
    -> akcpetinsurance.com
    """
    url = provider_cfg["url"]
    path = urlparse(url).path.rstrip("/")

    business_domain = path.split("/")[-1]

    return normalize_domain(business_domain)


def load_providers() -> dict:
    """Load provider configuration."""
    with open("web_scraping/providers.yaml", "r") as f:
        return yaml.safe_load(f)


def find_provider(business_unit: dict, providers: dict):
    """
    Match the provider contained in __NEXT_DATA__
    to the corresponding provider in providers.yaml.
    """

    identifying_name = business_unit.get("identifyingName")

    if not identifying_name:
        raise ValueError(
            "Could not find businessUnit.identifyingName "
            "in __NEXT_DATA__."
        )

    identifying_name = normalize_domain(identifying_name)

    for provider_key, provider_cfg in providers.items():
        provider_domain = get_provider_domain(provider_cfg)

        if identifying_name == provider_domain:
            return provider_key, provider_cfg

    return None, None


def load_rtf_json(filepath: Path) -> dict:
    """
    Convert an RTF file containing __NEXT_DATA__ into
    a Python dictionary.
    """

    print(f"\nReading: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        rtf_content = f.read()

    # Convert RTF formatting to plain text.
    text = rtf_to_text(rtf_content)

    # The manually copied content should already be the
    # __NEXT_DATA__ element, but remove the HTML wrapper
    # if it is still present.
    script_match = re.search(
        r"<script[^>]*id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if script_match:
        json_text = script_match.group(1).strip()
    else:
        # If only the JSON contents were copied, use the
        # entire converted file.
        json_text = text.strip()

    if not json_text:
        raise ValueError("No JSON content found in RTF file.")

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        print("\nJSON parsing failed.")
        print(f"Error: {e}")
        print("\nFirst 500 characters of extracted text:")
        print(json_text[:500])
        raise


def transform_review(
    review: dict,
    provider_key: str,
    source_file: Path,
) -> dict:
    """Transform a Trustpilot review into the existing project schema."""

    published_raw = review["dates"]["publishedDate"]

    return {
        "provider": provider_key,
        "review_id": review["id"],
        "rating": review["rating"],
        "title": review["title"],
        "text": review["text"],
        "likes": review["likes"],
        "filtered": review["filtered"],
        "pending": review["isPending"],
        "experienced_date": review["dates"]["experiencedDate"],
        "published_date": published_raw,
        "source_url": review.get("source_url"),
        "source_file": source_file.name,
    }


# ---------------------------
# PROCESS ONE FILE
# ---------------------------

def process_file(filepath: Path, providers: dict):
    """Process one manually captured Trustpilot RTF file."""

    data = load_rtf_json(filepath)

    try:
        page_props = data["props"]["pageProps"]
        business_unit = page_props["businessUnit"]
        reviews = page_props["reviews"]

    except KeyError as e:
        raise ValueError(
            f"Expected __NEXT_DATA__ structure not found: {e}"
        )

    # Identify provider from the Trustpilot payload.
    provider_key, provider_cfg = find_provider(
        business_unit,
        providers,
    )

    if provider_cfg is None:
        identifying_name = business_unit.get(
            "identifyingName",
            "UNKNOWN",
        )

        raise ValueError(
            f"Could not match Trustpilot business "
            f"'{identifying_name}' to providers.yaml."
        )

    provider_name = provider_cfg["name"]

    last_collected = parse_iso_utc(
        provider_cfg["last_collected"]
    )

    print(f"Provider: {provider_name}")
    print(f"Provider key: {provider_key}")
    print(f"Reviews in file: {len(reviews)}")
    print(f"Last collected: {last_collected}")

    # Show the date range contained in the source file.
    review_dates = [
        parse_iso_utc(r["dates"]["publishedDate"])
        for r in reviews
        if r.get("dates", {}).get("publishedDate")
    ]

    if review_dates:
        print(
            "Source date range: "
            f"{min(review_dates).date()} → "
            f"{max(review_dates).date()}"
        )

    # ---------------------------
    # FILTER TO NEW REVIEWS
    # ---------------------------

    rows = []

    for review in reviews:

        published_raw = review["dates"]["publishedDate"]
        published_dt = parse_iso_utc(published_raw)

        # Keep only reviews newer than last_collected.
        if published_dt <= last_collected:
            continue

        rows.append(
            transform_review(
                review,
                provider_key,
                filepath,
            )
        )

    print(f"New reviews after cutoff: {len(rows)}")

    return provider_key, rows


# ---------------------------
# MAIN
# ---------------------------

def main():

    providers = load_providers()

    rtf_files = sorted(MANUAL_DIR.glob("*.rtf"))

    if not rtf_files:
        print(f"No RTF files found in: {MANUAL_DIR}")
        return

    print(f"Found {len(rtf_files)} RTF file(s).")

    all_rows = []

    for filepath in rtf_files:

        try:
            provider_key, rows = process_file(
                filepath,
                providers,
            )

            all_rows.extend(rows)

        except Exception as e:
            print(
                f"\n✖ Error processing "
                f"{filepath.name}: {e}"
            )

    # ---------------------------
    # COMBINE RESULTS
    # ---------------------------

    if not all_rows:
        print("\nNo new reviews found.")
        return

    df = pd.DataFrame(all_rows)

    # Remove duplicates across files.
    before = len(df)

    df.drop_duplicates(
        subset=["review_id"],
        inplace=True,
    )

    duplicates_removed = before - len(df)

    # Sort chronologically.
    df.sort_values(
        by=["provider", "published_date"],
        inplace=True,
    )

    # ---------------------------
    # SAVE
    # ---------------------------

    output_path = DATA_DIR / "trustpilot_manual_incremental.csv"

    df.to_csv(
        output_path,
        index=False,
    )

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Total new reviews: {len(df)}")
    print(f"Duplicates removed: {duplicates_removed}")
    print(f"Output: {output_path}")

    print("\nReviews by provider:")
    print(df["provider"].value_counts().sort_index())


if __name__ == "__main__":
    main()