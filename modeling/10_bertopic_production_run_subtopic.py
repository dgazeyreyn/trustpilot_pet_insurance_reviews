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
input_file = BASE_DIR / "data" / "modeling" / "reviews_with_topics.csv"
output_dir = BASE_DIR / "data" / "modeling"

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(input_file)

# ----------------------------
# Filter data
# ----------------------------
df_filtered = df[df['topic'] == 2].reset_index(drop=True)
print(df_filtered.shape)

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

df_filtered = df_filtered[df_filtered['provider'].isin(keep_providers)].reset_index(drop=True)

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

# ----------------------------------------------
# Build term lists for stripping from embeddings
# ----------------------------------------------

species_terms = [
    'dog', 'dogs', 'cat', 'cats', 'kitten', 'kittens', 'kitty', 'feline',
]

affect_terms = [
    'fur baby', 'fur babies', 'furbaby', 'furbabies', 'fur-baby',
]

# NOTE: 'coverage' is stripped here ONLY for Topic 3's sub-clustering.
# Validated via seed-sweep A/B test: stripping it collapses Topic 2's
# already-confirmed 7-topic structure into 1 dominant cluster (bad),
# but is necessary here to dissolve the "Coverage" word-driven artifact
# into its real constituent themes (see [date] refresh notes).

# generic_noise_terms = [
#     'coverage',
# ]

embedding_strip_terms = species_terms + affect_terms
# + generic_noise_terms
sorted_strip_terms = sorted(embedding_strip_terms, key=len, reverse=True)
embedding_strip_pattern = re.compile(
    r'\b(?:' + '|'.join(re.escape(t) for t in sorted_strip_terms) + r')\b',
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
    text = embedding_strip_pattern.sub(" ", text)   # NEW — strip from raw text, pre-embedding
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

sub_vectorizer_model = CountVectorizer(
    stop_words=custom_stop_words,
    ngram_range=(1, 2),   # capture phrases like "claim denied", "customer service", "price increase"
    min_df=1,      # NOT 5 — remember min_df filters at the topic level in BERTopic's c-TF-IDF step, not per-review; 5 caused the "max_df corresponds to < documents than min_df" error the first time around
    max_df=0.9
)

# ----------------------------
# Fit BERTopic (baseline)
# ----------------------------
sub_umap_model = UMAP(
    n_neighbors=15,      # or whatever you're currently using / BERTopic's defaults
    n_components=5,
    min_dist=0.0,
    metric='cosine',
    random_state=0
)

sub_ctfidf_model = ClassTfidfTransformer(
    reduce_frequent_words=True,
    bm25_weighting=True
)

sub_topic_model = BERTopic(
    umap_model=sub_umap_model,
    vectorizer_model=sub_vectorizer_model,
    ctfidf_model=sub_ctfidf_model,
    language="english",
    min_topic_size=200,
    nr_topics=15,
    calculate_probabilities=True,
    verbose=True
)

sub_topics, sub_probs = sub_topic_model.fit_transform(documents)

# ----------------------------
# Attach results
# ----------------------------
df_filtered["sub_topic"] = sub_topics

# Save enriched dataset
output_path = output_dir / "reviews_with_topic2_subtopics.csv"
df_filtered.to_csv(output_path, index=False)

print(f"Saved results to: {output_path}")

# ----------------------------
# Quick topic summary
# ----------------------------
sub_topic_info = sub_topic_model.get_topic_info()
print(sub_topic_info.head(15))

sub_topic_model.save("bertopic_model_topic2_subtopics", serialization="safetensors")