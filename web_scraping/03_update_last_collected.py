import os
import glob
from pathlib import Path
import yaml
from datetime import datetime
import pandas as pd

# Define directory paths
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews/web_scraping")
incremental_dir = BASE_DIR / "incremental"
curated_dir = BASE_DIR / "curated"
providers_dir = BASE_DIR / "providers.yaml"

# ---------------------------
# LOAD PROVIDERS FROM YAML
# ---------------------------
with open(providers_dir, "r") as f:
    providers = yaml.safe_load(f)

# ---------------------------
# MERGE LOOP
# ---------------------------
for provider_key in providers.keys():

    inc_file = incremental_dir / f"{provider_key}_reviews_incremental.csv"

    # Load incremental if it exists
    df_inc = pd.read_csv(inc_file) if inc_file.exists() else pd.DataFrame()

    # Deduplicate
    df_inc.drop_duplicates(subset=["review_id"], inplace=True)

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
with open(providers_dir, "w") as f:
    yaml.safe_dump(providers, f, sort_keys=False)

print("\n providers.yaml updated.")