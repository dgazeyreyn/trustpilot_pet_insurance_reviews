from pathlib import Path
import pandas as pd
from bertopic import BERTopic

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews")
input_file = BASE_DIR / "data" / "modeling" / "reviews_with_topics_sentiment.csv"
output_dir = BASE_DIR / "data" / "modeling"

# ----------------------------
# Load model data
# ----------------------------
topic_model = BERTopic.load("bertopic_model_full_corpus")

# Pull counts once from get_topic_info(), rather than re-querying per topic in the loop
topic_info = topic_model.get_topic_info()
count_by_topic = dict(zip(topic_info["Topic"], topic_info["Count"]))

topic_records = []
for topic_id in sorted(topic_model.get_topics().keys()):
    words = [word for word, score in topic_model.get_topic(topic_id)]
    topic_records.append(
        {
            "topic": topic_id,
            "count": count_by_topic.get(topic_id),
            "words": ", ".join(words),
        }
    )

topic_df = (
    pd.DataFrame(topic_records)
    .sort_values("count", ascending=False)
    .reset_index(drop=True)
)
print(f"Saved {len(topic_df)} topics → {output_dir / 'topic_summary.csv'}")

# ---------------------------------
# Load data with topics & sentiment
# ---------------------------------
df = pd.read_csv(input_file)

# Generate a random sample of 10 reviews per topic for manual inspection
sample_df = (
    df.groupby(["provider", "topic"], group_keys=False)
    .apply(lambda x: x.sample(n=min(len(x), 15), random_state=42))
    .reset_index(drop=True)
)
output_path = output_dir / "sample_reviews_by_topic.csv"
sample_df.to_csv(output_path, index=False)
print(
    f"Saved {len(sample_df)} sample reviews → {output_dir / 'sample_reviews_by_topic.csv'}"
)

# Calculate average rating and sentiment per topic for summary table
topic_avgs_df = (
    df.groupby("topic", group_keys=False)
    .agg(
        avg_rating=("rating", "mean"),
        avg_sentiment=("sentiment_score", "mean"),
    )
    .reset_index()
)

topic_df = topic_df.merge(topic_avgs_df, on="topic")
output_path = output_dir / "topic_summary.csv"
topic_df.to_csv(output_path, index=False)
