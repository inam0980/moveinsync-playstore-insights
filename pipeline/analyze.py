"""Turn tagged reviews into the numbers the dashboard and report use.

Key idea - "stars at stake": for a set of reviews, sum(5 - stars) / total reviews.
It is how many points of the average written-review rating that issue costs.
If every review whose main complaint was X had been a 5, the average would rise by exactly that much.
"""
import re

import pandas as pd

from pipeline.config import CLASSIFIED_CSV, SNAPSHOTS_CSV
from pipeline.taxonomy import APP_OWNED, CATEGORIES, ISSUE_CATEGORIES, label, owner

DEVICE_PAT = re.compile(
    r"\b(pixel ?\d+\w*|oneplus ?\w+|vivo ?\w+|oppo ?\w+|realme ?\w+|redmi ?\w+|xiaomi|samsung|galaxy ?\w+|"
    r"iqoo ?\w*|motorola|moto ?g\d*|nothing phone|poco ?\w+|android ?\d+)\b", re.I)


def load(path=CLASSIFIED_CSV) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["at"] = pd.to_datetime(df["at"])
    df["repliedAt"] = pd.to_datetime(df["repliedAt"], errors="coerce")
    df["content"] = df["content"].fillna("")
    df["cats"] = df["categories"].fillna("other").str.split("|")
    df["month"] = df["at"].dt.to_period("M").dt.to_timestamp()
    df["replied"] = df["replyContent"].notna()
    df["negative"] = df["score"] <= 2
    return df


def load_snapshots() -> pd.DataFrame:
    if not SNAPSHOTS_CSV.exists():
        return pd.DataFrame()
    s = pd.read_csv(SNAPSHOTS_CSV)
    s["snapshot_at"] = pd.to_datetime(s["snapshot_at"])
    return s


def window(df: pd.DataFrame, days: int, end=None) -> pd.DataFrame:
    end = end or df["at"].max()
    return df[(df["at"] > end - pd.Timedelta(days=days)) & (df["at"] <= end)]


def kpis(df: pd.DataFrame, days: int = 90) -> dict:
    cur = window(df, days)
    prev = window(df, days, end=df["at"].max() - pd.Timedelta(days=days))
    def stats(x):
        return {"n": len(x), "avg": x["score"].mean(), "one_star": (x["score"] == 1).mean(),
                "five_star": (x["score"] == 5).mean(), "reply_rate": x.loc[x["negative"], "replied"].mean()}
    return {"current": stats(cur), "previous": stats(prev)}


def monthly(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("month").agg(reviews=("score", "size"), avg=("score", "mean"),
                                one_star=("score", lambda s: (s == 1).mean()),
                                reply_rate=("replied", "mean"))
    return g.reset_index()


def versions(df: pd.DataFrame, min_n: int = 30, lookback: int = 5) -> pd.DataFrame:
    """Per app version: 1-star share vs the trailing average of the previous `lookback` versions."""
    v = (df.dropna(subset=["reviewCreatedVersion"])
           .groupby("reviewCreatedVersion")
           .agg(n=("score", "size"), avg=("score", "mean"), one_star=("score", lambda s: (s == 1).mean()),
                first_seen=("at", "min"))
           .query("n >= @min_n").sort_values("first_seen").reset_index())
    v["baseline_one_star"] = v["one_star"].shift(1).rolling(lookback, min_periods=2).mean()
    v["delta_pp"] = (v["one_star"] - v["baseline_one_star"]) * 100
    v["regression"] = v["delta_pp"] >= 7  # 7+ points more 1-star reviews than recent releases
    return v


def issue_impact(df: pd.DataFrame, days: int = 365, trend_days: int = 90) -> pd.DataFrame:
    """Rank issues by how many rating points they cost, plus whether they're getting worse."""
    w = window(df, days)
    n = len(w)
    rows = []
    for cat in ISSUE_CATEGORIES:
        has = w["cats"].apply(lambda c: cat in c)
        prim = w["primary_category"] == cat
        neg_has = has & w["negative"]
        recent, before = window(df, trend_days), window(df, trend_days, end=df["at"].max() - pd.Timedelta(days=trend_days))
        r_share = (recent["negative"] & recent["cats"].apply(lambda c: cat in c)).sum() / max(recent["negative"].sum(), 1)
        b_share = (before["negative"] & before["cats"].apply(lambda c: cat in c)).sum() / max(before["negative"].sum(), 1)
        rows.append({
            "category": cat, "issue": label(cat), "owner": owner(cat), "app_owned": cat in APP_OWNED,
            "neg_mentions": int(neg_has.sum()),
            "share_of_negative": neg_has.sum() / max(w["negative"].sum(), 1),
            "stars_at_stake": (5 - w.loc[prim, "score"]).sum() / max(n, 1),
            "avg_when_mentioned": w.loc[has, "score"].mean(),
            "trend_pp": (r_share - b_share) * 100,
        })
    out = pd.DataFrame(rows)
    # priority: rating points at stake, weighted by how directly the app team controls the fix,
    # nudged up if the issue is growing
    out["priority"] = out["stars_at_stake"] * out["app_owned"].map({True: 1.0, False: 0.5}) \
        * (1 + out["trend_pp"].clip(-10, 10) / 50)
    return out.sort_values("priority", ascending=False).reset_index(drop=True)


def owner_split(impact: pd.DataFrame) -> pd.DataFrame:
    return impact.groupby("owner", as_index=False)["stars_at_stake"].sum().sort_values("stars_at_stake", ascending=False)


def examples(df: pd.DataFrame, cat: str, k: int = 5, days: int = 365) -> pd.DataFrame:
    w = window(df, days)
    m = w[w["negative"] & w["cats"].apply(lambda c: cat in c) & (w["content"].str.len() > 40)]
    return m.sort_values(["thumbsUpCount", "at"], ascending=False).head(k)


def device_mentions(df: pd.DataFrame, days: int = 90) -> pd.DataFrame:
    w = window(df, days)
    w = w[w["negative"]]
    hits = w["content"].str.findall(DEVICE_PAT).explode().dropna().str.lower().str.replace(r"\s+", " ", regex=True)
    return hits.value_counts().rename_axis("device").reset_index(name="mentions")


def unreplied_negative(df: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    w = window(df, days)
    return w[w["negative"] & ~w["replied"]].sort_values(["thumbsUpCount", "at"], ascending=False)
