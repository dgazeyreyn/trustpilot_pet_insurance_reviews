from pathlib import Path
import pandas as pd

# ----------------------------
# Paths
# ----------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent

INPUT_DIR = BASE_DIR / "web_scraping" / "curated"
OUTPUT_DIR = BASE_DIR / "data" / "modeling"
OUTPUT_FILE = OUTPUT_DIR / "reviews_for_modeling.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Read all *_reviews_all.csv files
# ----------------------------
files = list(INPUT_DIR.glob("*_reviews_all.csv"))

if not files:
    raise RuntimeError(f"No *_reviews_all.csv files found in {INPUT_DIR}")

all_dfs = []

for csv_path in files:

    print(f"\nProcessing: {csv_path.name}")

    df = pd.read_csv(csv_path)

    # Convert to consistent datetime format
    df["published_date"] = pd.to_datetime(
        df["published_date"],
        errors="coerce",
        utc=True
    )

    # ----------------------------
    # Rename review ID
    # ----------------------------
    if "id" in df.columns:
        df = df.rename(columns={"id": "review_id"})
    else:
        raise ValueError(f"{csv_path.name} missing 'id' column")

    # ----------------------------
    # Add provider column
    # ----------------------------
    provider_name = csv_path.stem.replace("_reviews_all", "")
    df["provider"] = provider_name

    # ----------------------------
    # Add dataframe to list
    # ----------------------------
    all_dfs.append(df)

# ----------------------------
# Merge all dataframes
# ----------------------------
merged = pd.concat(all_dfs, ignore_index=True)

# ----------------------------
# Sanity checks
# ----------------------------
required_cols = {
    "review_id",
    "text",
    "rating",
    "published_date",
    "provider"
}

missing = required_cols - set(merged.columns)

if missing:
    raise ValueError(
        f"Merged dataframe missing columns: {missing}"
    )

print(f"\nMerged {len(all_dfs)} files with {len(merged)} reviews")

print(
    f"Date range: "
    f"{merged['published_date'].min()} → "
    f"{merged['published_date'].max()}"
)

print("\nReviews by provider:")
print(merged["provider"].value_counts().sort_index())

# ----------------------------
# Save
# ----------------------------
merged.to_csv(OUTPUT_FILE, index=False)

print(f"\nSaved merged reviews to {OUTPUT_FILE}")