"""MoveInSync Play Store Insights - Streamlit dashboard.

Run locally:  streamlit run app.py
"""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
try:  # Streamlit Cloud: keys live in st.secrets
    for _k in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "LLM_PROVIDER"):
        if _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

from pipeline import analyze as A  # noqa: E402
from pipeline.classify import AI_ENGINES, default_engine  # noqa: E402
from pipeline.config import APPS, CLASSIFIED_CSV, PRIMARY_APP  # noqa: E402
from pipeline.recommendations import PLAYBOOK, QUICK_WINS  # noqa: E402
from pipeline.replies import draft  # noqa: E402
from pipeline.taxonomy import ISSUE_CATEGORIES, label  # noqa: E402

st.set_page_config(page_title="MoveInSync Play Store Insights", page_icon="📉", layout="wide")

# Fixed color per owning team (categorical slots 1-4, assigned in order, never by rank)
OWNER_COLORS = {"App Engineering": "#2a78d6", "Product": "#eb6834", "Operations": "#1baf7a", "Support": "#eda100"}
CRITICAL = "#d03b3b"
MUTED = "#898781"
SERIES = "#2a78d6"


@st.cache_data(ttl=3600)
def load_data():
    return A.load(), A.load_snapshots()


if not CLASSIFIED_CSV.exists():
    st.error("No data yet. Run `python -m pipeline.run` first.")
    st.stop()

df_all, snaps = load_data()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Filters")
    app_id = st.selectbox("App", list(APPS), index=list(APPS).index(PRIMARY_APP), format_func=APPS.get)
    days = st.select_slider("Analysis window", options=[90, 180, 365, 730], value=365,
                            format_func=lambda d: f"Last {d} days")
    st.divider()
    st.caption(f"Reviews stored: **{len(df_all):,}**")
    st.caption(f"Latest review: **{df_all['at'].max():%d %b %Y}**")
    ai = df_all[df_all["classifier"].isin(AI_ENGINES)]
    engines = ", ".join(sorted(ai["classifier"].unique())) or "none yet"
    st.caption(f"Tagged by AI ({engines}): **{len(ai):,}** reviews; rest by keyword rules")
    st.caption("Data refreshes weekly via GitHub Actions.")

df = df_all[df_all["app_id"] == app_id]
if df.empty:
    st.warning("No reviews for this app yet.")
    st.stop()

k = A.kpis(df, 90)
imp = A.issue_impact(df, days)
ver = A.versions(df)
snap = snaps[snaps["app_id"] == app_id].sort_values("snapshot_at").tail(1) if not snaps.empty else pd.DataFrame()
mon = A.monthly(df)

# ------------------------------------------------------------------ header + KPIs
st.title("Why are MoveInSync's Play Store ratings low, and what to fix first")
st.caption(f"{APPS[app_id]} · Google Play India · {len(df):,} reviews analysed")

c = k["current"]; p = k["previous"]
cols = st.columns(5)
if not snap.empty:
    s = snap.iloc[0]
    cols[0].metric("Play Store rating (all-time)", f"{s['score']:.2f} ★", help=f"{int(s['ratings']):,} ratings, version {s['version']}")
else:
    cols[0].metric("Play Store rating", "n/a")
cols[1].metric("Written reviews, last 90 days", f"{c['avg']:.2f} ★", f"{c['avg'] - p['avg']:+.2f} vs prior 90d")
cols[2].metric("1-star share, last 90 days", f"{c['one_star']:.0%}", f"{(c['one_star'] - p['one_star']) * 100:+.1f} pp",
               delta_color="inverse")
cols[3].metric("Reply rate on 1-2★ reviews", f"{c['reply_rate']:.0%}", f"{(c['reply_rate'] - p['reply_rate']) * 100:+.1f} pp")
latest = ver.iloc[-1] if not ver.empty else None
if latest is not None:
    cols[4].metric(f"Latest version {latest['reviewCreatedVersion']}", f"{latest['one_star']:.0%} 1-star",
                   f"{latest['delta_pp']:+.1f} pp vs recent releases", delta_color="inverse")

# headline verdict, computed
app_share = imp.loc[imp["app_owned"], "stars_at_stake"].sum()
ops_share = imp.loc[~imp["app_owned"], "stars_at_stake"].sum()
w = A.window(df, days)
gap = 5 - w["score"].mean()
top3 = imp.head(3)["issue"].tolist()
st.info(
    f"**Verdict:** written reviews average **{w['score'].mean():.2f}★** over the last {days} days, "
    f"**{gap:.2f} stars** short of 5. Issues the app/product team controls cost **{app_share:.2f}** of those stars; "
    f"on-ground operations (cabs, drivers, routes, helpdesk) cost **{ops_share:.2f}**. "
    f"The rest are 1-star reviews with no stated reason. **Fix first:** {', '.join(top3)}.",
    icon="🎯",
)

tab_why, tab_plan, tab_trend, tab_explore, tab_reply, tab_method = st.tabs(
    ["Why ratings are low", "Action plan", "Trends & releases", "Review explorer", "Reply queue", "Method"])

# ------------------------------------------------------------------ WHY
with tab_why:
    st.subheader("Which issues cost the most rating points")
    st.caption("Stars at stake = how much the average written-review rating would rise if every review whose "
               "main complaint is this issue had been 5★. Color = team that can fix it.")
    plot = imp.sort_values("stars_at_stake")
    fig = px.bar(plot, x="stars_at_stake", y="issue", color="owner", orientation="h",
                 color_discrete_map=OWNER_COLORS, category_orders={"owner": list(OWNER_COLORS)},
                 custom_data=["neg_mentions", "share_of_negative", "trend_pp", "owner"],
                 labels={"stars_at_stake": "Stars at stake", "issue": "", "owner": "Team"})
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Stars at stake: %{x:.3f}<br>%{customdata[0]} negative reviews "
                                    "(%{customdata[1]:.0%} of all 1-2★)<br>Trend (90d): %{customdata[2]:+.1f} pp"
                                    "<br>Owner: %{customdata[3]}<extra></extra>",
                      marker_line_width=0)
    fig.update_layout(height=480, bargap=0.35, legend=dict(orientation="h", y=1.08, x=0, title=None),
                      margin=dict(l=0, r=10, t=30, b=0), xaxis=dict(gridcolor="rgba(137,135,129,0.25)"))
    st.plotly_chart(fig, width="stretch")

    a, b = st.columns(2)
    with a:
        st.markdown("**Rating points lost, by team that owns the fix**")
        split = A.owner_split(imp)
        f2 = px.bar(split, x="owner", y="stars_at_stake", color="owner", color_discrete_map=OWNER_COLORS,
                    text=split["stars_at_stake"].map("{:.2f}".format), labels={"owner": "", "stars_at_stake": "Stars at stake"})
        f2.update_traces(textposition="outside", marker_line_width=0, hovertemplate="%{x}: %{y:.3f} stars<extra></extra>")
        f2.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=10, b=0), bargap=0.45)
        st.plotly_chart(f2, width="stretch")
    with b:
        st.markdown("**Growing vs shrinking complaints** (share of 1-2★ reviews, last 90d vs the 90d before)")
        t = imp[["issue", "trend_pp"]].sort_values("trend_pp", ascending=False)
        t["direction"] = t["trend_pp"].map(lambda x: "▲ growing" if x > 1 else "▼ shrinking" if x < -1 else "– flat")
        st.dataframe(t.rename(columns={"issue": "Issue", "trend_pp": "Change (pp)", "direction": "Direction"}),
                     hide_index=True, width="stretch",
                     column_config={"Change (pp)": st.column_config.NumberColumn(format="%+.1f")})

    with st.expander("Full table"):
        st.dataframe(imp.drop(columns=["category", "app_owned"]), hide_index=True, width="stretch",
                     column_config={"share_of_negative": st.column_config.NumberColumn(format="%.1%"),
                                    "stars_at_stake": st.column_config.NumberColumn(format="%.3f"),
                                    "avg_when_mentioned": st.column_config.NumberColumn(format="%.2f"),
                                    "trend_pp": st.column_config.NumberColumn(format="%+.1f"),
                                    "priority": st.column_config.NumberColumn(format="%.3f")})

# ------------------------------------------------------------------ PLAN
with tab_plan:
    neg_all = df[df["negative"]].copy()
    neg_all["half"] = neg_all["at"].dt.to_period("Q")
    by_q = neg_all.groupby("half")["replied"].mean()
    recent_vers = ver.tail(12)
    regs = recent_vers[recent_vers["regression"]]
    ctx = {"reply_peak": by_q.max() if len(by_q) else 0, "reply_now": c["reply_rate"] or 0,
           "n_reg": len(regs), "n_rel": len(recent_vers),
           "reg_list": ", ".join(regs["reviewCreatedVersion"].astype(str)) or "none"}

    st.subheader("Do this week: three moves on the rating mechanism itself")
    for i, q in enumerate(QUICK_WINS, 1):
        with st.container(border=True):
            st.markdown(f"#### {i}. {q['title'].format(**ctx)}")
            st.markdown(f"**Why:** {q['why'].format(**ctx)}")
            st.markdown("\n".join(f"- {x}" for x in q["what"]))
            st.caption(f"Owner: {q['owner']} · Effort: {q['effort']} · Success metric: {q['metric']}")

    st.subheader("Then: fix issues in priority order")
    st.caption("Ranked by stars at stake × how directly the app team controls it (ops issues count half) × trend. "
               "Re-ranks automatically on every data refresh.")
    for rank, r in enumerate(imp.itertuples(), 1):
        pb = PLAYBOOK.get(r.category)
        if not pb:
            continue
        with st.expander(f"#{rank} · {r.issue} — {r.stars_at_stake:.3f}★ at stake · {r.owner} · "
                         f"{'▲' if r.trend_pp > 1 else '▼' if r.trend_pp < -1 else '–'} {r.trend_pp:+.1f} pp",
                         expanded=rank <= 3):
            st.markdown("**What to do**")
            st.markdown("\n".join(f"- {x}" for x in pb["fix"]))
            st.caption(f"Effort: {pb['effort']} · Success metric: {pb['metric']}")
            ex = A.examples(df, r.category, 4, days)
            if len(ex):
                st.markdown("**What users are saying**")
                for e in ex.itertuples():
                    v = f"v{e.reviewCreatedVersion}" if pd.notna(e.reviewCreatedVersion) else ""
                    st.markdown(f"> {e.content[:300]}  \n> — {int(e.score)}★ · {e.at:%d %b %Y} · {v} · 👍 {int(e.thumbsUpCount)}")

# ------------------------------------------------------------------ TRENDS
with tab_trend:
    m = mon[mon["month"] >= mon["month"].max() - pd.DateOffset(months=36)]
    a, b = st.columns(2)
    with a:
        st.markdown("**Average stars of written reviews, by month**")
        f = px.line(m, x="month", y="avg", markers=True, labels={"month": "", "avg": "Avg stars"})
        f.update_traces(line=dict(width=2, color=SERIES), marker=dict(size=8),
                        hovertemplate="%{x|%b %Y}: %{y:.2f}★<extra></extra>")
        f.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified")
        st.plotly_chart(f, width="stretch")
    with b:
        st.markdown("**Share of 1-star reviews, by month**")
        f = px.line(m, x="month", y="one_star", markers=True, labels={"month": "", "one_star": "1-star share"})
        f.update_traces(line=dict(width=2, color=SERIES), marker=dict(size=8),
                        hovertemplate="%{x|%b %Y}: %{y:.0%}<extra></extra>")
        f.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis_tickformat=".0%", hovermode="x unified")
        st.plotly_chart(f, width="stretch")

    st.markdown("**Developer reply rate on 1-2★ reviews, by quarter**")
    rq = df[df["negative"]].assign(q=lambda x: x["at"].dt.to_period("Q").dt.to_timestamp()).groupby("q")["replied"].mean().reset_index()
    rq = rq[rq["q"] >= pd.Timestamp("2021-01-01")]
    f = px.bar(rq, x="q", y="replied", labels={"q": "", "replied": "Reply rate"})
    f.update_traces(marker_color=SERIES, marker_line_width=0, hovertemplate="%{x|Q%q %Y}: %{y:.0%}<extra></extra>")
    f.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0), yaxis_tickformat=".0%", bargap=0.3)
    st.plotly_chart(f, width="stretch")

    st.markdown("**1-star share by app release** (last 20 releases with ≥30 reviews; red = regression, 7+ pp above the previous 5 releases)")
    vv = ver.tail(20).copy()
    vv["status"] = vv["regression"].map({True: "⚠ Regression", False: "Normal"})
    f = go.Figure()
    f.add_bar(x=vv["reviewCreatedVersion"].astype(str), y=vv["one_star"],
              marker_color=[CRITICAL if r else SERIES for r in vv["regression"]], marker_line_width=0,
              customdata=vv[["n", "avg", "delta_pp", "status"]],
              hovertemplate="v%{x}<br>1-star: %{y:.0%}<br>Avg: %{customdata[1]:.2f}★ (%{customdata[0]} reviews)"
                            "<br>vs baseline: %{customdata[2]:+.1f} pp<br>%{customdata[3]}<extra></extra>")
    f.add_scatter(x=vv["reviewCreatedVersion"].astype(str), y=vv["baseline_one_star"], mode="lines",
                  line=dict(color=MUTED, width=2, dash="dot"), name="Baseline (prev. 5 releases)",
                  hovertemplate="Baseline: %{y:.0%}<extra></extra>")
    f.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), yaxis_tickformat=".0%", bargap=0.3,
                    legend=dict(orientation="h", y=1.1, x=0), xaxis_type="category")
    st.plotly_chart(f, width="stretch")
    st.dataframe(vv[["reviewCreatedVersion", "first_seen", "n", "avg", "one_star", "delta_pp", "status"]].iloc[::-1],
                 hide_index=True, width="stretch",
                 column_config={"one_star": st.column_config.NumberColumn(format="%.0%"),
                                "avg": st.column_config.NumberColumn(format="%.2f"),
                                "delta_pp": st.column_config.NumberColumn(format="%+.1f"),
                                "first_seen": st.column_config.DatetimeColumn(format="DD MMM YYYY")})

    if not snaps.empty:
        st.markdown("**Benchmark: headline Play Store rating vs competitors** (latest snapshot)")
        bm = snaps.sort_values("snapshot_at").groupby("app_id").tail(1)
        bm = bm[["app_name", "kind", "score", "ratings", "installs", "version"]].sort_values("score", ascending=False)
        st.dataframe(bm, hide_index=True, width="stretch",
                     column_config={"score": st.column_config.NumberColumn("Rating", format="%.2f ★"),
                                    "ratings": st.column_config.NumberColumn("Ratings", format="%d"),
                                    "installs": st.column_config.NumberColumn("Installs", format="%d"),
                                    "app_name": "App", "kind": "Type"})

    dev = A.device_mentions(df, 90)
    if len(dev):
        st.markdown("**Devices / Android versions named in 1-2★ reviews (last 90 days)**")
        st.dataframe(dev, hide_index=True)

    if not snaps.empty and snaps["snapshot_at"].nunique() > 1:
        st.markdown("**Play Store headline rating over time** (one point per pipeline run)")
        ss = snaps[snaps["kind"] == "moveinsync"]
        f = px.line(ss, x="snapshot_at", y="score", color="app_name", markers=True)
        f.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(f, width="stretch")

# ------------------------------------------------------------------ EXPLORER
with tab_explore:
    a, b, cc = st.columns(3)
    cat = a.selectbox("Issue", ["All"] + ISSUE_CATEGORIES + ["praise", "other"], format_func=lambda x: x if x == "All" else label(x))
    stars = b.multiselect("Stars", [1, 2, 3, 4, 5], default=[1, 2])
    q = cc.text_input("Search text")
    x = A.window(df, days)
    if cat != "All":
        x = x[x["cats"].apply(lambda cs: cat in cs)]
    if stars:
        x = x[x["score"].isin(stars)]
    if q:
        x = x[x["content"].str.contains(q, case=False, regex=False)]
    st.caption(f"{len(x):,} reviews")
    st.dataframe(x[["at", "score", "content", "primary_category", "summary", "reviewCreatedVersion", "thumbsUpCount"]]
                 .sort_values("at", ascending=False), hide_index=True, width="stretch", height=520,
                 column_config={"at": st.column_config.DatetimeColumn("Date", format="DD MMM YYYY"),
                                "score": "★", "content": st.column_config.TextColumn("Review", width="large"),
                                "primary_category": "Main issue", "summary": "AI summary",
                                "reviewCreatedVersion": "Version", "thumbsUpCount": "👍"})
    st.download_button("Download as CSV", x.drop(columns=["cats"]).to_csv(index=False), "reviews_filtered.csv")

# ------------------------------------------------------------------ REPLY QUEUE
with tab_reply:
    st.subheader("Unanswered 1-2★ reviews (last 30 days)")
    st.caption("Draft a reply, edit it, then post it in Google Play Console → Ratings and reviews. "
               + (f"Drafts use {default_engine().title()}." if default_engine() in AI_ENGINES
                  else "No API key set: drafts use category templates."))
    uq = A.unreplied_negative(df, 30)
    st.caption(f"{len(uq)} reviews waiting")
    for r in uq.head(15).itertuples():
        with st.container(border=True):
            st.markdown(f"**{int(r.score)}★ · {r.at:%d %b} · {label(r.primary_category)}** · 👍 {int(r.thumbsUpCount)}")
            st.write(r.content)
            key = f"reply_{r.reviewId}"
            if st.button("Draft reply", key=f"btn_{r.reviewId}"):
                st.session_state[key], st.session_state[key + "_eng"] = draft(r.content, int(r.score), r.primary_category)
            if key in st.session_state:
                st.text_area("Draft (edit before posting)", st.session_state[key], key=key + "_ta", max_chars=350)
                st.caption(f"drafted by: {st.session_state[key + '_eng']}")

# ------------------------------------------------------------------ METHOD
with tab_method:
    st.markdown("""
**Data.** Public Google Play reviews for MoveInSync's apps, pulled with the open-source `google-play-scraper`
(country=IN, language=EN, newest first). Re-runs only fetch reviews not seen before. Each run also stores the app's
headline rating, so the rating history builds over time.

**Tagging.** Each review is labelled with one or more issues from a taxonomy that follows the employee journey
(login → book → pickup time → track → board → ride → raise an issue). An LLM (Gemini or Claude, switchable) reads the
review (including Hindi/Hinglish) and returns the issues, the main issue, severity, and a one-line summary as validated JSON. Without an API key, a
keyword-rule fallback is used so the dashboard always works.

**Stars at stake.** For each issue: Σ(5 − stars) over reviews whose *main* complaint is that issue, ÷ all reviews in
the window. It's the rise in average rating if those reviews had been 5★, so issues can be compared in rating points.

**Priority.** stars at stake × (1.0 if the app/product team owns the fix, 0.5 if it depends on on-ground operations)
× (1 + trend). It is a ranking aid, not a forecast.

**Release regression.** A version is flagged when its 1-star share is ≥ 7 points above the average of the previous
5 releases (min 30 reviews).

**Assumptions & limits.**
- Written reviews are a vocal subset. The headline Play Store score includes star-only ratings and is all-time,
  so it is higher than the written-review average. Google's displayed score weights recent ratings, which is why the
  recent written-review trend matters.
- Only reviews Google Play exposes publicly are included. Language filter `en` still returns Hinglish text.
- The employee app is the focus; driver and field apps are tracked but have few reviews.
""")
