from pathlib import Path
import pandas as pd
from bertopic import BERTopic
import re
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from umap import UMAP
from bertopic.vectorizers import ClassTfidfTransformer

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "modeling" / "reviews_with_topics.csv"
OUTPUT_DIR = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT_FILE)

# -----------------------------------------------------------
# Exclude Dutch (Telehealth vs. Indemnity Insurance Provider)
# -----------------------------------------------------------

docs_topic1 = df.loc[df['topic'] == 1].reset_index(drop=True)
texts = docs_topic1["clean_text"].astype(str).tolist()

# ----------------------------
# Remove stopwords
# ----------------------------

domain_stopwords = {'pet', 'pets', 'insurance', 'pet insurance', 'vet',
    'claim', 'claims', 'year', 'years', 'coverage', 'company',
    'time', 'great', 'just', 'ive', 'quick', 'easy', 'process',
    'best', 'did'}
custom_stop_words = list(ENGLISH_STOP_WORDS.union(domain_stopwords))

sub_vectorizer = CountVectorizer(
    stop_words=custom_stop_words,
    ngram_range=(1, 2),
    min_df=1,
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
    random_state=42
)

sub_ctfidf_model = ClassTfidfTransformer(
    reduce_frequent_words=True,
    bm25_weighting=True
)

sub_topic_model = BERTopic(
    umap_model=sub_umap_model,
    vectorizer_model=sub_vectorizer,
    ctfidf_model=sub_ctfidf_model,
    language="english",
    min_topic_size=150,
    nr_topics=15,
    calculate_probabilities=True,
    verbose=True
)

sub_topics, sub_probs = sub_topic_model.fit_transform(texts)

docs_topic1["topic"] = sub_topics

# Save enriched dataset
output_path = OUTPUT_DIR / "reviews_with_topic1_subtopics.csv"
docs_topic1.to_csv(output_path, index=False)

print(f"Saved results to: {output_path}")

# ----------------------------
# Quick topic summary
# ----------------------------
sub_topic_info = sub_topic_model.get_topic_info()
print(sub_topic_info.head(10))

sub_topic_model.save("bertopic_model_topic1_subtopics", serialization="safetensors")