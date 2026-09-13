from pathlib import Path
import pandas as pd
from bertopic import BERTopic
import re
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from umap import UMAP
import contractions
from bertopic.vectorizers import ClassTfidfTransformer

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "modeling" / "reviews_for_modeling.csv"
OUTPUT_DIR = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT_FILE)

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

df_filtered = df[df['provider'].isin(keep_providers).reset_index(drop=True)]

# Basic hygiene
df_filtered = df_filtered.dropna(subset=["text"])
texts = df_filtered["text"].astype(str).tolist()

print(f"Loaded {len(texts):,} reviews")

# ------------------------------------
# Build provider name list
# ------------------------------------

provider_phrases = [
    'aspca',
    'embrace',
    'fetch',
    'figo',
    'healthy paws', 'healthypaws',
    'met life', 'metlife',
    'nationwide',
    'pets best', 'petsbest',
    'prudent',
    'pumpkin',
    'spot',
    'trupanion'
]

# Sort longest-first so multi-word phrases are tried before any shorter overlaps
sorted_phrases = sorted(provider_phrases, key=len, reverse=True)

# One compiled regex, word-boundary-safe, case-insensitive
provider_pattern = re.compile(
    r'\b(?:' + '|'.join(re.escape(p) for p in sorted_phrases) + r')\b',
    flags=re.IGNORECASE
)

# ------------------------------------
# Build species and affect list
# ------------------------------------

species_and_affect_terms = [
    'dog', 'dogs', 'cat', 'cats', 'kitten', 'kittens', 'kitty', 'feline',
    'fur baby', 'fur babies', 'furbaby', 'furbabies', 'fur-baby',
]

sorted_terms = sorted(species_and_affect_terms, key=len, reverse=True)
species_affect_pattern = re.compile(
    r'\b(?:' + '|'.join(re.escape(t) for t in sorted_terms) + r')\b',
    flags=re.IGNORECASE
)

# -----------------
# Clean review text
# -----------------

def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = contractions.fix(text)
    text = text.lower()
    text = provider_pattern.sub(" ", text)   # single-pass phrase removal
    text = species_affect_pattern.sub(" ", text)   # NEW — strip from raw text, pre-embedding
    text = re.sub(r"\s+", " ", text).strip() # collapse whitespace

    return text

df_filtered["clean_text"] = df_filtered["text"].apply(clean_text)

# Save df_filtered for downstream modeling 
df_filtered.to_csv(OUTPUT_DIR / "04_bertopic_baseline_input.csv", index=False)

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
    "travel insurance", "house insurance"
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
df_filtered['off_topic_flag'] = df_filtered['clean_text'].astype(str).apply(flag_off_topic)

# Filter flagged reviews
flagged = df_filtered[df_filtered['off_topic_flag'] == True]

# Save flagged reviews to CSV
flagged.to_csv(OUTPUT_DIR / "flagged_off_topic_reviews.csv", index=False)