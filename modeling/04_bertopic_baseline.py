from pathlib import Path
import pandas as pd
from bertopic import BERTopic
import re
from sklearn.feature_extraction.text import CountVectorizer

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
# Exclude Dutch (Telehealth vs. Indemnity Insurance Provider)
# -----------------------------------------------------------

df_filtered = df[df['provider'] != 'Dutch'].reset_index(drop=True)

# Basic hygiene
df_filtered = df_filtered.dropna(subset=["text"])
texts = df_filtered["text"].astype(str).tolist()

print(f"Loaded {len(texts):,} reviews")

# ------------------------------------
# Build provider name list dynamically
# ------------------------------------

# Create providers list
providers = (
    df["provider"]
    .dropna()
    .unique()
    .tolist()
)

# Normalize provider names for regex
provider_patterns = [
    re.escape(p.lower().replace("_", " "))
    for p in providers
]

# -----------------
# Clean review text
# -----------------

# Define cleaning function
def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = text.lower()

    # Remove provider names
    for pattern in provider_patterns:
        text = re.sub(pattern, "", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text

# Apply function
df["clean_text"] = df["text"].apply(clean_text)
documents = df["clean_text"].tolist()

# ----------------------------
# Remove stopwords
# ----------------------------

vectorizer_model = CountVectorizer(
    stop_words="english",
    ngram_range=(1, 2),   # capture phrases like "claim denied", "customer service", "price increase"
    min_df=5               # drop ultra-rare tokens/noise
)

# ----------------------------
# Fit BERTopic (baseline)
# ----------------------------
topic_model = BERTopic(
    vectorizer_model=vectorizer_model,
    language="english",
    min_topic_size=200,
    nr_topics=15,
    calculate_probabilities=True,
    verbose=True
)

topics, probs = topic_model.fit_transform(documents)

# ----------------------------
# Attach results
# ----------------------------
df["topic"] = topics

# Save enriched dataset
output_path = OUTPUT_DIR / "reviews_with_topics.csv"
df.to_csv(output_path, index=False)

print(f"Saved results to: {output_path}")

# ----------------------------
# Quick topic summary
# ----------------------------
topic_info = topic_model.get_topic_info()
print(topic_info.head(10))