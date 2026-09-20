#!/usr/bin/env python3
"""
theme_labeling.py

Purpose:
- Merge BERTopic results (full corpus + every sub-clustering run) with review data
- Build a single `leaf` label per review that identifies its final BERTopic cluster
- Map leaves to human-readable themes via theme_rules.LEAF_TO_THEMES (1:many capable)
- Write:
    1. reviews_with_leaf.csv        one row per review, includes `leaf` (input to the outlier step)
    2. theme_rows_topic.csv         long format (review_id, theme, is_primary, ...) for NON-outlier reviews
    3. reviews_with_themes.csv      one row per review with a primary `theme` (interim: outliers ->
                                    General/Mixed Experience) so existing downstream steps keep working

Outlier leaves ("-1", "2.-1", "3.-1", "5.-1", "2.3.-1") are NOT themed here. They are resolved in
the next step (rules + centroid scoring), which appends rows to the long-format theme table.

theme_rules.py must sit next to this script (or be on PYTHONPATH).
"""

import pandas as pd
from pathlib import Path

import theme_rules as tr

pd.set_option("display.max_rows", 50)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
MODEL_DIR = BASE_DIR / "data" / "modeling"
INPUT_TOPICS = MODEL_DIR / "reviews_with_topics_sentiment.csv"
INPUT_TOPIC2_SUBTOPICS = MODEL_DIR / "reviews_with_topic2_subtopics.csv"
INPUT_TOPIC3_SUBTOPICS = MODEL_DIR / "reviews_with_topic3_subtopics.csv"
# TODO: point these at the files your sub-clustering runs actually wrote
INPUT_TOPIC5_SUBTOPICS = MODEL_DIR / "reviews_with_topic5_subtopics.csv"
INPUT_TOPIC2_3_SUBTOPICS = MODEL_DIR / "reviews_with_topic2_subtopic3.csv"
OUTPUT_DIR = MODEL_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
topics = pd.read_csv(INPUT_TOPICS)

# Each sub-clustering file needs review_id, topic (its parent), sub_topic.
# (parent topic column name, sub_topic column name) for the joined frame:
SUB_RUNS = {
    "topic2": (INPUT_TOPIC2_SUBTOPICS, "topic_df2", "topic2_subtopics"),
    "topic3": (INPUT_TOPIC3_SUBTOPICS, "topic_df3", "topic3_subtopics"),
    "topic5": (INPUT_TOPIC5_SUBTOPICS, "topic_df5", "topic5_subtopics"),
    "topic2_3": (INPUT_TOPIC2_3_SUBTOPICS, "topic_df2_3", "topic2_3_subtopics"),
}

# ----------------------------
# Join data
# ----------------------------
result = topics.set_index("review_id")
for name, (path, parent_col, sub_col) in SUB_RUNS.items():
    sub = pd.read_csv(path).set_index("review_id")[["topic", "sub_topic"]]
    sub = sub.rename(columns={"topic": parent_col, "sub_topic": sub_col})
    assert sub.index.is_unique, f"duplicate review_id in {path.name}"
    result = result.join(sub, how="left")


# ----------------------------
# Build the leaf label
#   full-corpus topic           -> "0", "7", "-1", ...
#   sub-clustered topics 2/3/5  -> "2.1", "3.-1", "5.3", ...
#   topic 2 -> subtopic 3       -> "2.3.0", "2.3.1", "2.3.-1"
# ----------------------------
t = result["topic"].astype(int)
leaf = t.astype(str)

for parent, col in [
    (2, "topic2_subtopics"),
    (3, "topic3_subtopics"),
    (5, "topic5_subtopics"),
]:
    in_parent = t.eq(parent)
    assert (
        result.loc[in_parent, col].notna().all()
    ), f"topic {parent} reviews missing from its sub-clustering file"
    assert (
        result.loc[~in_parent, col].isna().all()
    ), f"{col} populated for reviews outside topic {parent}"
    leaf[in_parent] = f"{parent}." + result.loc[in_parent, col].astype(int).astype(str)

in_2_3 = leaf.eq("2.3")
assert (
    result.loc[in_2_3, "topic2_3_subtopics"].notna().all()
), "topic 2 / subtopic 3 reviews missing from second-level file"
assert (
    result.loc[~in_2_3, "topic2_3_subtopics"].isna().all()
), "topic2_3_subtopics populated outside 2.3"
leaf[in_2_3] = "2.3." + result.loc[in_2_3, "topic2_3_subtopics"].astype(int).astype(str)

result["leaf"] = leaf

# ----------------------------
# Validate against the mapping table
# ----------------------------
unmapped = set(result["leaf"]) - set(tr.LEAF_TO_THEMES) - tr.OUTLIER_LEAVES
assert not unmapped, f"leaves with no theme mapping: {sorted(unmapped)}"

mismatch, unexpected = tr.check_leaf_sizes(result)
if len(mismatch) or unexpected:
    print("WARNING: leaf sizes differ from the mapping table")
    print(mismatch.to_string(index=False))
    print("unexpected leaves:", sorted(unexpected))
else:
    print("Leaf sizes match the mapping table.")

# ----------------------------
# Theme rows
# ----------------------------
out = result.reset_index()

topic_rows = tr.long_from_leaf(
    out, leaf_col="leaf"
)  # non-outlier reviews, 1..n themes each

# Interim single-theme view so downstream steps keep running until the outlier step is done
primary = topic_rows.loc[topic_rows["is_primary"]].set_index("review_id")["theme"]
out["theme"] = out["review_id"].map(primary).fillna(tr.GENERAL)

# ----------------------------
# Save
# ----------------------------
out.to_csv(OUTPUT_DIR / "reviews_with_leaf.csv", index=False)
topic_rows.to_csv(OUTPUT_DIR / "theme_rows_topic.csv", index=False)
out.to_csv(OUTPUT_DIR / "reviews_with_themes.csv", index=False)
print("Saved: reviews_with_leaf.csv, theme_rows_topic.csv, reviews_with_themes.csv")
print(out["theme"].value_counts())
