import pandas as pd
import theme_rules as tr

df = pd.read_csv("data/modeling/reviews_with_leaf.csv")
b5 = df[df["leaf"] == "5.-1"]
rule_rows, cancel_ids = tr.apply_rules(b5)

print(rule_rows.groupby("rule")["review_id"].nunique().sort_values(ascending=False))
print(len(b5), len(cancel_ids))

content = rule_rows[rule_rows.theme != tr.NAMED]
print(content.review_id.nunique(), "of", len(b5))
print(content.groupby("review_id").size().value_counts())

pairs = content.groupby("review_id")["theme"].apply(lambda s: " + ".join(sorted(s)))
print(pairs.value_counts().head(10))

unres = b5[~b5["review_id"].isin(content["review_id"])]
print(unres["rating"].describe())
print(unres["text"].str.split().str.len().describe())
for _, r in unres.sample(25, random_state=1).iterrows():
    print(f"[{r.rating:.0f}] {str(r.title)[:40]} :: {str(r.text)[:200]}")

raw, _ = tr.apply_rules(b5, max_themes=10)
raw_c = raw[raw.theme != tr.NAMED]
print(raw_c.groupby("review_id").size().value_counts())
print(raw_c.groupby("theme")["review_id"].nunique().sort_values(ascending=False))
