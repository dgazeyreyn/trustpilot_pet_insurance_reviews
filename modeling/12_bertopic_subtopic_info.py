from pathlib import Path
import pandas as pd
from bertopic import BERTopic

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path("/Users/davidreynolds/projects/trustpilot_pet_insurance_reviews")
input_file = BASE_DIR / "data" / "modeling" / "reviews_with_topic5_subtopics.csv"
output_dir = BASE_DIR / "data" / "modeling"

# ----------------------------
# Load model data
# ----------------------------
sub_topic_model = BERTopic.load("bertopic_model_topic5_subtopics")

# Pull counts once from get_topic_info(), rather than re-querying per topic in the loop
sub_topic_info = sub_topic_model.get_topic_info()
count_by_sub_topic = dict(zip(sub_topic_info["Topic"], sub_topic_info["Count"]))

topic_records = []
for topic_id in sorted(sub_topic_model.get_topics().keys()):
    words = [word for word, score in sub_topic_model.get_topic(topic_id)]
    topic_records.append(
        {
            "topic": topic_id,
            "count": count_by_sub_topic.get(topic_id),
            "words": ", ".join(words),
        }
    )

sub_topic_df = (
    pd.DataFrame(topic_records)
    .sort_values("count", ascending=False)
    .reset_index(drop=True)
)
print(f"Saved {len(sub_topic_df)} topics → {output_dir / 'topic_summary.csv'}")

# ---------------------------------
# Load data with topics & sentiment
# ---------------------------------
df = pd.read_csv(input_file)

# Generate a random sample of 10 reviews per topic for manual inspection
sample_df = (
    df.groupby("topic", group_keys=False)
    .apply(lambda x: x.sample(n=min(len(x), 15), random_state=42))
    .reset_index(drop=True)
)
output_path = output_dir / "sample_reviews_topic5_subtopic.csv"
sample_df.to_csv(output_path, index=False)
print(
    f"Saved {len(sample_df)} sample reviews → {output_dir / 'sample_reviews_by_topic.csv'}"
)

# Calculate average rating and sentiment per topic for summary table
sub_topic_avgs_df = (
    df.groupby("sub_topic", group_keys=False)
    .agg(
        avg_rating=("rating", "mean"),
        avg_sentiment=("sentiment_score", "mean"),
    )
    .reset_index()
)

sub_topic_df = sub_topic_df.merge(
    sub_topic_avgs_df,
    left_on="topic",
    right_on="sub_topic",
)
output_path = output_dir / "summary_topic5_subtopic.csv"
sub_topic_df.to_csv(output_path, index=False)
