from pathlib import Path
import pandas as pd
from bertopic import BERTopic
import re

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

# Basic hygiene
df = df.dropna(subset=["text"])
texts = df["text"].astype(str).tolist()

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
# Fit BERTopic (baseline)
# ----------------------------
topic_model = BERTopic(
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