import pandas as pd
import yaml
from pathlib import Path

# ---------------------------
# CONFIG
# ---------------------------
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews/web_scraping")
RAW_DIR = BASE_DIR / "raw"
INCREMENTAL_DIR = BASE_DIR / "incremental"
CURATED_DIR = BASE_DIR / "curated"

CURATED_DIR.mkdir(exist_ok=True)

# ---------------------------
# LOAD PROVIDERS FROM YAML
# ---------------------------
with open(BASE_DIR / "providers.yaml", "r") as f:
    providers = yaml.safe_load(f)

# ---------------------------
# MERGE LOOP
# ---------------------------
for provider_key in providers.keys():
    print(f"\n▶ Merging provider: {provider_key}")

    raw_file = RAW_DIR / f"{provider_key}_reviews.csv"
    inc_file = INCREMENTAL_DIR / f"{provider_key}_reviews_incremental.csv"

    # Load raw if it exists
    if raw_file.exists():
        df_raw = pd.read_csv(raw_file)
        # Normalize schema defensively
        if "review_id" in df_raw.columns and "id" not in df_raw.columns:
            df_raw.rename(columns={"review_id": "id"}, inplace=True)
    else:
        df_raw = pd.DataFrame()
        print("  No raw file found — treating incremental as full dataset")

    # Load incremental if it exists
    if inc_file.exists():
        df_inc = pd.read_csv(inc_file)
        if "review_id" in df_inc.columns and "id" not in df_inc.columns:
            df_inc.rename(columns={"review_id": "id"}, inplace=True)
    else:
        df_inc = pd.DataFrame()
        print("  No incremental file found — skipping incremental merge")

    # Merge logic
    if not df_raw.empty and not df_inc.empty:
        df_all = pd.concat([df_raw, df_inc], ignore_index=True)
    elif not df_raw.empty:
        df_all = df_raw
    elif not df_inc.empty:
        df_all = df_inc
    else:
        print(f"  No data available for {provider_key} — skipping")
        continue

    # Deduplicate on Trustpilot review ID
    df_all.drop_duplicates(subset=["id"], inplace=True)

    # Save curated output
    output_file = CURATED_DIR / f"{provider_key}_reviews_all.csv"
    df_all.to_csv(output_file, index=False)

    print(f"  Saved {len(df_all)} reviews → {output_file}")

print("\n✅ Merge complete for all providers.")