import nltk
nltk.download('vader_lexicon')
from nltk.sentiment import SentimentIntensityAnalyzer
import pandas as pd
from pathlib import Path

# Set max rows to 50
pd.set_option('display.max_rows', 15)

# ----------------------------
# Paths
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]  # adjust if running from project root
INPUT  = BASE_DIR / "data" / "modeling" / "reviews_with_themes.csv"
OUTPUT_DIR    = BASE_DIR / "data" / "modeling"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Load data
# ----------------------------
df = pd.read_csv(INPUT)

sia = SentimentIntensityAnalyzer()

def get_sentiment(text):
    if not isinstance(text, str) or not text.strip():
        return None
    return sia.polarity_scores(text)['compound']

df['sentiment_score'] = df['text'].apply(get_sentiment)

# Save merged review + theme file
df.to_csv(OUTPUT_DIR / "reviews_with_themes_sentiment.csv", index=False)
print("Saved: reviews_with_themes_sentiment.csv")