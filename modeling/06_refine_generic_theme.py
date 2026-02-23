"""
06_refine_generic_theme.py

Hierarchical refinement of the "Other / Generic" theme using BERTopic.

Key choices:
- Train on ALL providers (consistent with baseline modeling)
- Remove provider tokens (ALL provider names/variants) from the corpus
  to avoid provider-name-driven subtopics.
- Use CountVectorizer with stopwords + bigrams for interpretability.

Input:
- data/modeling/reviews_with_themes.csv
  expected columns: review_id, provider, rating, published_date, topic, theme, text

Outputs:
- data/modeling/other_generic_refined_reviews.csv
- data/modeling/other_generic_subtopic_counts_by_provider.csv
- data/modeling/other_generic_subtopic_monthly_trends_by_provider.csv
- data/modeling/other_generic_subtopic_top_terms.csv
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from bertopic import BERTopic
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


# ----------------------------
# Config
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "modeling"

INPUT_FILE = DATA_DIR / "reviews_with_themes.csv"

OUTPUT_REFINED = DATA_DIR / "other_generic_refined_reviews.csv"
OUTPUT_COUNTS = DATA_DIR / "other_generic_subtopic_counts_by_provider.csv"
OUTPUT_TRENDS = DATA_DIR / "other_generic_subtopic_monthly_trends_by_provider.csv"
OUTPUT_TERMS = DATA_DIR / "other_generic_subtopic_top_terms.csv"

GENERIC_THEME_NAME = "Other / Generic"

# Refinement model settings (tune later)
MIN_TOPIC_SIZE = 75
NR_TOPICS = 20

DOMAIN_STOPWORDS = [
    "insurance",
    "pet",
    "dog",
    "vet",
    "company",
    "policy",
    "coverage",
    "years",
    "easy",
    "recommend",
    "best",
    "excellent",
    "happy",
    "love"
]

custom_stopwords = list(ENGLISH_STOP_WORDS.union(DOMAIN_STOPWORDS))

# Vectorizer settings (avoid stopword-heavy topics + prior min_df/max_df issue)
VECTORIZER = CountVectorizer(
    stop_words=custom_stopwords,
    ngram_range=(1, 2),
    min_df=1,
    max_df=0.95,
)


# ----------------------------
# Helpers
# ----------------------------
def require_cols(df: pd.DataFrame, needed: set[str], name: str) -> None:
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "provider" in df.columns:
        df["provider"] = df["provider"].astype(str).str.strip().str.lower()
    return df


def build_provider_aliases(all_providers: list[str]) -> list[str]:
    """
    Build provider name variants to remove from text:
    - raw provider values
    - underscore -> space variants
    - concatenated variants for spaced ones
    - manual aliases for common concatenated brand keys
    """
    aliases = set()

    for p in all_providers:
        if not p:
            continue
        p = str(p).strip().lower()
        if not p:
            continue

        aliases.add(p)
        aliases.add(p.replace("_", " "))
        aliases.add(p.replace(" ", ""))  # catch "healthy paws" -> "healthypaws"

    # Manual aliases for common concatenated brand keys (extend if you see leakage)
    manual = {
        "healthypaws": ["healthy paws"],
        "petsbest": ["pets best"],
        "manypets": ["many pets"],
        "nationwide": ["nation wide"],  # optional
        "metlife": ["met life"],        # optional
    }

    for k, vals in manual.items():
        if k in aliases:
            for v in vals:
                aliases.add(v)
                aliases.add(v.replace(" ", ""))

    return sorted(aliases)


def compile_provider_regex(aliases: list[str]) -> re.Pattern:
    """
    Compile a single regex that matches any provider alias with flexible whitespace.
    Example: "healthy paws" matches "healthy    paws".
    """
    parts = []
    for a in aliases:
        a = a.strip().lower()
        if not a:
            continue

        # escape, then allow flexible whitespace between tokens
        escaped = re.escape(a)
        escaped = re.sub(r"\\\s+", r"\\s+", escaped)
        parts.append(escaped)

    # Case-insensitive, word boundaries
    pattern = r"(?i)\b(" + "|".join(parts) + r")\b"
    return re.compile(pattern)


def clean_for_refine(text: str, provider_re: re.Pattern) -> str:
    """
    Minimal but effective cleaning:
    - lowercase
    - normalize punctuation to spaces
    - remove provider aliases
    - collapse whitespace
    """
    if not isinstance(text, str):
        return ""

    t = text.lower()

    # Normalize punctuation to avoid missing tokens like "Healthy-Paws"
    t = re.sub(r"[^a-z0-9\s]", " ", t)

    # Remove provider names
    t = provider_re.sub(" ", t)

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    print(f"Reading: {INPUT_FILE}")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)
    df = normalize_columns(df)

    require_cols(df, {"review_id", "provider", "theme", "text"}, "reviews_with_themes.csv")

    # Parse published_date -> month (for trends)
    if "published_date" in df.columns:
        df["published_date"] = pd.to_datetime(df["published_date"], utc=True, errors="coerce")
        df["month"] = df["published_date"].dt.to_period("M").dt.to_timestamp()
    else:
        df["month"] = pd.NaT

    # Filter to Other / Generic (ALL providers)
    df_generic = df[df["theme"].astype(str).str.strip() == GENERIC_THEME_NAME].copy()
    print(f'Rows in "{GENERIC_THEME_NAME}" (all providers): {len(df_generic):,}')
    if df_generic.empty:
        raise RuntimeError(f'No rows found for theme == "{GENERIC_THEME_NAME}".')

    # Build provider alias regex from ALL providers present in the dataset
    all_providers = (
        df["provider"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
        .unique()
        .tolist()
    )

    aliases = build_provider_aliases(all_providers)
    provider_re = compile_provider_regex(aliases)

    # Clean docs
    df_generic["clean_text"] = df_generic["text"].apply(lambda t: clean_for_refine(t, provider_re))

    # Drop empty docs
    df_generic = df_generic[df_generic["clean_text"].str.len() > 0].copy()
    docs = df_generic["clean_text"].tolist()

    print(f"Docs to model after cleaning: {len(docs):,}")
    if len(docs) < 300:
        print("Warning: small corpus; consider lowering MIN_TOPIC_SIZE.")

    # Train refinement topic model
    print("Training BERTopic refinement model...")
    topic_model = BERTopic(
        min_topic_size=MIN_TOPIC_SIZE,
        nr_topics=NR_TOPICS,
        vectorizer_model=VECTORIZER,
        calculate_probabilities=False,
        verbose=True,
    )

    topics, _ = topic_model.fit_transform(docs)
    df_generic["generic_subtopic_id"] = topics

    # Topic info + mapping
    info = topic_model.get_topic_info()
    name_map = dict(zip(info["Topic"], info["Name"]))
    df_generic["generic_subtopic_name"] = df_generic["generic_subtopic_id"].map(name_map)

    # Save row-level output
    OUTPUT_REFINED.parent.mkdir(parents=True, exist_ok=True)
    df_generic.to_csv(OUTPUT_REFINED, index=False)
    print(f"Saved refined review assignments → {OUTPUT_REFINED}")

    # Provider x subtopic counts
    counts = (
        df_generic.groupby(["provider", "generic_subtopic_id", "generic_subtopic_name"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values(["provider", "count"], ascending=[True, False])
    )
    counts.to_csv(OUTPUT_COUNTS, index=False)
    print(f"Saved provider x subtopic counts → {OUTPUT_COUNTS}")

    # Monthly trends
    if df_generic["month"].notna().any():
        trends = (
            df_generic.dropna(subset=["month"])
            .groupby(["provider", "generic_subtopic_id", "generic_subtopic_name", "month"], as_index=False)
            .size()
            .rename(columns={"size": "count"})
            .sort_values(["provider", "generic_subtopic_id", "month"])
        )
        trends.to_csv(OUTPUT_TRENDS, index=False)
        print(f"Saved monthly trends → {OUTPUT_TRENDS}")
    else:
        print("No valid month values found; skipping trend output.")

    # Top terms table
    rows = []
    for tid in info["Topic"].tolist():
        words = topic_model.get_topic(tid)
        if not words:
            continue
        top_terms = [w for w, _ in words[:10]]
        rows.append(
            {
                "generic_subtopic_id": tid,
                "generic_subtopic_name": name_map.get(tid, ""),
                "top_terms": ", ".join(top_terms),
                "count": int(info.loc[info["Topic"] == tid, "Count"].iloc[0]),
            }
        )

    terms_df = pd.DataFrame(rows).sort_values("count", ascending=False)
    terms_df.to_csv(OUTPUT_TERMS, index=False)
    print(f"Saved top terms table → {OUTPUT_TERMS}")

    print("\nDone.")


if __name__ == "__main__":
    main()