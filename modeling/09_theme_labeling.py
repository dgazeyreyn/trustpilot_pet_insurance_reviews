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
pd.set_option('display.max_rows', 15)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
# INPUT_REVIEWS = BASE_DIR / "data" / "modeling" / "reviews_for_modeling.csv"
INPUT_TOPICS  = BASE_DIR / "data" / "modeling" / "reviews_with_topics.csv"
INPUT_SUBTOPICS  = BASE_DIR / "data" / "modeling" / "reviews_with_topic1_subtopics.csv"
OUTPUT_DIR    = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
topics = pd.read_csv(INPUT_TOPICS)
subtopics  = pd.read_csv(INPUT_SUBTOPICS)

# ----------------------------
# Join data
# ----------------------------
topics_indexed = topics.set_index('review_id')
subtopics_indexed = subtopics.set_index('review_id')
result = topics_indexed.join(subtopics_indexed[['topic']], rsuffix='_df2')

conditions = [
    (result['topic'] == 1) & (result['topic_df2'] == 0),
    (result['topic'] == 2) & (result['topic_df2'].isna()),
    (result['topic'] == 4) & (result['topic_df2'].isna()),
    (result['topic'] == 6) & (result['topic_df2'].isna()),
    (result['topic'] == 1) & (result['topic_df2'] == 1),
    (result['topic'] == 8) & (result['topic_df2'].isna()),
    (result['topic'] == 1) & (result['topic_df2'] == -1),
    (result['topic'] == 3) & (result['topic_df2'].isna()),
    (result['topic'] == 1) & (result['topic_df2'] == 6),
    (result['topic'] == 1) & (result['topic_df2'] == 5),
    (result['topic'] == 1) & (result['topic_df2'].isin([2, 4])),
    (result['topic'] == 5) & (result['topic_df2'].isna()),
    (result['topic'] == -1) & (result['topic_df2'].isna()),
    (result['topic'] == 9) & (result['topic_df2'].isna()),
    (result['topic'] == 10) & (result['topic_df2'].isna()),
    (result['topic'] == 0) & (result['topic_df2'].isna()),
    (result['topic'] == 1) & (result['topic_df2'] == 3),
    (result['topic'] == 7) & (result['topic_df2'].isna())
]

categories = [
    'App Experience',
    'App Experience',
    'Claims Filing Process',
    'Concierge/Named-Rep',
    'Emotional Support/Compassionate Care',
    'General Service Satisfaction',
    'General/Mixed Claims Narrative',
    'Policy Administration & Billing',
    'Pre-existing Condition/Denial',
    'Premium Increases',
    'Reimbursement/Payment Experience',
    'Reimbursement/Payment Experience',
    'Short/Low-Content',
    'Short/Low-Content',
    'Short/Low-Content',
    'Sign-up/Enrollment',
    'Sign-up/Enrollment',
    'Sign-up/Enrollment'
]

result['theme'] = np.select(
    conditions,
    categories,
    default='Other'
)

# Save merged review + theme file
result.to_csv(OUTPUT_DIR / "reviews_with_themes.csv", index=False)
print("Saved: reviews_with_themes.csv")