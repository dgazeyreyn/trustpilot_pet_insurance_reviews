import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime

# ---------------------------
# CONFIG
# ---------------------------
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews/web_scraping")
INCREMENTAL_DIR = BASE_DIR / "incremental"
CURATED_DIR = BASE_DIR / "curated"
PROVIDERS_YAML = BASE_DIR / "providers.yaml"

CURATED_DIR.mkdir(exist_ok=True)

# ---------------------------
# LOAD PROVIDERS FROM YAML
# ---------------------------
with open(PROVIDERS_YAML, "r") as f:
    providers = yaml.safe_load(f)

# ---------------------------
# MERGE LOOP
# ---------------------------
for provider_key in providers.keys():

    inc_file = INCREMENTAL_DIR / f"{provider_key}_reviews_incremental.csv"
    
    # NEW: capture the OLD last_collected before this run's update overwrites it
    previous_last_collected = providers.get(provider_key, {}).get("last_collected")
    previous_last_collected_ts = (
        pd.to_datetime(previous_last_collected, utc=True) if previous_last_collected else None
    )

    # Load incremental if it exists
    df_inc = pd.read_csv(inc_file) if inc_file.exists() else pd.DataFrame()

    # Deduplicate
    df_inc.drop_duplicates(subset=["id"], inplace=True)

    # Save curated output
    output_file = CURATED_DIR / f"{provider_key}_reviews_all.csv"
    df_inc.to_csv(output_file, index=False)
    print(f"  Saved {len(df_inc)} reviews → {output_file}")

    # ---------------------------
    # UPDATE last_collected TIMESTAMP
    # ---------------------------
    if "published_date" in df_inc.columns:
        # Parse ISO strings to datetime and find the latest
        df_inc["published_date_parsed"] = pd.to_datetime(df_inc["published_date"], utc=True, errors="coerce")
        latest_ts = df_inc["published_date_parsed"].max()
        if pd.notna(latest_ts):
            providers[provider_key]["last_collected"] = latest_ts.isoformat()
            print(f"  Updated last_collected → {latest_ts.isoformat()}")

# ---------------------------
# WRITE UPDATED YAML BACK
# ---------------------------
with open(PROVIDERS_YAML, "w") as f:
    yaml.safe_dump(providers, f, sort_keys=False)

print("\n providers.yaml updated.")