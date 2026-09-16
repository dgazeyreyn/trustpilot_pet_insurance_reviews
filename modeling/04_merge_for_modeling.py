from pathlib import Path
import pandas as pd

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews")
input_dir = BASE_DIR / "web_scraping" / "curated"
output_dir = BASE_DIR / "data" / "modeling"
output_file = output_dir / "reviews_for_modeling.csv"

# ----------------------------
# Read all *_reviews_all.csv files
# ----------------------------
files = list(input_dir.glob("*_reviews_all.csv"))

if not files:
    raise RuntimeError(f"No *_reviews_all.csv files found in {input_dir}")

all_dfs = []

for csv_path in files:

    print(f"\nProcessing: {csv_path.name}")

    df = pd.read_csv(csv_path)

    # Deduplicate
    df.drop_duplicates(subset=["review_id"], inplace=True)

    # Convert to consistent datetime format
    df["published_date"] = pd.to_datetime(
        df["published_date"], errors="coerce", utc=True
    )

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
required_cols = {"review_id", "text", "rating", "published_date", "provider"}

missing = required_cols - set(merged.columns)

if missing:
    raise ValueError(f"Merged dataframe missing columns: {missing}")

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
merged.to_csv(output_file, index=False)

print(f"\nSaved merged reviews to {output_file}")
