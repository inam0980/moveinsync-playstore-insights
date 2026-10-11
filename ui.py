"""Visual layer for the Streamlit dashboard (dark neon theme): CSS + small HTML components.

All user-generated text goes through html.escape before it is rendered.
"""
import base64
from html import escape
from pathlib import Path

import streamlit as st

# Fixed color per owning team (assigned in order, never by rank); bright steps chosen for the dark surface
OWNER_COLORS = {"App Engineering": "#60a5fa", "Product": "#fb923c", "Operations": "#34d399", "Support": "#facc15"}
OWNER_ICONS = {"App Engineering": "📱", "Product": "🧩", "Operations": "🚕", "Support": "🎧"}
GOOD, BAD, NEUTRAL = "#34d399", "#f87171", "#94a3b8"
VIOLET, CYAN, PINK = "#a78bfa", "#22d3ee", "#f472b6"
SURFACE = "#0b1020"

CSS = """
<style>
:root { --bg:#0b1020; --card:#141a33; --card2:#1b2244; --ink:#eef1ff; --ink2:#a3acd1;
        --line:rgba(167,139,250,.18); --v:#8b5cf6; --c:#22d3ee; --p:#f472b6; }
.stApp { background:
  radial-gradient(1200px 600px at 10% -10%, rgba(139,92,246,.18), transparent 60%),
  radial-gradient(900px 500px at 100% 0%, rgba(34,211,238,.12), transparent 60%), var(--bg); }
.block-container { padding-top: 1.6rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#121836 0%,#0d1228 100%);
                            border-right:1px solid var(--line); }
[data-testid="stHeader"] { background: transparent; }

/* hero */
@keyframes flow { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
.hero { background: linear-gradient(120deg,#6d28d9,#2563eb,#0891b2,#db2777,#6d28d9); background-size:300% 300%;
        animation: flow 14s ease infinite; color:#fff; border-radius:22px; padding:28px 32px; margin-bottom:20px;
        position:relative; overflow:hidden; box-shadow:0 0 0 1px rgba(255,255,255,.08), 0 18px 50px rgba(109,40,217,.35); }
.hero:after { content:""; position:absolute; right:-80px; top:-80px; width:280px; height:280px;
              background:radial-gradient(circle,rgba(255,255,255,.22),transparent 70%); }
.hero h1 { color:#fff; font-size:1.95rem; line-height:1.25; margin:0 0 6px 0; padding:0; font-weight:800; }
.hero p { color:rgba(255,255,255,.88); margin:0; font-size:1rem; }
.hero-row { display:flex; gap:22px; align-items:center; position:relative; z-index:1; }
.hero .logo { width:84px; height:84px; flex:0 0 84px; border-radius:20px;
              box-shadow:0 0 0 3px rgba(255,255,255,.25), 0 10px 30px rgba(0,0,0,.35); }
@media (max-width: 700px) { .hero .logo { width:56px; height:56px; flex-basis:56px; } }
.hero .chip { display:inline-block; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.28);
              padding:4px 12px; border-radius:999px; font-size:.8rem; margin:12px 6px 0 0; backdrop-filter:blur(4px); }

/* KPI cards */
.kpis { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; margin-bottom:18px; }
@media (max-width: 1150px) { .kpis { grid-template-columns:repeat(3,minmax(0,1fr)); } }
@media (max-width: 760px) { .kpis { grid-template-columns:repeat(2,minmax(0,1fr)); } }
.kpi { background:linear-gradient(160deg,var(--card2),var(--card)); border-radius:18px; padding:16px 18px;
       border:1px solid var(--line); position:relative; overflow:hidden; transition:transform .15s, box-shadow .15s; }
.kpi:before { content:""; position:absolute; inset:0 0 auto 0; height:3px; background:var(--accent);
              box-shadow:0 0 18px var(--accent); }
.kpi:hover { transform:translateY(-3px); box-shadow:0 10px 30px -8px var(--accent); }
.kpi .lbl { color:var(--ink2); font-size:.72rem; min-height:2.2em; font-weight:700; text-transform:uppercase; letter-spacing:.05em; }
.kpi .val { color:var(--ink); font-size:1.8rem; font-weight:800; margin:6px 0 8px; text-shadow:0 0 22px var(--tint); }
.kpi .ico { float:right; font-size:1.35rem; background:var(--tint); border-radius:12px; padding:4px 8px; }
.delta { display:inline-block; font-size:.76rem; font-weight:700; padding:3px 10px; border-radius:999px; }

/* verdict */
.verdict { background:linear-gradient(135deg,rgba(139,92,246,.16),rgba(34,211,238,.08)); border:1px solid var(--line);
           border-left:5px solid var(--v); border-radius:18px; padding:18px 22px; margin:4px 0 20px; color:var(--ink);
           box-shadow:0 0 40px -18px var(--v); }
.verdict b { color:#c4b5fd; }
.split { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
.pill { padding:6px 13px; border-radius:999px; font-weight:700; font-size:.84rem; color:#0b1020; }

/* tabs: one segmented bar, equal-width pills, never wraps (Streamlit renders tabs as div[role=tab]) */
.stTabs div:has(> [role="tab"]) { display:flex; flex-wrap:nowrap; gap:6px; width:100%; padding:6px;
    background:var(--card); border:1px solid var(--line) !important; border-radius:999px;
    overflow-x:auto; scrollbar-width:none; box-shadow:0 8px 24px -12px rgba(0,0,0,.6); }
.stTabs div:has(> [role="tab"])::-webkit-scrollbar { display:none; }
.stTabs div:has(> div > [role="tab"]), .stTabs div:has(> div > div > [role="tab"]) {
    border-bottom:none !important; box-shadow:none !important; }
.stTabs div:has(> div > [role="tab"])::before, .stTabs div:has(> div > [role="tab"])::after,
.stTabs div:has(> [role="tab"])::before, .stTabs div:has(> [role="tab"])::after { display:none !important; }
.stTabs [role="tab"] { flex:1 1 0; min-width:max-content; justify-content:center; text-align:center;
    background:transparent; border:none; border-radius:999px; padding:9px 12px !important; transition:all .15s; }
.stTabs [role="tab"]:hover { background:rgba(167,139,250,.12); }
.stTabs [role="tab"] p { color:var(--ink2) !important; font-weight:600; font-size:.92rem; white-space:nowrap; }
.stTabs [role="tab"][aria-selected="true"] { background:linear-gradient(120deg,#7c3aed,#2563eb 60%,#0891b2);
    box-shadow:0 0 22px -4px rgba(124,58,237,.8); }
.stTabs [role="tab"][aria-selected="true"] p { color:#fff !important; }
.stTabs .react-aria-SelectionIndicator { display:none !important; }
@media (max-width: 1250px) { .stTabs [role="tab"] { padding:8px 8px !important; }
  .stTabs [role="tab"] p { font-size:.84rem; } .stTabs div:has(> [role="tab"]) { gap:2px; padding:5px; } }

/* section headings */
.sec { font-size:1.22rem; font-weight:800; margin:16px 0 4px; }
.sec span { background:linear-gradient(120deg,#c4b5fd,#67e8f9 55%,#f9a8d4); -webkit-background-clip:text;
            background-clip:text; color:transparent; }
.sub { color:var(--ink2); font-size:.9rem; margin-bottom:10px; }

/* quick-win cards */
.win { background:linear-gradient(160deg,var(--card2),var(--card)); border-radius:20px; padding:18px 20px;
       margin-bottom:14px; border:1px solid var(--line); display:flex; gap:16px; transition:box-shadow .15s; }
.win:hover { box-shadow:0 0 34px -10px var(--c1); }
.win .num { flex:0 0 48px; height:48px; border-radius:14px; color:#fff; font-weight:800; font-size:1.3rem;
            display:flex; align-items:center; justify-content:center;
            background:linear-gradient(135deg,var(--c1),var(--c2)); box-shadow:0 0 22px -4px var(--c1); }
.win h4 { margin:0 0 6px; color:var(--ink); font-size:1.05rem; }
.win .why { color:var(--ink2); font-size:.92rem; margin-bottom:8px; }
.win ul { margin:0 0 10px 18px; padding:0; color:var(--ink); font-size:.92rem; }
.tag { display:inline-block; font-size:.74rem; font-weight:700; padding:3px 10px; border-radius:999px; margin:2px 6px 2px 0;
       background:var(--bg); color:var(--fg); border:1px solid var(--fg); }

/* review quotes */
.quote { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--qc);
         border-radius:6px 16px 16px 6px; padding:10px 14px; margin:8px 0; color:var(--ink); font-size:.92rem; }
.quote .stars { color:var(--qc); letter-spacing:1px; }
.quote .meta { color:var(--ink2); font-size:.78rem; margin-top:4px; }

/* expanders */
[data-testid="stExpander"] details { background:var(--card); border:1px solid var(--line) !important; border-radius:16px; }
[data-testid="stExpander"] summary:hover { color:#c4b5fd; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


LOGO = Path(__file__).parent / "assets" / "logo.png"


def hero(title: str, subtitle: str, chips: list[str]) -> None:
    chip_html = "".join(f'<span class="chip">{escape(c)}</span>' for c in chips)
    logo = ""
    if LOGO.exists():
        b64 = base64.b64encode(LOGO.read_bytes()).decode()
        logo = f'<img class="logo" src="data:image/png;base64,{b64}" alt="MoveInSync logo">'
    st.markdown(f'<div class="hero"><div class="hero-row">{logo}<div><h1>{escape(title)}</h1>'
                f'<p>{escape(subtitle)}</p>{chip_html}</div></div></div>', unsafe_allow_html=True)


def _delta(text: str, good: bool | None) -> str:
    color = NEUTRAL if good is None else GOOD if good else BAD
    return f'<span class="delta" style="background:{color}26;color:{color}">{escape(text)}</span>'


def kpi_cards(cards: list[dict]) -> None:
    """cards: {label, value, icon, accent, delta?, good?(True/False/None)}"""
    html = []
    for c in cards:
        delta = _delta(c["delta"], c.get("good")) if c.get("delta") else ""
        html.append(f'<div class="kpi" style="--accent:{c["accent"]};--tint:{c["accent"]}33">'
                    f'<span class="ico">{c["icon"]}</span><div class="lbl">{escape(c["label"])}</div>'
                    f'<div class="val">{escape(c["value"])}</div>{delta}</div>')
    st.markdown(f'<div class="kpis">{"".join(html)}</div>', unsafe_allow_html=True)


def verdict(body_html: str, split: dict[str, float]) -> None:
    pills = "".join(f'<span class="pill" style="background:{OWNER_COLORS[o]}">{OWNER_ICONS[o]} {escape(o)}: −{v:.2f}★</span>'
                    for o, v in split.items() if o in OWNER_COLORS)
    st.markdown(f'<div class="verdict">🎯 {body_html}<div class="split">{pills}</div></div>', unsafe_allow_html=True)


def section(title: str, subtitle: str = "") -> None:
    sub = f'<div class="sub">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="sec"><span>{escape(title)}</span></div>{sub}', unsafe_allow_html=True)


WIN_GRADIENTS = [("#7c3aed", "#db2777"), ("#2563eb", "#06b6d4"), ("#059669", "#84cc16")]


def tag(text: str, color: str) -> str:
    return f'<span class="tag" style="--bg:{color}1f;--fg:{color}">{escape(text)}</span>'


def win_card(i: int, title: str, why: str, steps: list[str], owner: str, effort: str, metric: str) -> None:
    c1, c2 = WIN_GRADIENTS[(i - 1) % len(WIN_GRADIENTS)]
    items = "".join(f"<li>{escape(s)}</li>" for s in steps)
    tags = tag(f"👥 {owner}", VIOLET) + tag(f"⏱ {effort}", CYAN) + tag(f"📏 {metric}", GOOD)
    st.markdown(f'<div class="win" style="--c1:{c1};--c2:{c2}"><div class="num">{i}</div><div>'
                f'<h4>{escape(title)}</h4><div class="why">{escape(why)}</div><ul>{items}</ul>{tags}</div></div>',
                unsafe_allow_html=True)


def quote(text: str, meta: str, stars: int) -> None:
    qc = BAD if stars <= 2 else "#facc15" if stars == 3 else GOOD
    st.markdown(f'<div class="quote" style="--qc:{qc}"><span class="stars">{"★" * stars}{"☆" * (5 - stars)}</span>'
                f' &nbsp;{escape(text)}<div class="meta">{escape(meta)}</div></div>', unsafe_allow_html=True)


def style_fig(fig, height: int):
    """Common chart chrome for the dark surface: transparent background, faint grid, light text."""
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color="#c7cdea"),
                      margin=dict(l=0, r=10, t=30, b=0),
                      hoverlabel=dict(bgcolor="#1b2244", bordercolor="#8b5cf6", font=dict(color="#eef1ff", size=13)))
    fig.update_xaxes(gridcolor="rgba(167,139,250,.10)", zeroline=False, linecolor="rgba(167,139,250,.2)")
    fig.update_yaxes(gridcolor="rgba(167,139,250,.10)", zeroline=False, linecolor="rgba(167,139,250,.2)")
    return fig
