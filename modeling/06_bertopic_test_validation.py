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
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews")
input_file = BASE_DIR / "data" / "modeling" / "reviews_for_modeling.csv"
output_dir = BASE_DIR / "data" / "modeling"

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(input_file)

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

df_filtered = df[df['provider'].isin(keep_providers)].reset_index(drop=True)

# Basic hygiene
df_filtered = df_filtered.dropna(subset=["text"])

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
documents = df_filtered["clean_text"].astype(str).tolist()

print(f"Cleaned {len(documents):,} documents")

# ----------------------------
# Remove stopwords
# ----------------------------

domain_stopwords = {
    'pet', 'pets', 'insurance', 'pet insurance', 'vet',
    'claim', 'claims', 'year', 'years', 'coverage', 'company',
    'time', 'great', 'just', 'ive', 'quick', 'easy', 'process',
    'best', 'did'
}
custom_stop_words = list(ENGLISH_STOP_WORDS.union(domain_stopwords))

vectorizer_model = CountVectorizer(
    stop_words=custom_stop_words,
    ngram_range=(1, 2),   # capture phrases like "claim denied", "customer service", "price increase"
    min_df=1,      # NOT 5 — remember min_df filters at the topic level in BERTopic's c-TF-IDF step, not per-review; 5 caused the "max_df corresponds to < documents than min_df" error the first time around
    max_df=0.9
)

ctfidf_model = ClassTfidfTransformer(
    reduce_frequent_words=True,
    bm25_weighting=True
)

for seed in [0, 1, 7, 42, 99]:
    test_umap = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric='cosine',
        random_state=seed
    )
    test_model = BERTopic(
        umap_model=test_umap,
        vectorizer_model=vectorizer_model,
        ctfidf_model=ctfidf_model,
        min_topic_size=150,
        calculate_probabilities=False,  # faster for the sweep — only need topic assignments here
        verbose=False
    )
    topics, _ = test_model.fit_transform(documents)
    n_topics = len(set(topics)) - (1 if -1 in topics else 0)
    sizes = test_model.get_topic_info()['Count'].tolist()
    print(f"seed={seed}: {n_topics} topics, sizes={sizes}")