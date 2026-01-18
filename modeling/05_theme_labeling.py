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

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
INPUT_REVIEWS = BASE_DIR / "data" / "modeling" / "reviews_for_modeling.csv"
INPUT_TOPICS  = BASE_DIR / "data" / "modeling" / "reviews_with_topics.csv"
OUTPUT_DIR    = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
reviews = pd.read_csv(INPUT_REVIEWS)
topics  = pd.read_csv(INPUT_TOPICS)

# ----------------------------
# Topic → Theme Mapping
# ----------------------------
topic_map = {
    -1: "Other / Generic",
     0: "Other / Generic",
     1: "Customer Service / Claims Support",
     2: "App / Digital Experience",
     3: "Other / Generic",
     4: "Reimbursement Speed",
     5: "Claims Ease"
}

# ----------------------------
# Merge topics with reviews
# ----------------------------
reviews_topics = reviews.merge(
    topics[['review_id', 'topic']],
    on='review_id',
    how='left'
)

# Map human-readable theme
reviews_topics['theme'] = reviews_topics['topic'].map(topic_map)

# Reorder columns for clarity
reviews_topics = reviews_topics[['review_id','provider','rating','published_date','topic','theme','text']]

# Save merged review + theme file
reviews_topics.to_csv(OUTPUT_DIR / "reviews_with_themes.csv", index=False)
print("Saved: reviews_with_themes.csv")

# ----------------------------
# Aggregations for Tableau
# ----------------------------

# 1. Theme counts by provider
theme_counts = reviews_topics.groupby(['provider','theme']).size().reset_index(name='count')
theme_counts.to_csv(OUTPUT_DIR / "theme_counts_by_provider.csv", index=False)
print("Saved: theme_counts_by_provider.csv")

# 2. Theme average rating by provider
theme_ratings = reviews_topics.groupby(['provider','theme'])['rating'].mean().reset_index(name='avg_rating')
theme_ratings.to_csv(OUTPUT_DIR / "theme_avg_rating_by_provider.csv", index=False)
print("Saved: theme_avg_rating_by_provider.csv")

# 3. Monthly trends of themes by provider
reviews_topics['published_date'] = pd.to_datetime(reviews_topics['published_date'], errors='coerce')
reviews_topics['year_month'] = reviews_topics['published_date'].dt.to_period('M')

monthly_trends = reviews_topics.groupby(['provider','theme','year_month']).size().reset_index(name='count')
monthly_trends.to_csv(OUTPUT_DIR / "theme_monthly_trends_by_provider.csv", index=False)
print("Saved: theme_monthly_trends_by_provider.csv")

print("All Tableau-ready outputs created successfully!")