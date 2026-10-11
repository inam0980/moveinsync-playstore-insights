"""Tag each review with issue categories.

Two engines:
  * claude  - Claude API with structured JSON output (used when ANTHROPIC_API_KEY is set)
  * keyword - regex fallback so the pipeline and dashboard work with no key / no cost

Incremental: only reviews not already tagged by the requested engine are sent.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from pipeline.config import CLASSIFIED_CSV, REVIEWS_CSV
from pipeline.taxonomy import CATEGORIES

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
BATCH_SIZE = 40
WORKERS = 4
CAT_KEYS = list(CATEGORIES)

TAG_COLS = ["categories", "primary_category", "sentiment", "severity", "summary", "classifier"]


# ---------------------------------------------------------------- keyword engine
_PATTERNS = {k: [re.compile(p, re.I) for p in v["keywords"]] for k, v in CATEGORIES.items()}


def keyword_tag(text: str, score: int) -> dict:
    text = text if isinstance(text, str) else ""
    hits = [k for k, pats in _PATTERNS.items() if k != "praise" and any(p.search(text) for p in pats)]
    if not hits:
        hits = ["praise"] if score >= 4 and any(p.search(text) for p in _PATTERNS["praise"]) else ["other"]
    # primary = issue mentioned first in the text (crude but stable)
    def first_pos(k):
        return min((m.start() for p in _PATTERNS[k] for m in [p.search(text)] if m), default=10**6)
    primary = min(hits, key=first_pos)
    sentiment = "negative" if score <= 2 else "neutral" if score == 3 else "positive"
    return {"categories": "|".join(hits), "primary_category": primary, "sentiment": sentiment,
            "severity": "high" if score == 1 else "medium" if score <= 3 else "low",
            "summary": "", "classifier": "keyword"}


# ---------------------------------------------------------------- claude engine
SYSTEM_PROMPT = f"""You label Google Play reviews of MoveInSync, an employee commute app used by
corporate employees in India to book office cabs/shuttles, track the vehicle, board with OTP, and raise issues.
Reviews may be in English, Hindi, Hinglish or other Indian languages.

For each review return:
- categories: every issue the reviewer actually describes (one or more of the keys below).
  Use "praise" only when there is no complaint. Use "other" only if nothing fits.
- primary_category: the single issue that most drove the star rating.
- sentiment: negative | neutral | positive
- severity: high (blocks getting to work / safety risk / cannot use app), medium (recurring friction), low (minor or none)
- summary: <= 12 English words describing the concrete problem (or praise). Be specific, e.g.
  "OTP never arrives so cannot log in", not "login issue".

Category keys:
{chr(10).join(f"- {k}: {v['label']}" for k, v in CATEGORIES.items())}

Distinguish carefully: a cab arriving late is cab_delay_noshow (operations), but the app showing the
wrong cab position is tracking_eta (app). Booking window/cut-off rules are booking_scheduling."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "categories": {"type": "array", "items": {"type": "string", "enum": CAT_KEYS}},
                    "primary_category": {"type": "string", "enum": CAT_KEYS},
                    "sentiment": {"type": "string", "enum": ["negative", "neutral", "positive"]},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "summary": {"type": "string"},
                },
                "required": ["id", "categories", "primary_category", "sentiment", "severity", "summary"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _claude_batch(client, batch: pd.DataFrame) -> dict[str, dict]:
    payload = [{"id": str(r.reviewId), "stars": int(r.score), "text": str(r.content)[:1500]}
               for r in batch.itertuples()]
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": "Label these reviews:\n" + json.dumps(payload, ensure_ascii=False)}],
    )
    if resp.stop_reason == "refusal":
        return {}
    text = next(b.text for b in resp.content if b.type == "text")
    out = {}
    for r in json.loads(text)["results"]:
        cats = [c for c in r["categories"] if c in CATEGORIES] or [r["primary_category"]]
        out[r["id"]] = {"categories": "|".join(dict.fromkeys(cats)), "primary_category": r["primary_category"],
                        "sentiment": r["sentiment"], "severity": r["severity"], "summary": r["summary"],
                        "classifier": "claude"}
    return out


def claude_tag(df: pd.DataFrame) -> dict[str, dict]:
    import anthropic
    client = anthropic.Anthropic()
    batches = [df.iloc[i:i + BATCH_SIZE] for i in range(0, len(df), BATCH_SIZE)]
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(WORKERS) as pool:
        futures = {pool.submit(_claude_batch, client, b): i for i, b in enumerate(batches)}
        for n, f in enumerate(as_completed(futures), 1):
            try:
                results.update(f.result())
            except anthropic.APIError as e:
                print(f"[classify] batch {futures[f]} failed: {e}")  # these fall back to keyword tags
            if n % 10 == 0 or n == len(batches):
                print(f"[classify] claude: {n}/{len(batches)} batches")
    return results


# ---------------------------------------------------------------- driver
def run(engine: str | None = None, since: str | None = None, limit: int | None = None) -> pd.DataFrame:
    """engine: 'claude' | 'keyword' | None (auto: claude if a key is configured)."""
    engine = engine or ("claude" if os.getenv("ANTHROPIC_API_KEY") else "keyword")
    reviews = pd.read_csv(REVIEWS_CSV)
    reviews["at"] = pd.to_datetime(reviews["at"])

    prev = pd.read_csv(CLASSIFIED_CSV) if CLASSIFIED_CSV.exists() else pd.DataFrame(columns=["reviewId", *TAG_COLS])
    prev = prev[["reviewId", *TAG_COLS]].drop_duplicates("reviewId")
    # only send Claude what it hasn't tagged before (keeps reruns cheap)
    done = set(prev.loc[prev["classifier"] == "claude", "reviewId"].astype(str)) if engine == "claude" else set()
    has_text = reviews["content"].fillna("").str.strip().str.len() > 0
    todo = reviews[has_text & ~reviews["reviewId"].astype(str).isin(done)]
    if since:
        todo = todo[todo["at"] >= pd.Timestamp(since)]
    if limit:
        todo = todo.head(limit)

    print(f"[classify] engine={engine} reviews to tag: {len(todo)}")
    if engine == "claude" and len(todo):
        tags = claude_tag(todo)
    else:
        tags = {}
    # keyword tags for everything not tagged by claude (also covers failed claude batches)
    for r in reviews[has_text].itertuples():
        rid = str(r.reviewId)
        if rid not in tags:
            tags[rid] = keyword_tag(r.content, int(r.score))

    new = pd.DataFrame.from_dict(tags, orient="index").rename_axis("reviewId").reset_index()
    # never overwrite an existing claude tag with a keyword tag
    keep_claude = prev[prev["classifier"] == "claude"]
    new = new[~(new["reviewId"].isin(keep_claude["reviewId"].astype(str)) & (new["classifier"] == "keyword"))]
    tags_df = pd.concat([keep_claude.astype({"reviewId": str}), new], ignore_index=True).drop_duplicates("reviewId", keep="last")

    out = reviews.astype({"reviewId": str}).merge(tags_df, on="reviewId", how="left")
    out.to_csv(CLASSIFIED_CSV, index=False)
    print(f"[classify] wrote {len(out)} rows -> {CLASSIFIED_CSV.name} "
          f"(claude-tagged: {(out['classifier'] == 'claude').sum()})")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["claude", "keyword"])
    ap.add_argument("--since", help="only send reviews on/after this date to Claude, e.g. 2025-10-01")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    run(a.engine, a.since, a.limit)
