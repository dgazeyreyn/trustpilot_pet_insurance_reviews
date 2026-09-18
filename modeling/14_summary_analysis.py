import pandas as pd
from pathlib import Path
import numpy as np

# Set max rows to 50
pd.set_option("display.max_rows", 15)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
INPUT_FILE = BASE_DIR / "data" / "modeling" / "reviews_with_themes_sentiment.csv"
OUTPUT_DIR = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT_FILE)

# ----------------------------
# Summary Analysis
# ----------------------------

# 1. Theme counts by provider
theme_counts = df.groupby(["provider", "theme"]).size().reset_index(name="count")
theme_counts.to_csv(
    OUTPUT_DIR / "summary_analysis" / "theme_counts_by_provider.csv", index=False
)
print("Saved: theme_counts_by_provider.csv")

# 2. Theme average rating by provider
theme_ratings = (
    df.groupby(["provider", "theme"])
    .agg(avg_sentiment_score=("rating", "mean"), count=("rating", "count"))
    .reset_index()
)
theme_ratings.to_csv(
    OUTPUT_DIR / "summary_analysis" / "theme_avg_rating_by_provider.csv", index=False
)
print("Saved: theme_avg_rating_by_provider.csv")

# 3. Monthly trends of themes by provider
df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
df["year_month"] = df["published_date"].dt.to_period("M")

monthly_trends = (
    df.groupby(["provider", "theme", "year_month"]).size().reset_index(name="count")
)
monthly_trends.to_csv(
    OUTPUT_DIR / "summary_analysis" / "theme_monthly_trends_by_provider.csv",
    index=False,
)
print("Saved: theme_monthly_trends_by_provider.csv")

# 4. Theme average sentiment score by provider
theme_sentiment = (
    df.groupby(["provider", "theme"])
    .agg(
        avg_sentiment_score=("sentiment_score", "mean"),
        count=("sentiment_score", "count"),
    )
    .reset_index()
)
theme_sentiment.to_csv(
    OUTPUT_DIR / "summary_analysis" / "theme_avg_sentiment_by_provider.csv", index=False
)
print("Saved: theme_avg_sentiment_by_provider.csv")

# 5. Rating vs. sentiment correlation by theme
theme_corr = (
    df.groupby("theme")
    .agg(correlation=("sentiment_score", lambda x: x.corr(df.loc[x.index, "rating"])))
    .reset_index()
)

theme_corr.to_csv(
    OUTPUT_DIR / "summary_analysis" / "rating_vs_sentiment_corr_by_theme.csv",
    index=False,
)
print("Saved: rating_vs_sentiment_corr_by_theme.csv")

# 6. Rating vs. sentiment correlation by provider
provider_corr = (
    df.groupby("provider")
    .agg(correlation=("sentiment_score", lambda x: x.corr(df.loc[x.index, "rating"])))
    .reset_index()
)
provider_corr.to_csv(
    OUTPUT_DIR / "summary_analysis" / "rating_vs_sentiment_corr_by_provider.csv",
    index=False,
)
print("Saved: rating_vs_sentiment_corr_by_provider.csv")

# 7. Rating vs. sentiment correlation by provider by theme
provider_theme_corr = (
    df.groupby(["provider", "theme"])
    .agg(correlation=("sentiment_score", lambda x: x.corr(df.loc[x.index, "rating"])))
    .reset_index()
)
provider_theme_corr.to_csv(
    OUTPUT_DIR / "summary_analysis" / "rating_vs_sentiment_corr_by_provider_theme.csv",
    index=False,
)
print("Saved: rating_vs_sentiment_corr_by_provider_theme.csv")

# 8. Average rating by provider
avg_rating_by_provider = (
    df.groupby(["provider"])
    .agg(avg_rating=("rating", "mean"), count=("rating", "count"))
    .reset_index()
)
avg_rating_by_provider.to_csv(
    OUTPUT_DIR / "site_update_files" / "avg_rating_by_provider.csv", index=False
)
print("Saved: avg_rating_by_provider.csv")

# 9. Average rating by theme
avg_rating_by_theme = (
    df.groupby(["theme"])
    .agg(avg_rating=("rating", "mean"), count=("rating", "count"))
    .reset_index()
)
avg_rating_by_theme.to_csv(
    OUTPUT_DIR / "summary_analysis" / "avg_rating_by_theme.csv", index=False
)
print("Saved: avg_rating_by_theme.csv")

# 10. Average sentiment by provider
avg_sentiment_by_provider = (
    df.groupby(["provider"])
    .agg(
        avg_sentiment_score=("sentiment_score", "mean"),
        count=("sentiment_score", "count"),
    )
    .reset_index()
)
avg_sentiment_by_provider.to_csv(
    OUTPUT_DIR / "site_update_files" / "avg_sentiment_by_provider.csv", index=False
)
print("Saved: avg_sentiment_by_provider.csv")

# 11. Average sentiment by theme
avg_sentiment_by_theme = (
    df.groupby(["theme"])
    .agg(
        avg_sentiment_score=("sentiment_score", "mean"),
        count=("sentiment_score", "count"),
    )
    .reset_index()
)
avg_sentiment_by_theme.to_csv(
    OUTPUT_DIR / "summary_analysis" / "avg_sentiment_by_theme.csv", index=False
)
print("Saved: avg_sentiment_by_theme.csv")

# 12.  Min/Max Published Date
min_max_dates = df["published_date"].agg(["min", "max"])
min_max_dates.to_csv(
    OUTPUT_DIR / "site_update_files" / "min_max_published_date.csv", index=False
)

# 13.  Random sample of reviews by theme
sample_reviews = (
    df.groupby(["theme"])
    .apply(lambda x: x.sample(n=15, random_state=42))
    .reset_index(drop=True)
)
sample_reviews.to_csv(
    OUTPUT_DIR / "site_update_files" / "sample_reviews_by_theme.csv", index=False
)

# 14.  Total Reviews Count
total_reviews_count = df["rating"].count()

# Convert the number into a DataFrame
output_df = pd.DataFrame({"total_reviews": [total_reviews_count]})

# Now you can successfully use .to_csv()
output_df.to_csv(OUTPUT_DIR / "site_update_files" / "total_reviews.csv", index=False)
