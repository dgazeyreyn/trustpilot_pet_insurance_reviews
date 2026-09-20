"""
Leaf -> theme mapping and rule layer for the pet-insurance review pipeline.

Leaf naming (matches the nesting of the BERTopic runs):
  "<t>"        full-corpus topic t (not sub-clustered)         e.g. "0", "7"
  "<t>.<k>"    sub-topic k of a sub-clustered topic (2, 3, 5)  e.g. "5.1"
  "2.3.<k>"    sub-sub-topic k of topic 2 -> sub-topic 3       e.g. "2.3.1"
  outliers     "-1", "2.-1", "3.-1", "5.-1", "2.3.-1"

Ordering inside each list matters: the FIRST theme is the primary theme.
"""
import re
import pandas as pd

GENERAL = "General/Mixed Experience"
FILING = "Claim Filing Process"
TURNAROUND = "Claim Turnaround & Status"
REIMB = "Reimbursement/Payment Experience"
COVERAGE = "Coverage Scope & Limits"
DENIAL = "Pre-existing Condition/Denial"
PREMIUM = "Premium Increases"
SIGNUP = "Sign-up/Enrollment"
GSS = "General Service Satisfaction"
SHORT = "Short/Low-Content"
WEB = "Website Experience & Pricing Perception"
APP = "App Experience"
NAMED = "Concierge/Named-Rep"
EMOTIONAL = "Emotional Support/Compassionate Care"

LEAF_TO_THEMES = {
    "0":     [SIGNUP],
    "1":     [APP],
    "2.0":   [APP],
    "2.1":   [EMOTIONAL],
    "2.2":   [REIMB],
    "2.3.0": [SIGNUP],
    "2.3.1": [FILING, REIMB],          # dual-label
    "2.4":   [DENIAL],
    "2.5":   [PREMIUM],
    "3.0":   [GENERAL],
    "3.1":   [PREMIUM],
    "4":     [REIMB],
    "5.0":   [GSS],
    "5.1":   [FILING],
    "5.2":   [REIMB],
    "5.3":   [TURNAROUND],
    "6":     [SIGNUP],
    "7":     [NAMED],
    "8":     [GSS],
    "9":     [SHORT],
    "10":    [WEB],
}
OUTLIER_LEAVES = {"-1", "2.-1", "3.-1", "5.-1", "2.3.-1"}   # resolved by rules/centroids

# ---------------------------------------------------------------- rules
def rx(p):
    return re.compile(p, re.I)

CLAIM = rx(r"\b(claims?|submit\w*|fil(e|ed|ing)\b|reimburs\w*|vet bills?|invoices?|receipts?)")
EASE = rx(r"\b(easy|easier|simple|straight ?forward|seamless|smooth|breeze|painless|intuitive|hassle|user.?friendly|no problem)")
SPEED = rx(r"\b(quick|quickly|fast|prompt|promptly|speedy|timely|expedit\w*|turn ?around|immediate\w*|within (a |an |\d+ |\w+ )?(day|days|hours?|week|weeks)|a (few|couple) (of )?days)\b")
DELAY = rx(r"\b(still (in review|pending|waiting|not)|weeks|months|too long|took forever|taking forever|forever|delay\w*|slow|no update|waiting|long wait|never (paid|received))\b")
PAY = rx(r"\b(reimburs\w*|paid|payment|payout|pay(s)? out|deposit\w*|refund\w*|check|money)\b")
DENY = rx(r"\b(denied|deny|denial|refus\w*|rejected|excuse\w*|pre.?existing|scam|fraud\w*|hoops|wiggle|not pay|won.t pay|don.t pay|never pay|withhold\w*)\b")
COVER_LIMIT = rx(r"(not covered|isn.t covered|wasn.t covered|doesn.t cover|does not cover|don.t cover|won.t cover|wouldn.t cover|will not cover|refus\\w* to cover|hardly cover|covers? (very |so )?little|cover(s)? nothing|only (a )?(third|half|quarter|\\d+ ?%)|misleading|deceiv\w*|fine print|read the (policy|fine print)|exclusion\w*|waiting period|caps? on|capped|limit(s|ed)? (on|per|of)|annual limit|per incident|wellness (coverage|limit|plan)|exam fee|riders?|only (pay|cover|reimburs)\w* (a |about |\d+)|limited coverage|not enough coverage|coverage (is|was) (limited|poor|lacking))")
COVER_PRAISE = rx(r"\b(great|good|excellent|extensive|comprehensive|solid|amazing|fair|wonderful)\s+(plan\s+)?coverage\b|\bcoverage\b[^.]{0,20}\b(great|good|excellent|extensive|comprehensive|fair)\b")
PREM = rx(r"((premium|rate|price|cost)s?\b[^.]{0,40}(increas\w*|went up|hike\w*|rais\w*|skyrocket\w*|tripled|doubled|steep|too high|shot up|jump\w*)|(increas\w*|hike\w*|rais\w*)\b[^.]{0,20}(premium|rate|price|cost)s?|price hikes?)")
SIGN = rx(r"\b(sign(ed|ing)? up|enroll\w*|regist\w*|appl(y|ied|ication)|quote|purchas\w*|get(ting)? (it )?started|set ?up|choos\w* (a |the )?(plan|policy)|compar\w*|shopping)\b")
WEB_FAIL = rx(r"(website|web site|site|portal|app|log ?in|password|account|online (claim|system)|chat)\b[^.]{0,70}\b(down|not work\w*|doesn.t work|won.t work|unable|can.t|cannot|couldn.t|reset|error|froze|glitch\w*|crash\w*|never connects|hangs up|stopped working)")
WEB_FAIL2 = rx(r"\b(down|not work\w*|unable|can.t|cannot|couldn.t|froze|glitch\w*|stopped working)\b[^.]{0,50}\b(website|web site|portal|app|log ?in|password)")
SERVICE = rx(r"\b(service|customer (service|care|support)|rep(resentative)?s?|agents?|staff|helpful|friendly|knowledgeable|support|polite|courteous)\b")
STAGE = rx(r"\b(claims?|sign(ed|ing)? up|enroll\w*|appl(y|ication)|quote|purchas\w*|reimburs\w*|premium|coverages?|polic(y|ies)|renew\w*|cancel\w*)\b")
CANCEL = rx(r"\b(cancel\w*|auto.?renew\w*|lapse\w*|unauthori[sz]ed|charged me|didn.t realize)\b")

NON_NAMES = set("""
Embrace Fetch Spot Pumpkin Pumkin Trupanion Nationwide Metlife Met Life Prudent Figo Fego Figi Aspca Healthy Healthly Paws Pets Best Petsbest
Costco Lemonade Chewy Thank Thanks Great Very Excellent Always Highly Good Easy Quick Fast Simple Love Wonderful Amazing
Customer Service Insurance Pet Dog Cat Dogs Cats Have Had Has The My Our Your Their Everyone She He They There Which But Honestly Recently
Website Site Documents Deductible Price Cost Claims Claim Rep Payment Reimbursement Communication Onboarding Staff Health Florida German
Yorkie Shepherd Four Seasons Company Team Everything Nothing Someone Person Agent Agents Representative Representatives Support
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October November December
You Truly Coverage Overall Really American USA English Trustpilot Google Vet Vets Pawlicy Consumer Reports BBB Christmas Halloween
""".split())
NON_NAMES_L = {n.lower() for n in NON_NAMES}
NAME_TOK = r"[A-Z][a-z]{2,}"
ADJ = r"(?:helpful|friendly|kind|knowledgeable|patient|professional|great|amazing|wonderful|outstanding|excellent|pleasant|nice|awesome|efficient|personable|polite|courteous|thorough|quick|fantastic|lovely|informative|respectful|caring|super)"
NAME_2 = rf"(?:\s+(?:{NAME_TOK}|[A-Z]\.))?"
NAME_CTX = [
    re.compile(rf"\b(?:spoke (?:with|to)|talked (?:with|to)|worked with|helped by|assisted by|thank(?:s| you),?|shout ?out to|speak(?:ing)? (?:with|to)|rep(?:resentative)?(?: named)?|agent(?: named)?|associate(?: named)?|specialist(?: named)?)\s+\(?({NAME_TOK}){NAME_2}"),
    re.compile(rf"\b({NAME_TOK}){NAME_2}\s+(?:(?:was|is|were|has been)\s+(?:(?:so|very|extremely|incredibly|really|super|always|just|truly|absolutely)\s+)*{ADJ}|helped|walked|explained|answered|assisted|guided|handled|worked|took (?:care|the time)|made (?:the|it|everything|my|our|this|me))"),
]

def named_rep(raw_text: str) -> bool:
    """True if the review credits a specific person. Uses original casing."""
    for pat in NAME_CTX:
        for m in pat.finditer(raw_text or ""):
            if m.group(1).lower() not in NON_NAMES_L:
                return True
    return False


NARRATIVE_MIN_WORDS = 40      # tune on your data
NARRATIVE_MIN_THEMES = 3


def rule_themes(title, text, rating, n_words=None):
    """Return an ordered list of (theme, rule_name) hits. Caller keeps the top 2
    content themes, then adds NAMED as an extra tag if it fired."""
    raw = f"{title or ''}. {text or ''}"
    t = raw.lower()
    n_words = n_words if n_words is not None else len((text or "").split())
    hits = []
    low = rating is not None and rating <= 3

    web_fail = bool(WEB_FAIL.search(t) or WEB_FAIL2.search(t))
    if web_fail:
        only_app = re.search(r"\bapp\b", t) and not re.search(r"\b(website|web site|site|portal)\b", t)
        hits.append((APP if only_app else WEB, "web_failure"))
        if CLAIM.search(t) and re.search(r"\b(submit\w*|fil(e|ing))\b", t):
            hits.append((FILING, "web_failure+filing"))
    if low and DENY.search(t):
        hits.append((DENIAL, "denial_low"))
    if COVER_LIMIT.search(t) and (low or not CLAIM.search(t)):
        hits.append((COVERAGE, "coverage_limit"))
    if CLAIM.search(t) and (DELAY.search(t) and (low or re.search(r"\b(still|too long|forever|delay\w*)\b", t))):
        hits.append((TURNAROUND, "claim_delay"))
    claim_ctx = bool(re.search(r"\b(claims?|submit\w*|filing|filed|file a|reimburs\w*|payouts?|pay(s)? out|refunds?)\b", t))
    pos_ok = rating is None or rating >= 3          # positive-attribute rules skip 1-2 star reviews
    if claim_ctx and pos_ok and EASE.search(t):
        hits.append((FILING, "claim_ease"))
    if claim_ctx and pos_ok and SPEED.search(t):
        hits.append((TURNAROUND, "claim_speed"))
    if PAY.search(t) and claim_ctx and pos_ok:
        hits.append((REIMB, "claim_payment"))
    if PREM.search(t):
        hits.append((PREMIUM, "premium"))
    if SIGN.search(t) and not claim_ctx:
        hits.append((SIGNUP, "signup"))
    if COVER_PRAISE.search(t) and not claim_ctx and not low:
        hits.append((COVERAGE, "coverage_praise"))
    if n_words <= 8 and not STAGE.search(t):
        hits.append((GSS if SERVICE.search(t) else SHORT, "stageless_short"))
    # long multi-aspect narratives: General/Mixed is primary, strongest specific themes ride along
    distinct = {th for th, rule in hits}
    if n_words >= NARRATIVE_MIN_WORDS and len(distinct) >= NARRATIVE_MIN_THEMES:
        hits = [(GENERAL, "narrative")] + hits
    return hits, named_rep(raw), bool(CANCEL.search(t))


def apply_rules(df, title="title", text="text", rating="rating", max_themes=2):
    """Adds rule-based theme rows for review-level frame `df` (one row per review,
    needs a review_id column). Returns a long frame: review_id, theme, is_primary,
    source, rule. Reviews with no hit are omitted (send them to centroid scoring)."""
    rows, cancel_ids = [], []
    for r in df.itertuples(index=False):
        hits, named, cancel = rule_themes(getattr(r, title), getattr(r, text), getattr(r, rating))
        seen, kept = set(), []
        limit = max_themes + (1 if hits and hits[0][0] == GENERAL else 0)   # narratives: General + 2 specifics
        for th, rule in hits:                       # priority = order of hits
            if th not in seen:
                seen.add(th); kept.append((th, rule))
            if len(kept) == limit:
                break
        for i, (th, rule) in enumerate(kept):
            rows.append((r.review_id, th, i == 0, "rule", rule))
        if named:
            rows.append((r.review_id, NAMED, False, "rule", "named_rep"))
        if cancel:
            cancel_ids.append(r.review_id)
    out = pd.DataFrame(rows, columns=["review_id", "theme", "is_primary", "source", "rule"])
    return out, cancel_ids


# ------------------------------------------------------------ assembly helpers
def long_from_leaf(df, leaf_col="leaf"):
    """Topic-based rows for every non-outlier review (source='topic')."""
    d = df[["review_id", leaf_col]].copy()
    d["theme"] = d[leaf_col].map(LEAF_TO_THEMES)
    d = d[d["theme"].map(lambda x: isinstance(x, list))]
    d = d.explode("theme")
    d["is_primary"] = d.groupby("review_id").cumcount().eq(0)
    d["source"], d["rule"] = "topic", "leaf_mapping"
    return d[["review_id", "theme", "is_primary", "source", "rule"]]


def finalize(long):
    """De-duplicate (review_id, theme), keep one primary per review, and add weights.
    Content themes share weight 1/k per review; the Named-Rep tag carries weight 1."""
    long = long.sort_values(["review_id", "is_primary"], ascending=[True, False])
    long = long.drop_duplicates(["review_id", "theme"]).copy()
    content = long["theme"] != NAMED
    k = long[content].groupby("review_id")["theme"].transform("size")
    long["weight"] = 1.0
    long.loc[content, "weight"] = 1.0 / k
    # a review whose only row is a rule-based Named-Rep tag also gets General/Mixed as its primary
    rule_named = (long["theme"] == NAMED) & (long["source"] == "rule")
    only_named = rule_named.groupby(long["review_id"]).transform("all") & \
                 (long.groupby("review_id")["theme"].transform("size") == 1)
    extra = long[only_named].drop_duplicates("review_id").copy()
    extra["theme"], extra["is_primary"], extra["source"], extra["rule"], extra["weight"] = GENERAL, True, "fallback", "only_named_rep", 1.0
    long = pd.concat([long, extra], ignore_index=True)
    return long


# ------------------------------------------------------------------ usage
# df needs: review_id, provider, rating, title, text, leaf   (leaf per the naming above)
#
# topic_rows   = long_from_leaf(df)                              # Step 2 output (non-outliers)
# outliers     = df[df["leaf"].isin(OUTLIER_LEAVES)]
# rule_rows, cancel_ids = apply_rules(outliers)                  # Step 4
# rule_rows.groupby("rule")["review_id"].nunique()               # Step 3 sizing (per rule)
# unresolved   = outliers[~outliers["review_id"].isin(rule_rows.loc[rule_rows.theme != NAMED, "review_id"])]
# -> score `unresolved` against leaf centroids (Step 5), then fall back to GENERAL with source="fallback"
# long_theme_df = finalize(pd.concat([topic_rows, rule_rows, centroid_rows, fallback_rows]))


# ------------------------------------------------------------- sanity check
# Leaf sizes from the mapping table (corpus of 29,923 reviews). If your refreshed data
# differs slightly, treat mismatches as a prompt to investigate, not necessarily an error.
EXPECTED_LEAF_SIZES = {
    "-1": 3626, "0": 448, "1": 571, "2.-1": 3609, "2.0": 214, "2.1": 273, "2.2": 987,
    "2.3.-1": 948, "2.3.0": 224, "2.3.1": 1481, "2.4": 448, "2.5": 382, "3.-1": 921,
    "3.0": 2077, "3.1": 834, "4": 1659, "5.-1": 3745, "5.0": 510, "5.1": 305,
    "5.2": 508, "5.3": 421, "6": 349, "7": 975, "8": 2701, "9": 1139, "10": 568,
}


def check_leaf_sizes(df, leaf_col="leaf"):
    """Return (mismatches, unexpected_leaves). Empty results mean the leaf column
    reproduces the sizes in your mapping table exactly."""
    got = df[leaf_col].value_counts()
    rows = [(k, v, int(got.get(k, 0))) for k, v in EXPECTED_LEAF_SIZES.items()]
    out = pd.DataFrame(rows, columns=["leaf", "expected", "actual"])
    out["diff"] = out["actual"] - out["expected"]
    return out[out["diff"] != 0], set(got.index) - set(EXPECTED_LEAF_SIZES)
