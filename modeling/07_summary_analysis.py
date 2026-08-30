import pandas as pd
from pathlib import Path
import numpy as np

# Set max rows to 50
pd.set_option('display.max_rows', 15)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
INPUT  = BASE_DIR / "data" / "modeling" / "reviews_with_themes_sentiment.csv"
OUTPUT_DIR    = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT)

# ----------------------------
# Summary Analysis
# ----------------------------

# 1. Theme counts by provider
theme_counts = df.groupby(['provider','theme']).size().reset_index(name='count')
theme_counts.to_csv(OUTPUT_DIR / "theme_counts_by_provider.csv", index=False)
print("Saved: theme_counts_by_provider.csv")

# 2. Theme average rating by provider
theme_ratings = df.groupby(['provider','theme'])['rating'].mean().reset_index(name='avg_rating')
theme_ratings.to_csv(OUTPUT_DIR / "theme_avg_rating_by_provider.csv", index=False)
print("Saved: theme_avg_rating_by_provider.csv")

# 3. Monthly trends of themes by provider
df['published_date'] = pd.to_datetime(df['published_date'], errors='coerce')
df['year_month'] = df['published_date'].dt.to_period('M')

monthly_trends = df.groupby(['provider','theme','year_month']).size().reset_index(name='count')
monthly_trends.to_csv(OUTPUT_DIR / "theme_monthly_trends_by_provider.csv", index=False)
print("Saved: theme_monthly_trends_by_provider.csv")

# 4. Theme average sentiment score by provider
theme_sentiment = df.groupby(['provider','theme'])['sentiment_score'].mean().reset_index(name='avg_sentiment_score')
theme_sentiment.to_csv(OUTPUT_DIR / "theme_avg_sentiment_by_provider.csv", index=False)
print("Saved: theme_avg_sentiment_by_provider.csv")

# 5. Rating vs. sentiment correlation by theme  
theme_corr = (
    df.groupby('theme')
      .agg(correlation=('sentiment_score', lambda x: x.corr(df.loc[x.index, 'rating'])))
      .reset_index()
)

theme_corr.to_csv(OUTPUT_DIR / "rating_vs_sentiment_corr_by_theme.csv", index=False)
print("Saved: rating_vs_sentiment_corr_by_theme.csv")

# 6. Rating vs. sentiment correlation by provider
provider_corr = (
    df.groupby('provider')
      .agg(correlation=('sentiment_score', lambda x: x.corr(df.loc[x.index, 'rating'])))
      .reset_index()
)
provider_corr.to_csv(OUTPUT_DIR / "rating_vs_sentiment_corr_by_provider.csv", index=False)
print("Saved: rating_vs_sentiment_corr_by_provider.csv")

# 7. Rating vs. sentiment correlation by provider by theme
provider_theme_corr = (
    df.groupby(['provider', 'theme'])
      .agg(correlation=('sentiment_score', lambda x: x.corr(df.loc[x.index, 'rating'])))
      .reset_index()
)
provider_theme_corr.to_csv(OUTPUT_DIR / "rating_vs_sentiment_corr_by_provider_theme.csv", index=False)
print("Saved: rating_vs_sentiment_corr_by_provider_theme.csv")