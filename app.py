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
    for _k in ("GEMINI_API_KEY", "LLM_PROVIDER"):
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
import ui  # noqa: E402

st.set_page_config(page_title="MoveInSync Play Store Insights",
                   page_icon=str(ui.LOGO) if ui.LOGO.exists() else "🚕", layout="wide")
ui.inject_css()
if ui.LOGO.exists():
    st.logo(str(ui.LOGO), size="large")

OWNER_COLORS = ui.OWNER_COLORS
CRITICAL = "#f87171"
MUTED = "#94a3b8"
SERIES = "#a78bfa"


@st.cache_data(ttl=3600)
def load_data():
    return A.load(), A.load_snapshots()


if not CLASSIFIED_CSV.exists():
    st.error("No data yet. Run `python -m pipeline.run` first.")
    st.stop()

df_all, snaps = load_data()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("## 🎛 Filters")
    app_id = st.selectbox("App", list(APPS), index=list(APPS).index(PRIMARY_APP), format_func=APPS.get)
    days = st.select_slider("Analysis window", options=[90, 180, 365, 730], value=365,
                            format_func=lambda d: f"Last {d} days")
    st.divider()
    st.caption(f"Reviews stored: **{len(df_all):,}**")
    st.caption(f"Latest review: **{df_all['at'].max():%d %b %Y}**")
    ai = df_all[df_all["classifier"].isin(AI_ENGINES)]
    engines = ", ".join(sorted(ai["classifier"].unique())) or "none yet"
    n_ml = (df_all["classifier"] == "local-ml").sum()
    st.caption(f"Tagged by AI ({engines}): **{len(ai):,}** · local ML backup: **{n_ml:,}** · rest: keyword rules")
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
ui.hero("Why are MoveInSync's Play Store ratings low, and what to fix first",
        f"{APPS[app_id]} · Google Play India",
        [f"📝 {len(df):,} reviews analysed", f"🗓 Latest review {df['at'].max():%d %b %Y}", "🔁 Refreshes weekly"])

c = k["current"]; p = k["previous"]
cards = []
if not snap.empty:
    s = snap.iloc[0]
    cards.append({"label": "Play Store rating", "value": f"{s['score']:.2f} ★", "icon": "⭐",
                  "accent": "#a78bfa", "delta": f"{int(s['ratings']):,} ratings", "good": None})
cards.append({"label": "Review avg · 90d", "value": f"{c['avg']:.2f} ★", "icon": "✍️", "accent": "#22d3ee",
              "delta": f"{c['avg'] - p['avg']:+.2f} vs prior 90d", "good": c["avg"] >= p["avg"]})
cards.append({"label": "1★ share · 90d", "value": f"{c['one_star']:.0%}", "icon": "😡", "accent": "#f87171",
              "delta": f"{(c['one_star'] - p['one_star']) * 100:+.1f} pp", "good": c["one_star"] <= p["one_star"]})
cards.append({"label": "Reply rate · 1-2★", "value": f"{c['reply_rate']:.0%}", "icon": "💬", "accent": "#facc15",
              "delta": "nobody answers" if c["reply_rate"] < 0.1 else f"{(c['reply_rate'] - p['reply_rate']) * 100:+.1f} pp",
              "good": c["reply_rate"] >= 0.5})
latest = ver.iloc[-1] if not ver.empty else None
if latest is not None:
    cards.append({"label": f"Latest v{latest['reviewCreatedVersion']}", "value": f"{latest['one_star']:.0%} 1★",
                  "icon": "🚀", "accent": "#34d399",
                  "delta": f"{latest['delta_pp']:+.1f} pp vs usual" + (" ⚠" if latest["regression"] else ""),
                  "good": not latest["regression"]})
ui.kpi_cards(cards)

# headline verdict, computed
w = A.window(df, days)
gap = 5 - w["score"].mean()
top3 = imp.head(3)["issue"].tolist()
app_share = imp.loc[imp["app_owned"], "stars_at_stake"].sum()
ops_share = imp.loc[~imp["app_owned"], "stars_at_stake"].sum()
ui.verdict(
    f"<b>Verdict:</b> written reviews average <b>{w['score'].mean():.2f}★</b> over the last {days} days, "
    f"<b>{gap:.2f} stars</b> short of 5. Problems inside the app cost <b>{app_share:.2f}★</b>; on-ground operations "
    f"cost <b>{ops_share:.2f}★</b>; the rest are 1★ reviews with no stated reason. "
    f"<b>Fix first:</b> {ui.escape(', '.join(top3))}.",
    A.owner_split(imp).set_index("owner")["stars_at_stake"].to_dict(),
)

tab_why, tab_plan, tab_trend, tab_explore, tab_reply, tab_method = st.tabs(
    ["🔍 Why it's low", "✅ Action plan", "📈 Trends", "🗂 Reviews", "💬 Replies", "📘 Method"])

# ------------------------------------------------------------------ WHY
with tab_why:
    ui.section("Which issues cost the most rating points",
               "Stars at stake = how much the average written-review rating would rise if every review whose "
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
    ui.style_fig(fig, 480).update_layout(bargap=0.3, legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title=None),
                                         yaxis=dict(categoryorder="total ascending"), margin=dict(t=60))
    fig.update_traces(texttemplate="%{x:.2f}", textposition="outside", cliponaxis=False)
    st.plotly_chart(fig, width="stretch")

    a, b = st.columns(2)
    with a:
        ui.section("Stars lost, by team that owns the fix")
        split = A.owner_split(imp)
        f2 = px.pie(split, names="owner", values="stars_at_stake", color="owner", color_discrete_map=OWNER_COLORS,
                    hole=0.55)
        f2.update_traces(textinfo="label+percent", marker=dict(line=dict(color=ui.SURFACE, width=4)),
                         hovertemplate="%{label}: %{value:.3f} stars<extra></extra>")
        ui.style_fig(f2, 320).update_layout(showlegend=False)
        st.plotly_chart(f2, width="stretch")
    with b:
        ui.section("Growing vs shrinking complaints", "Share of 1-2★ reviews, last 90 days vs the 90 days before")
        t = imp[["issue", "trend_pp"]].sort_values("trend_pp")
        f3 = px.bar(t, x="trend_pp", y="issue", orientation="h", labels={"trend_pp": "Change (pp)", "issue": ""})
        f3.update_traces(marker_color=[ui.BAD if v > 1 else ui.GOOD if v < -1 else ui.NEUTRAL for v in t["trend_pp"]],
                         hovertemplate="%{y}: %{x:+.1f} pp<extra></extra>", texttemplate="%{x:+.1f}",
                         textposition="outside", cliponaxis=False)
        ui.style_fig(f3, 320).update_layout(bargap=0.3, yaxis=dict(categoryorder="array", categoryarray=list(t["issue"])))
        st.plotly_chart(f3, width="stretch")

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

    ui.section("⚡ Do this week: three moves on the rating mechanism itself")
    for i, q in enumerate(QUICK_WINS, 1):
        ui.win_card(i, q["title"].format(**ctx), q["why"].format(**ctx), q["what"], q["owner"], q["effort"], q["metric"])

    ui.section("🛠 Then: fix issues in priority order",
               "Ranked by stars at stake × how directly the app team controls it (ops issues count half) × trend. "
               "Re-ranks automatically on every data refresh.")
    for rank, r in enumerate(imp.itertuples(), 1):
        pb = PLAYBOOK.get(r.category)
        if not pb:
            continue
        with st.expander(f"{ui.OWNER_ICONS.get(r.owner, '•')} #{rank} · {r.issue} — {r.stars_at_stake:.3f}★ at stake · {r.owner} · "
                         f"{'▲' if r.trend_pp > 1 else '▼' if r.trend_pp < -1 else '–'} {r.trend_pp:+.1f} pp",
                         expanded=rank <= 3):
            st.markdown(ui.tag(f"{ui.OWNER_ICONS.get(r.owner, '')} {r.owner}", OWNER_COLORS.get(r.owner, ui.NEUTRAL))
                        + ui.tag(f"⏱ Effort {pb['effort']}", "#0891b2") + ui.tag(f"📏 {pb['metric']}", "#059669"),
                        unsafe_allow_html=True)
            st.markdown("**What to do**")
            st.markdown("\n".join(f"- {x}" for x in pb["fix"]))
            ex = A.examples(df, r.category, 4, days)
            if len(ex):
                st.markdown("**🗣 What users are saying**")
                for e in ex.itertuples():
                    v = f"v{e.reviewCreatedVersion}" if pd.notna(e.reviewCreatedVersion) else ""
                    ui.quote(e.content[:300], f"{e.at:%d %b %Y} · {v} · 👍 {int(e.thumbsUpCount)}", int(e.score))

# ------------------------------------------------------------------ TRENDS
with tab_trend:
    m = mon[mon["month"] >= mon["month"].max() - pd.DateOffset(months=36)]
    a, b = st.columns(2)
    with a:
        ui.section("⭐ Average stars of written reviews, by month")
        f = px.area(m, x="month", y="avg", markers=True, labels={"month": "", "avg": "Avg stars"})
        f.update_traces(line=dict(width=3, color="#a78bfa"), fillcolor="rgba(167,139,250,.18)", marker=dict(size=8),
                        hovertemplate="%{x|%b %Y}: %{y:.2f}★<extra></extra>")
        ui.style_fig(f, 300).update_layout(hovermode="x unified", yaxis_range=[1, 5])
        st.plotly_chart(f, width="stretch")
    with b:
        ui.section("😡 Share of 1-star reviews, by month")
        f = px.area(m, x="month", y="one_star", markers=True, labels={"month": "", "one_star": "1-star share"})
        f.update_traces(line=dict(width=2.5, color=CRITICAL), fillcolor="rgba(248,113,113,.16)", marker=dict(size=8),
                        hovertemplate="%{x|%b %Y}: %{y:.0%}<extra></extra>")
        ui.style_fig(f, 300).update_layout(yaxis_tickformat=".0%", hovermode="x unified")
        st.plotly_chart(f, width="stretch")

    ui.section("💬 Developer reply rate on 1-2★ reviews, by quarter")
    rq = df[df["negative"]].assign(q=lambda x: x["at"].dt.to_period("Q").dt.to_timestamp()).groupby("q")["replied"].mean().reset_index()
    rq = rq[rq["q"] >= pd.Timestamp("2021-01-01")]
    f = px.bar(rq, x="q", y="replied", labels={"q": "", "replied": "Reply rate"})
    f.update_traces(marker_color=[ui.GOOD if v >= 0.5 else "#facc15" if v >= 0.1 else ui.BAD for v in rq["replied"]],
                    marker_line_width=0, hovertemplate="%{x|Q%q %Y}: %{y:.0%}<extra></extra>")
    ui.style_fig(f, 260).update_layout(yaxis_tickformat=".0%", bargap=0.3)
    st.plotly_chart(f, width="stretch")

    ui.section("🚀 1-star share by app release",
               "Last 20 releases with ≥30 reviews. Red = regression: 7+ pp above the previous 5 releases.")
    vv = ver.tail(20).copy()
    vv["status"] = vv["regression"].map({True: "⚠ Regression", False: "Normal"})
    f = go.Figure()
    f.add_bar(x=vv["reviewCreatedVersion"].astype(str), y=vv["one_star"], name="1★ share (red = regression)",
              marker_color=[CRITICAL if r else SERIES for r in vv["regression"]], marker_line_width=0,
              customdata=vv[["n", "avg", "delta_pp", "status"]],
              hovertemplate="v%{x}<br>1-star: %{y:.0%}<br>Avg: %{customdata[1]:.2f}★ (%{customdata[0]} reviews)"
                            "<br>vs baseline: %{customdata[2]:+.1f} pp<br>%{customdata[3]}<extra></extra>")
    f.add_scatter(x=vv["reviewCreatedVersion"].astype(str), y=vv["baseline_one_star"], mode="lines",
                  line=dict(color=MUTED, width=2, dash="dot"), name="Baseline (prev. 5 releases)",
                  hovertemplate="Baseline: %{y:.0%}<extra></extra>")
    ui.style_fig(f, 320).update_layout(yaxis_tickformat=".0%", bargap=0.3,
                    legend=dict(orientation="h", y=1.1, x=0), xaxis_type="category")
    st.plotly_chart(f, width="stretch")
    st.dataframe(vv[["reviewCreatedVersion", "first_seen", "n", "avg", "one_star", "delta_pp", "status"]].iloc[::-1],
                 hide_index=True, width="stretch",
                 column_config={"one_star": st.column_config.NumberColumn(format="%.0%"),
                                "avg": st.column_config.NumberColumn(format="%.2f"),
                                "delta_pp": st.column_config.NumberColumn(format="%+.1f"),
                                "first_seen": st.column_config.DatetimeColumn(format="DD MMM YYYY")})

    if not snaps.empty:
        ui.section("🏁 Benchmark: headline Play Store rating vs competitors", "Latest snapshot")
        bm = snaps.sort_values("snapshot_at").groupby("app_id").tail(1)
        bm = bm[["app_name", "kind", "score", "ratings", "installs", "version"]].sort_values("score", ascending=False)
        st.dataframe(bm, hide_index=True, width="stretch",
                     column_config={"score": st.column_config.NumberColumn("Rating", format="%.2f ★"),
                                    "ratings": st.column_config.NumberColumn("Ratings", format="%d"),
                                    "installs": st.column_config.NumberColumn("Installs", format="%d"),
                                    "app_name": "App", "kind": "Type"})

    dev = A.device_mentions(df, 90)
    if len(dev):
        ui.section("📱 Devices / Android versions named in 1-2★ reviews", "Last 90 days")
        st.dataframe(dev, hide_index=True)

    if not snaps.empty and snaps["snapshot_at"].nunique() > 1:
        ui.section("⭐ Play Store headline rating over time", "One point per pipeline run")
        ss = snaps[snaps["kind"] == "moveinsync"]
        f = px.line(ss, x="snapshot_at", y="score", color="app_name", markers=True)
        ui.style_fig(f, 280)
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
    ui.section("💬 Unanswered 1-2★ reviews", "Last 30 days")
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
(login → book → pickup time → track → board → ride → raise an issue). Google Gemini reads the
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
