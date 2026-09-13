from pathlib import Path
import pandas as pd
import re
import contractions

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews")
input_dir = BASE_DIR / "web_scraping" / "incremental"
output_dir = BASE_DIR / "data" / "modeling"

# ----------------------------------------
# Read all *_reviews_incremental.csv files
# ----------------------------------------
files = list(input_dir.glob("*_reviews_incremental.csv"))

if not files:
    raise RuntimeError(f"No *_reviews_incremental.csv files found in {input_dir}")

all_dfs = []

for csv_path in files:

    print(f"\nProcessing: {csv_path.name}")

    df = pd.read_csv(csv_path)
    
    # Deduplicate
    df.drop_duplicates(subset=["review_id"], inplace=True)

    # ----------------------------
    # Add dataframe to list
    # ----------------------------
    all_dfs.append(df)

# ----------------------------
# Merge all dataframes
# ----------------------------
merged = pd.concat(all_dfs, ignore_index=True)

# -----------------------------------------------------------
# Provider Exclusions
# -----------------------------------------------------------
keep_providers = [
    'aspca', 'embrace',
    'fetch', 'figo',
    'healthypaws', 'metlife',
    'nationwide', 'petsbest',
    'prudent', 'pumpkin',
    'spot', 'trupanion'
]

df_filtered = merged[merged['provider'].isin(keep_providers)].reset_index(drop=True)

# Basic hygiene
df_filtered = df_filtered.dropna(subset=["text"])

# ----------------------
# Flag off-topic reviews
# ----------------------

other_insurance_phrases = [
    # Explicit product names — high precision on their own
    "renters insurance", "renter's insurance", "homeowners insurance",
    "homeowner's insurance", "home insurance", "auto insurance",
    "car insurance", "life insurance", "term life", "whole life policy",
    "umbrella policy", "umbrella insurance", "condo insurance",
    "landlord insurance", "flood insurance", "business insurance",
    "commercial insurance", "disability insurance", "identity theft protection",
    "travel insurance", "house insurance",
    # Claim-context terms that strongly imply a non-pet claim
    "totaled my car", "car accident claim", "house fire", "burglary",
    "break-in", "broke into", "stole my", "roof damage", "water damage claim",
]

pet_context_terms = [
    "dog", "cat", "pet", "vet", "puppy", "kitten", "veterinarian",
    "vaccine", "spay", "neuter", "kennel"
]

def flag_off_topic(text: str) -> bool:
    text_lower = text.lower()
    has_other_insurance = any(phrase in text_lower for phrase in other_insurance_phrases)
    has_pet_context = any(term in text_lower for term in pet_context_terms)
    return has_other_insurance and not has_pet_context

# Apply the flagging function to the cleaned text
df_filtered['off_topic_flag'] = df_filtered['text'].astype(str).apply(flag_off_topic)

# Filter flagged reviews
flagged = df_filtered[df_filtered['off_topic_flag'] == True]

# Save flagged reviews to CSV
flagged.to_csv(output_dir / "flagged_off_topic_reviews.csv", index=False)