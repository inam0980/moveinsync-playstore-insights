"""Fetch Play Store reviews + app-level rating snapshots.

Incremental: re-running only adds reviews we haven't seen (keyed by reviewId),
so this can run on a schedule and build history over time.
"""
from datetime import datetime, timezone

import pandas as pd
from google_play_scraper import Sort, app, reviews

from pipeline.config import (APPS, COMPETITORS, COUNTRY, DATA_DIR, LANG,
                             MAX_REVIEWS_PER_APP, REVIEWS_CSV, SNAPSHOTS_CSV)

# reviewer names are deliberately not stored (not needed, and the repo is public)
REVIEW_COLS = ["reviewId", "app_id", "app_name", "content", "score",
               "thumbsUpCount", "reviewCreatedVersion", "at", "replyContent", "repliedAt"]


def fetch_reviews(app_id: str, known_ids: set[str], cap: int = MAX_REVIEWS_PER_APP) -> list[dict]:
    """Page through newest-first reviews; stop once we hit a page of already-known reviews."""
    out, token = [], None
    while len(out) < cap:
        batch, token = reviews(app_id, lang=LANG, country=COUNTRY, sort=Sort.NEWEST,
                               count=200, continuation_token=token)
        if not batch:
            break
        new = [r for r in batch if r["reviewId"] not in known_ids]
        out.extend(new)
        if len(new) < len(batch) or token is None:  # reached reviews we already have
            break
    return out


def snapshot(app_id: str, name: str, kind: str) -> dict:
    d = app(app_id, lang=LANG, country=COUNTRY)
    h = d.get("histogram") or [0] * 5
    return {
        "snapshot_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_id": app_id, "app_name": name, "kind": kind,
        "score": d.get("score"), "ratings": d.get("ratings"), "reviews": d.get("reviews"),
        "installs": d.get("realInstalls"), "version": d.get("version"),
        "updated": d.get("lastUpdatedOn"),
        "star1": h[0], "star2": h[1], "star3": h[2], "star4": h[3], "star5": h[4],
    }


def run() -> pd.DataFrame:
    DATA_DIR.mkdir(exist_ok=True)
    existing = pd.read_csv(REVIEWS_CSV) if REVIEWS_CSV.exists() else pd.DataFrame(columns=REVIEW_COLS)
    known = set(existing["reviewId"].astype(str))

    rows = []
    for app_id, name in APPS.items():
        got = fetch_reviews(app_id, known)
        for r in got:
            rows.append({**{k: r.get(k) for k in REVIEW_COLS}, "app_id": app_id, "app_name": name})
        print(f"[scrape] {name}: +{len(got)} new reviews")

    merged = pd.concat([existing, pd.DataFrame(rows, columns=REVIEW_COLS)], ignore_index=True)
    merged = merged.drop_duplicates("reviewId").sort_values("at", ascending=False)
    merged.to_csv(REVIEWS_CSV, index=False)

    snaps = [snapshot(i, n, "moveinsync") for i, n in APPS.items()]
    for i, n in COMPETITORS.items():
        try:
            snaps.append(snapshot(i, n, "competitor"))
        except Exception as e:  # competitor app ids can disappear; never fail the run for them
            print(f"[scrape] competitor {i} skipped: {e}")
    snap_df = pd.DataFrame(snaps)
    if SNAPSHOTS_CSV.exists():
        snap_df = pd.concat([pd.read_csv(SNAPSHOTS_CSV), snap_df], ignore_index=True)
    snap_df.to_csv(SNAPSHOTS_CSV, index=False)

    print(f"[scrape] total reviews stored: {len(merged)}")
    return merged


if __name__ == "__main__":
    run()
