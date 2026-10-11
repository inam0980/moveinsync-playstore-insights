"""Offline backup tagger: a small ML model distilled from Gemini's labels.

When Gemini is unavailable (no key, quota used up, network down), reviews that Gemini hasn't seen
are tagged by this model instead of the regex rules. It's trained on the fly from the reviews Gemini
already labelled (stored in classified.csv), runs in a few seconds on a laptop and costs nothing.

  python -m pipeline.local_model     # prints accuracy vs. the keyword rules on held-out Gemini labels
"""
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, make_pipeline
from sklearn.preprocessing import MultiLabelBinarizer

MIN_TRAINING_REVIEWS = 300
EXTRA_LABEL_THRESHOLD = 0.35  # secondary categories need this probability to be added


def _text(df: pd.DataFrame) -> pd.Series:
    """Review text plus two hint tokens: the star rating, and which keyword rules fired.
    The rule hints let the model learn when the rules are right (5-fold CV: +2pp overall, +9pp on 1-2★)."""
    from pipeline.classify import keyword_tag
    stars = "stars" + df["score"].astype(int).astype(str)
    hints = [" ".join("kw_" + c for c in keyword_tag(t, int(s))["categories"].split("|"))
             for t, s in zip(df["content"], df["score"])]
    return stars + " " + df["content"].fillna("").astype(str) + " " + pd.Series(hints, index=df.index)


def _features() -> FeatureUnion:
    # word n-grams for meaning + character n-grams for Hinglish spellings and typos ("otp nhi aaya", "worstt")
    return FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, sublinear_tf=True)),
    ])


class LocalTagger:
    def __init__(self, labelled: pd.DataFrame):
        self.primary = make_pipeline(_features(), LogisticRegression(max_iter=3000, C=10))
        self.primary.fit(_text(labelled), labelled["primary_category"])
        self.mlb = MultiLabelBinarizer()
        y = self.mlb.fit_transform(labelled["categories"].str.split("|"))
        self.multi = make_pipeline(_features(), OneVsRestClassifier(LogisticRegression(max_iter=3000, C=10)))
        self.multi.fit(_text(labelled), y)

    def tag(self, df: pd.DataFrame) -> dict[str, dict]:
        x = _text(df)
        primary = self.primary.predict(x)
        probs = self.multi.predict_proba(x)
        out = {}
        for rid, score, p, pr in zip(df["reviewId"].astype(str), df["score"].astype(int), primary, probs):
            extra = [c for c, v in zip(self.mlb.classes_, pr) if v >= EXTRA_LABEL_THRESHOLD and c != p]
            out[rid] = {"categories": "|".join([p, *extra]), "primary_category": p,
                        "sentiment": "negative" if score <= 2 else "neutral" if score == 3 else "positive",
                        "severity": "high" if score == 1 else "medium" if score <= 3 else "low",
                        "summary": "", "classifier": "local-ml"}
        return out


def train(classified: pd.DataFrame) -> "LocalTagger | None":
    labelled = classified[classified["classifier"] == "gemini"].dropna(subset=["content", "primary_category"])
    if len(labelled) < MIN_TRAINING_REVIEWS or labelled["primary_category"].nunique() < 3:
        return None
    return LocalTagger(labelled)


def evaluate() -> None:
    """Hold out 20% of Gemini-labelled reviews; compare the local model and the keyword rules against Gemini."""
    from pipeline.classify import keyword_tag
    from pipeline.config import CLASSIFIED_CSV

    df = pd.read_csv(CLASSIFIED_CSV)
    labelled = df[df["classifier"] == "gemini"].dropna(subset=["content", "primary_category"])
    counts = labelled["primary_category"].value_counts()
    labelled = labelled[labelled["primary_category"].isin(counts[counts >= 5].index)]
    tr, te = train_test_split(labelled, test_size=0.2, random_state=42, stratify=labelled["primary_category"])

    model = LocalTagger(tr)
    ml = model.tag(te)
    kw = {str(r.reviewId): keyword_tag(r.content, int(r.score)) for r in te.itertuples()}
    truth = te.set_index(te["reviewId"].astype(str))["primary_category"]
    neg = te.set_index(te["reviewId"].astype(str))["score"] <= 2

    def acc(pred, mask=None):
        hit = pd.Series({rid: pred[rid]["primary_category"] == truth[rid] for rid in truth.index})
        return hit[mask].mean() if mask is not None else hit.mean()

    print(f"Gemini-labelled reviews: {len(labelled)} (train {len(tr)}, test {len(te)})")
    print("Agreement with Gemini on the main issue (held-out test set):")
    print(f"  local ML model : {acc(ml):.0%} overall | {acc(ml, neg):.0%} on 1-2★ reviews")
    print(f"  keyword rules  : {acc(kw):.0%} overall | {acc(kw, neg):.0%} on 1-2★ reviews")
    print(f"  (always guessing the most common label would score {truth.value_counts(normalize=True).iloc[0]:.0%})")


if __name__ == "__main__":
    evaluate()
