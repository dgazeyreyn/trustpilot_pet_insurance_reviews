"""
07_build_hierarchical_themes.py

Creates a final hierarchical theme dataset by:
1) Starting from baseline themes (reviews_with_themes.csv)
2) Refining ONLY "Other / Generic" via generic subtopics (other_generic_refined_reviews.csv)
3) Assigning Level 1 + Level 2 themes

Inputs:
- data/modeling/reviews_with_themes.csv
  expected columns: review_id, provider, rating, published_date, topic, theme, text

- data/modeling/other_generic_refined_reviews.csv
  expected to include: review_id, generic_subtopic_id, generic_subtopic_name
  (it may include additional columns; that's fine)

Output:
- data/modeling/reviews_with_hierarchical_themes.csv
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


# ----------------------------
# Config
# ----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "modeling"

BASELINE_FILE = DATA_DIR / "reviews_with_themes.csv"
REFINED_GENERIC_FILE = DATA_DIR / "other_generic_refined_reviews.csv"

OUTPUT_FILE = DATA_DIR / "reviews_with_hierarchical_themes.csv"

GENERIC_THEME_NAME = "Other / Generic"


# ----------------------------
# Mapping Tables
# ----------------------------
# Baseline theme -> (Level 1, Level 2)
BASELINE_THEME_MAP = {
    "Claims Ease": ("Claims Experience", "Claims Ease"),
    "Reimbursement Speed": ("Claims Experience", "Reimbursement Speed"),
    "App / Digital Experience": ("Digital Experience", "App UX"),
    "Customer Service / Claims Support": ("Claims Experience", "Customer Service / Claims Support"),
    # If you have other baseline themes later, add them here
}

# Generic subtopic id -> (Level 1, Level 2)
# Locked to final refined output from other_generic_subtopic_top_terms.csv

GENERIC_SUBTOPIC_MAP = {
    4: ("Claims Experience", "General Claims Experience"),
    2: ("Billing & Policy", "Billing & Cancellation Issues"),
    3: ("Digital Experience", "Digital Claims Submission"),
    1: ("Onboarding", "Enrollment Experience"),
    0: ("Sentiment Signals", "Strong Negative Ratings"),
    -1: ("Other", "Residual / Edge Cases"),
}


# ----------------------------
# Helpers
# ----------------------------
def require_cols(df: pd.DataFrame, needed: set[str], name: str) -> None:
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing required columns: {missing}")


def normalize_lower_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def safe_int(x):
    """Convert topic id to int if possible, else return None."""
    try:
        if pd.isna(x):
            return None
        return int(x)
    except Exception:
        return None


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    print(f"Reading baseline: {BASELINE_FILE}")
    if not BASELINE_FILE.exists():
        raise FileNotFoundError(f"Not found: {BASELINE_FILE}")

    df = pd.read_csv(BASELINE_FILE)
    df = normalize_lower_cols(df)

    require_cols(df, {"review_id", "provider", "rating", "published_date", "theme", "text"}, "reviews_with_themes.csv")

    # Normalize provider values
    df["provider"] = df["provider"].astype(str).str.strip().str.lower()

    # Parse published_date (optional but useful)
    df["published_date"] = pd.to_datetime(df["published_date"], utc=True, errors="coerce")

    # Default hierarchical columns
    df["level_1_theme"] = None
    df["level_2_theme"] = None
    df["theme_source"] = "baseline"  # will override for refined generic

    # Apply baseline mapping for non-generic themes
    non_generic_mask = df["theme"].astype(str).str.strip() != GENERIC_THEME_NAME

    def map_baseline(theme: str):
        theme = (theme or "").strip()
        return BASELINE_THEME_MAP.get(theme, (None, None))

    mapped = df.loc[non_generic_mask, "theme"].apply(map_baseline)
    df.loc[non_generic_mask, "level_1_theme"] = mapped.apply(lambda t: t[0])
    df.loc[non_generic_mask, "level_2_theme"] = mapped.apply(lambda t: t[1])

    # If any baseline themes are unmapped, keep them visible (so you notice and can decide)
    # We'll fall back to: Level1="Other", Level2=<original theme>
    unmapped_mask = non_generic_mask & df["level_1_theme"].isna()
    if unmapped_mask.any():
        unmapped_vals = df.loc[unmapped_mask, "theme"].value_counts().head(10)
        print("\nWarning: Unmapped baseline themes found (showing up to 10):")
        print(unmapped_vals.to_string())

        df.loc[unmapped_mask, "level_1_theme"] = "Other"
        df.loc[unmapped_mask, "level_2_theme"] = df.loc[unmapped_mask, "theme"].astype(str).str.strip()

    # Now refine generic themes using the refined file
    generic_mask = df["theme"].astype(str).str.strip() == GENERIC_THEME_NAME
    print(f"\nBaseline rows total: {len(df):,}")
    print(f'Rows with theme == "{GENERIC_THEME_NAME}": {generic_mask.sum():,}')

    if generic_mask.any():
        print(f"Reading refined generic: {REFINED_GENERIC_FILE}")
        if not REFINED_GENERIC_FILE.exists():
            raise FileNotFoundError(
                f"Generic refinement file not found: {REFINED_GENERIC_FILE}\n"
                f"Run modeling/06_refine_generic_theme.py first."
            )

        df_ref = pd.read_csv(REFINED_GENERIC_FILE)
        df_ref = normalize_lower_cols(df_ref)

        require_cols(df_ref, {"review_id", "generic_subtopic_id"}, "other_generic_refined_reviews.csv")

        # Ensure topic id is int
        df_ref["generic_subtopic_id"] = df_ref["generic_subtopic_id"].apply(safe_int)

        # Keep only the columns we need for merge (avoid duplicate column collisions)
        keep_cols = ["review_id", "generic_subtopic_id"]
        if "generic_subtopic_name" in df_ref.columns:
            keep_cols.append("generic_subtopic_name")

        df_ref = df_ref[keep_cols].copy()

        # Deduplicate in case of any duplicates (shouldn't happen, but safe)
        df_ref = df_ref.drop_duplicates(subset=["review_id"])

        # Merge into baseline
        df = df.merge(df_ref, on="review_id", how="left")

        # Assign hierarchical themes for generic rows
        def map_generic_subtopic(tid):
            if tid is None:
                return (None, None)
            return GENERIC_SUBTOPIC_MAP.get(tid, ("Other", "Residual / Edge Cases"))

        generic_mapped = df.loc[generic_mask, "generic_subtopic_id"].apply(map_generic_subtopic)
        df.loc[generic_mask, "level_1_theme"] = generic_mapped.apply(lambda t: t[0])
        df.loc[generic_mask, "level_2_theme"] = generic_mapped.apply(lambda t: t[1])
        df.loc[generic_mask, "theme_source"] = "refined_generic"

        # If any generic rows didn't get a subtopic id (should be rare if refinement used same baseline file)
        missing_ref = generic_mask & df["generic_subtopic_id"].isna()
        if missing_ref.any():
            print(
                f"\nWarning: {missing_ref.sum():,} generic rows did not find a matching refined subtopic.\n"
                f"These will be labeled as Residual / Edge Cases."
            )
            df.loc[missing_ref, "level_1_theme"] = "Other"
            df.loc[missing_ref, "level_2_theme"] = "Residual / Edge Cases"

    # Final sanity checks
    missing_levels = df["level_1_theme"].isna() | df["level_2_theme"].isna()
    if missing_levels.any():
        print(
            f"\nWarning: {missing_levels.sum():,} rows still missing hierarchical labels.\n"
            f"Filling with Level1='Other', Level2='Uncategorized'."
        )
        df.loc[missing_levels, "level_1_theme"] = df.loc[missing_levels, "level_1_theme"].fillna("Other")
        df.loc[missing_levels, "level_2_theme"] = df.loc[missing_levels, "level_2_theme"].fillna("Uncategorized")

    # Order columns nicely
    preferred_order = [
        "review_id",
        "provider",
        "rating",
        "published_date",
        "topic",
        "theme",
        "generic_subtopic_id",
        "generic_subtopic_name",
        "level_1_theme",
        "level_2_theme",
        "theme_source",
        "text",
    ]
    # Keep only columns that exist, plus any extras at the end
    cols_in_df = [c for c in preferred_order if c in df.columns]
    extras = [c for c in df.columns if c not in cols_in_df]
    df = df[cols_in_df + extras]

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved final hierarchical dataset → {OUTPUT_FILE}")
    print("\nQuick check: Level 2 theme distribution (top 15):")
    print(df["level_2_theme"].value_counts().head(15).to_string())


if __name__ == "__main__":
    main()