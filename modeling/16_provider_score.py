import pandas as pd
import numpy as np
from pathlib import Path

# Set max rows to 50
pd.set_option("display.max_rows", 15)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
LONG_THEME = BASE_DIR / "data" / "modeling" / "site_update_files" / "long_theme_df.csv"
INPUT_FILE = BASE_DIR / "data" / "modeling" / "reviews_with_themes_sentiment.csv"
OUTPUT_DIR = BASE_DIR / "data" / "modeling" / "site_update_files"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT_FILE)
long_theme_df = pd.read_csv(LONG_THEME)

# ----------------------------
# Provider-level weighted score
# ----------------------------
theme_weights = {
    "Pre-existing Condition/Denial": 0.20,
    "Premium Increases": 0.15,
    "Claims Filing Process": 0.15,
    "Reimbursement/Payment Experience": 0.15,
    "General Service Satisfaction": 0.10,
    "Concierge/Named-Rep": 0.05,
    "App Experience": 0.05,
    "Sign-up/Enrollment": 0.05,
    "Emotional Support/Compassionate Care": 0.05,
    "Website Experience & Pricing Perception": 0.05,  # <-- still need your confirmation on this
    "General/Mixed Claims Narrative": 0.0,
    "Short/Low-Content": 0.0,
}

excluded_sentiment_themes = ["Premium Increases", "Pre-existing Condition/Denial"]


def compute_theme_score(row):
    if row["theme"] in excluded_sentiment_themes:
        return row["avg_rating"]
    sentiment_scaled = (row["avg_sentiment_score"] + 1) * 2 + 1
    return 0.7 * row["avg_rating"] + 0.3 * sentiment_scaled


def assign_tier(score):
    if score >= 4.5:
        return "Excellent"
    if score >= 4.0:
        return "Very Good"
    if score >= 3.5:
        return "Good"
    if score >= 3.0:
        return "Fair"
    return "Below Average"


def provider_score(
    provider, long_theme_df, total_reviews_by_provider, n_threshold=20, n_ref=500
):
    sub = long_theme_df[long_theme_df["provider"] == provider].copy()
    sub["weight"] = sub["theme"].map(theme_weights)
    eligible = sub[(sub["reviews"] >= n_threshold) & (sub["weight"] > 0)].copy()
    if eligible.empty:
        return None
    eligible["theme_score"] = eligible.apply(compute_theme_score, axis=1)
    base_score = np.average(eligible["theme_score"], weights=eligible["weight"])
    confidence = min(
        1.0, np.log1p(total_reviews_by_provider[provider]) / np.log1p(n_ref)
    )
    return base_score * confidence


total_reviews_by_provider = df.groupby("provider").size().to_dict()
providers = long_theme_df["provider"].unique()
scores = {
    p: provider_score(p, long_theme_df, total_reviews_by_provider) for p in providers
}

scores_df = pd.Series(scores, name="provider_score").reset_index()
scores_df.columns = ["provider", "provider_score"]
scores_df["tier"] = scores_df["provider_score"].apply(assign_tier)
scores_df = scores_df.sort_values("provider_score", ascending=False).reset_index(
    drop=True
)

scores_df.to_csv(OUTPUT_DIR / "provider_scores.csv", index=False)
print(scores_df)
