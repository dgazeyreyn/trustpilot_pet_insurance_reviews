import pandas as pd
import numpy as np
from pathlib import Path

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
# Summarize data
# ----------------------------
long_theme_df = df.groupby(['provider', 'theme'], as_index=False).agg(
    avg_rating=('rating', 'mean'),
    avg_sentiment_score=('sentiment_score', 'mean'),
    reviews=('rating', 'count')
)

# ----------------------------
# Theme classification
# ----------------------------
risk_themes = ['Pre-existing Condition/Denial', 'Premium Increases',
               'Policy Administration & Billing', 'General/Mixed Claims Narrative']
quality_themes = ['Concierge/Named-Rep', 'Emotional Support/Compassionate Care',
                   'General Service Satisfaction', 'App Experience',
                   'Claims Filing Process', 'Reimbursement/Payment Experience',
                   'Sign-up/Enrollment']


def build_flag_table(long_theme_df, n_threshold=20, index_threshold=200,
                      z_threshold=1.0, std_floor=0.05):
    """
    Builds a table of provider/theme flags (red = risk, green = quality) from two
    independent signals:
      - frequency: this provider's share of a theme vs. its overall corpus share (index)
      - severity: how this provider's theme-level score compares to peers (z-score)

    For themes where rating has near-zero variance across providers (e.g. Concierge,
    where nearly everyone scores ~5.0), the severity z-score falls back to sentiment,
    which has real spread and can actually discriminate between providers.

    Each flag is tagged with signal_type: 'frequency', 'severity', or 'both' —
    so a high-volume-but-unremarkable flag is never displayed the same way as a
    severity-confirmed one.
    """
    df = long_theme_df[long_theme_df['reviews'] >= n_threshold].copy()

    # --- Index: this provider's share of the theme vs. its share of the overall corpus ---
    theme_totals = df.groupby('theme')['reviews'].transform('sum')
    provider_totals = df.groupby('provider')['reviews'].transform('sum')
    grand_total = df['reviews'].sum()
    df['pct_of_theme'] = df['reviews'] / theme_totals
    df['pct_of_overall'] = provider_totals / grand_total
    df['index'] = (df['pct_of_theme'] / df['pct_of_overall']) * 100

    # --- Z-score: rating-based by default, sentiment-based when rating has ~no variance ---
    theme_stats = df.groupby('theme').agg(
        rating_mean=('avg_rating', 'mean'),
        rating_std=('avg_rating', 'std'),
        sentiment_mean=('avg_sentiment_score', 'mean'),
        sentiment_std=('avg_sentiment_score', 'std'),
    ).reset_index()
    df = df.merge(theme_stats, on='theme')

    df['z_basis'] = np.where(df['rating_std'] < std_floor, 'sentiment', 'rating')
    df['z_score'] = np.where(
        df['z_basis'] == 'sentiment',
        (df['avg_sentiment_score'] - df['sentiment_mean']) / df['sentiment_std'],
        (df['avg_rating'] - df['rating_mean']) / df['rating_std'],
    )

    # --- Determine flags ---
    flags = []
    for _, row in df.iterrows():
        is_index_hit = row['index'] > index_threshold
        is_red_severity = row['z_score'] <= -z_threshold
        is_green_severity = row['z_score'] >= z_threshold

        if row['theme'] in risk_themes and (is_index_hit or is_red_severity):
            signal_type = 'both' if (is_index_hit and is_red_severity) else \
                          ('severity' if is_red_severity else 'frequency')
            flags.append({**row.to_dict(), 'flag_type': 'red', 'signal_type': signal_type})

        if row['theme'] in quality_themes and (is_index_hit or is_green_severity):
            signal_type = 'both' if (is_index_hit and is_green_severity) else \
                          ('severity' if is_green_severity else 'frequency')
            flags.append({**row.to_dict(), 'flag_type': 'green', 'signal_type': signal_type})

    flags_df = pd.DataFrame(flags)
    if flags_df.empty:
        return flags_df

    # --- Rank for capping: 'both' > 'severity' > 'frequency' ---
    signal_rank = {'both': 2, 'severity': 1, 'frequency': 0}
    flags_df['signal_rank'] = flags_df['signal_type'].map(signal_rank)
    flags_df['severity'] = flags_df['z_score'].abs().fillna(0)

    return flags_df.sort_values(['signal_rank', 'severity'], ascending=False)


def top_flags_by_provider(flags_df, n=2):
    """Caps to the strongest N flags per provider/flag_type, prioritizing
    'both'-signal flags first, then severity-only, then frequency-only."""
    return (flags_df.groupby(['provider', 'flag_type'])
                     .head(n)
                     .reset_index(drop=True))
    
flags_df = build_flag_table(long_theme_df, n_threshold=20, index_threshold=200,
                              z_threshold=1.0, std_floor=0.05)
flags_df.to_csv(OUTPUT_DIR/'flags_df.csv', sep=',')

top_flags = top_flags_by_provider(flags_df, n=2)
top_flags.to_csv(OUTPUT_DIR/'top_flags.csv', sep=',')