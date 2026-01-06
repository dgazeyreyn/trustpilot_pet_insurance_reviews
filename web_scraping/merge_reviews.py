import pandas as pd
import yaml
from pathlib import Path

BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews/web_scraping")

RAW_DIR = BASE_DIR / "raw"
INCREMENTAL_DIR = BASE_DIR / "incremental"
CURATED_DIR = BASE_DIR / "curated"

CURATED_DIR.mkdir(exist_ok=True)

# ---------------------------
# LOAD PROVIDERS
# ---------------------------
with open(BASE_DIR / "providers.yaml", "r") as f:
    providers = yaml.safe_load(f)

# ---------------------------
# MERGE LOOP
# ---------------------------
for provider_key in providers.keys():
    print(f"\n▶ Merging {provider_key}")

    raw_path = RAW_DIR / f"{provider_key}_reviews.csv"
    inc_path = INCREMENTAL_DIR / f"{provider_key}_reviews_incremental.csv"

    if not raw_path.exists():
        print("  Raw file missing — skipping")
        continue

    df_raw = pd.read_csv(raw_path)

    # Normalize schema defensively
    if "review_id" in df_raw.columns and "id" not in df_raw.columns:
        df_raw.rename(columns={"review_id": "id"}, inplace=True)

    if inc_path.exists():
        df_inc = pd.read_csv(inc_path)

        if "review_id" in df_inc.columns:
            df_inc.rename(columns={"review_id": "id"}, inplace=True)

        df_all = pd.concat([df_raw, df_inc], ignore_index=True)
    else:
        print("  No incremental file found — using raw only")
        df_all = df_raw.copy()

    # Deduplicate on Trustpilot review ID
    df_all.drop_duplicates(subset=["id"], inplace=True)

    output_path = CURATED_DIR / f"{provider_key}_reviews_all.csv"
    df_all.to_csv(output_path, index=False)

    print(f"  Saved {len(df_all)} reviews → {output_path}")
