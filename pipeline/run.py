"""One command to refresh everything:  python -m pipeline.run

1. scrape new reviews + rating snapshot
2. tag new reviews (Claude if ANTHROPIC_API_KEY is set, else keyword rules)
3. print a short health report (and exit non-zero on a release regression, so CI can alert)
"""
import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from pipeline import analyze, classify, scrape  # noqa: E402
from pipeline.config import PRIMARY_APP  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-scrape", action="store_true")
    ap.add_argument("--since", default=None, help="only send reviews on/after this date to Claude")
    ap.add_argument("--fail-on-regression", action="store_true")
    a = ap.parse_args()

    if not a.skip_scrape:
        scrape.run()
    classify.run(since=a.since)

    df = analyze.load()
    df = df[df["app_id"] == PRIMARY_APP]
    k = analyze.kpis(df)["current"]
    imp = analyze.issue_impact(df)
    ver = analyze.versions(df)
    latest = ver.iloc[-1]

    print("\n=== Play Store health (employee app, last 90 days) ===")
    print(f"written-review avg {k['avg']:.2f} | 1-star {k['one_star']:.0%} | reply rate on 1-2★ {k['reply_rate']:.0%}")
    print("top issues by stars at stake:")
    for r in imp.head(5).itertuples():
        print(f"  {r.issue:<45} {r.stars_at_stake:.3f}  ({r.owner}, trend {r.trend_pp:+.1f}pp)")
    flag = "REGRESSION" if latest["regression"] else "ok"
    print(f"latest version {latest['reviewCreatedVersion']}: 1-star {latest['one_star']:.0%} "
          f"({latest['delta_pp']:+.1f}pp vs baseline) -> {flag}")

    if a.fail_on_regression and latest["regression"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
