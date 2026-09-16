#!/usr/bin/env python3
"""
theme_labeling.py

Purpose:
- Merge BERTopic results with review data
- Map topics to human-readable themes
- Output Tableau-ready CSVs:
    1. reviews with theme labels
    2. theme counts by provider
    3. theme average ratings by provider
    4. monthly theme trends by provider
"""

import pandas as pd
from pathlib import Path
import numpy as np

# Set max rows to 50
pd.set_option("display.max_rows", 15)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
INPUT_TOPICS = BASE_DIR / "data" / "modeling" / "reviews_with_topics.csv"
INPUT_TOPIC2_SUBTOPICS = (
    BASE_DIR / "data" / "modeling" / "reviews_with_topic2_subtopics.csv"
)
INPUT_TOPIC3_SUBTOPICS = (
    BASE_DIR / "data" / "modeling" / "reviews_with_topic3_subtopics.csv"
)
OUTPUT_DIR = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
topics = pd.read_csv(INPUT_TOPICS)
topic2_subtopics = pd.read_csv(INPUT_TOPIC2_SUBTOPICS)
topic3_subtopics = pd.read_csv(INPUT_TOPIC3_SUBTOPICS)

# ----------------------------
# Join data
# ----------------------------
# 1. Set indices normally
topics_indexed = topics.set_index("review_id")
topic2_subtopics_indexed = topic2_subtopics.set_index("review_id")
topic3_subtopics_indexed = topic3_subtopics.set_index("review_id")

# 2. Extract and rename both columns for the topic2 DataFrame
df2_to_join = topic2_subtopics_indexed[["topic", "sub_topic"]].rename(
    columns={"topic": "topic_df2", "sub_topic": "topic2_subtopics"}
)

# 3. Extract and rename both columns for the topic3 DataFrame
df3_to_join = topic3_subtopics_indexed[["topic", "sub_topic"]].rename(
    columns={"topic": "topic_df3", "sub_topic": "topic3_subtopics"}
)

# 4. Chain the joins sequentially to ensure zero overlapping column issues
result = topics_indexed.join(df2_to_join, how="left")
result = result.join(df3_to_join, how="left")

conditions = [
    (result["topic"] == 1) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 2) & (result["topic2_subtopics"] == 0),
    (result["topic"] == 7) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 2) & (result["topic2_subtopics"] == 1),
    (result["topic"] == 8) & (result["topic2_subtopics"].isna()),
    (result["topic"] == -1) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 2) & (result["topic2_subtopics"] == -1),
    (result["topic"] == 3) & (result["topic3_subtopics"] == -1),
    (result["topic"] == 2) & (result["topic2_subtopics"] == 4),
    (result["topic"] == 2) & (result["topic2_subtopics"] == 5),
    (result["topic"] == 3) & (result["topic3_subtopics"] == 1),
    (result["topic"] == 2) & (result["topic2_subtopics"] == 2),
    (result["topic"] == 2) & (result["topic2_subtopics"] == 3),
    (result["topic"] == 3) & (result["topic3_subtopics"] == 0),
    (result["topic"] == 4) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 5) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 9) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 0) & (result["topic2_subtopics"].isna()),
    (result["topic"] == 6) & (result["topic_df2"].isna()),
    (result["topic"] == 10) & (result["topic_df2"].isna()),
]

categories = [
    "App Experience",
    "App Experience",
    "Concierge/Named-Rep",
    "Emotional Support/Compassionate Care",
    "General Service Satisfaction",
    "General/Mixed Claims Narrative",
    "General/Mixed Claims Narrative",
    "General/Mixed Claims Narrative",
    "Pre-existing Condition/Denial",
    "Premium Increases",
    "Premium Increases",
    "Reimbursement/Payment Experience",
    "Reimbursement/Payment Experience",
    "Reimbursement/Payment Experience",
    "Reimbursement/Payment Experience",
    "Reimbursement/Payment Experience",
    "Short/Low-Content",
    "Sign-up/Enrollment",
    "Sign-up/Enrollment",
    "Website Experience & Pricing Perception",
]

result["theme"] = np.select(conditions, categories, default="Other")

# Save merged review + theme file
result.to_csv(OUTPUT_DIR / "reviews_with_themes.csv", index=False)
print("Saved: reviews_with_themes.csv")
