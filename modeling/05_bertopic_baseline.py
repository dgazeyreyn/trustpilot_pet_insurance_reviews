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
INPUT_FILE = BASE_DIR / "data" / "modeling" / "04_bertopic_baseline_input.csv"
OUTPUT_DIR = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT_FILE)

documents = df["clean_text"].tolist()

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
    min_df=5               # drop ultra-rare tokens/noise
)

# ----------------------------
# Fit BERTopic (baseline)
# ----------------------------
umap_model = UMAP(
    n_neighbors=15,      # or whatever you're currently using / BERTopic's defaults
    n_components=5,
    min_dist=0.0,
    metric='cosine',
    random_state=42
)

ctfidf_model = ClassTfidfTransformer(
    reduce_frequent_words=True,
    bm25_weighting=True
)

topic_model = BERTopic(
    umap_model=umap_model,
    vectorizer_model=vectorizer_model,
    ctfidf_model=ctfidf_model,
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

topic_model.save("bertopic_model_full_corpus", serialization="safetensors")