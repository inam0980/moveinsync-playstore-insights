"""Visual layer for the Streamlit dashboard: CSS + small HTML components.

All user-generated text goes through html.escape before it is rendered.
"""
from html import escape

import streamlit as st

# Fixed color per owning team (assigned in order, never by rank)
OWNER_COLORS = {"App Engineering": "#2a78d6", "Product": "#eb6834", "Operations": "#1baf7a", "Support": "#eda100"}
OWNER_ICONS = {"App Engineering": "📱", "Product": "🧩", "Operations": "🚕", "Support": "🎧"}
GOOD, BAD, NEUTRAL = "#0ca30c", "#d03b3b", "#898781"

CSS = """
<style>
:root { --ink:#1b1b2f; --ink2:#55566b; --card:#ffffff; --line:rgba(27,27,47,.08); }
.block-container { padding-top: 1.6rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#eef0ff 0%,#f4fbf8 100%); }

/* hero */
.hero { background: linear-gradient(120deg,#4f46e5 0%,#2a78d6 50%,#14b8a6 100%); color:#fff;
        border-radius:20px; padding:26px 30px; margin-bottom:18px; position:relative; overflow:hidden;
        box-shadow:0 10px 30px rgba(79,70,229,.25); }
.hero:after { content:""; position:absolute; right:-60px; top:-60px; width:240px; height:240px;
              background:radial-gradient(circle,rgba(255,255,255,.25),transparent 70%); }
.hero h1 { color:#fff; font-size:1.9rem; line-height:1.25; margin:0 0 6px 0; padding:0; }
.hero p { color:rgba(255,255,255,.9); margin:0; font-size:.98rem; }
.hero .chip { display:inline-block; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.3);
              padding:3px 10px; border-radius:999px; font-size:.8rem; margin:10px 6px 0 0; }

/* KPI cards */
.kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:16px; }
.kpi { background:var(--card); border-radius:16px; padding:16px 18px; border:1px solid var(--line);
       box-shadow:0 4px 14px rgba(27,27,47,.06); border-top:5px solid var(--accent); }
.kpi .lbl { color:var(--ink2); font-size:.8rem; font-weight:600; text-transform:uppercase; letter-spacing:.03em; }
.kpi .val { color:var(--ink); font-size:1.9rem; font-weight:800; margin:4px 0 6px; }
.kpi .ico { float:right; font-size:1.4rem; background:var(--tint); border-radius:12px; padding:4px 8px; }
.delta { display:inline-block; font-size:.78rem; font-weight:700; padding:2px 9px; border-radius:999px; }

/* verdict */
.verdict { background:linear-gradient(135deg,#fff7ed,#fdf2f8); border:1px solid #fbcfe8; border-left:6px solid #ec4899;
           border-radius:16px; padding:18px 22px; margin:4px 0 18px; color:var(--ink); }
.verdict b { color:#9d174d; }
.split { display:flex; gap:10px; flex-wrap:wrap; margin-top:10px; }
.pill { padding:6px 12px; border-radius:999px; font-weight:700; font-size:.85rem; color:#fff; }

/* tabs */
.stTabs [data-baseweb="tab-list"] { gap:8px; flex-wrap:wrap; }
.stTabs [data-baseweb="tab"] { background:#eef0fa; border-radius:999px; padding:8px 16px; height:auto; }
.stTabs [aria-selected="true"] { background:linear-gradient(120deg,#4f46e5,#2a78d6); color:#fff !important; }
.stTabs [aria-selected="true"] p { color:#fff !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }

/* section headings */
.sec { font-size:1.25rem; font-weight:800; color:var(--ink); margin:14px 0 4px; }
.sec span { background:linear-gradient(120deg,#4f46e5,#14b8a6); -webkit-background-clip:text; background-clip:text;
            color:transparent; }
.sub { color:var(--ink2); font-size:.9rem; margin-bottom:10px; }

/* quick-win cards */
.win { background:var(--card); border-radius:18px; padding:18px 20px; margin-bottom:14px; border:1px solid var(--line);
       box-shadow:0 6px 18px rgba(27,27,47,.07); display:flex; gap:16px; }
.win .num { flex:0 0 46px; height:46px; border-radius:14px; color:#fff; font-weight:800; font-size:1.3rem;
            display:flex; align-items:center; justify-content:center;
            background:linear-gradient(135deg,var(--c1),var(--c2)); }
.win h4 { margin:0 0 6px; color:var(--ink); font-size:1.05rem; }
.win .why { color:var(--ink2); font-size:.92rem; margin-bottom:8px; }
.win ul { margin:0 0 8px 18px; padding:0; color:var(--ink); font-size:.92rem; }
.tag { display:inline-block; font-size:.75rem; font-weight:700; padding:3px 10px; border-radius:999px; margin:2px 6px 2px 0;
       background:var(--bg); color:var(--fg); }

/* review quotes */
.quote { background:#f6f7ff; border-left:4px solid var(--qc); border-radius:4px 14px 14px 4px; padding:10px 14px;
         margin:8px 0; color:var(--ink); font-size:.92rem; }
.quote .meta { color:var(--ink2); font-size:.78rem; margin-top:4px; }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, chips: list[str]) -> None:
    chip_html = "".join(f'<span class="chip">{escape(c)}</span>' for c in chips)
    st.markdown(f'<div class="hero"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p>{chip_html}</div>',
                unsafe_allow_html=True)


def _delta(text: str, good: bool | None) -> str:
    color = NEUTRAL if good is None else GOOD if good else BAD
    return f'<span class="delta" style="background:{color}1f;color:{color}">{escape(text)}</span>'


def kpi_cards(cards: list[dict]) -> None:
    """cards: {label, value, icon, accent, delta?, good?(True/False/None)}"""
    html = []
    for c in cards:
        delta = _delta(c["delta"], c.get("good")) if c.get("delta") else ""
        html.append(f'<div class="kpi" style="--accent:{c["accent"]};--tint:{c["accent"]}1f">'
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


WIN_GRADIENTS = [("#ec4899", "#f97316"), ("#4f46e5", "#06b6d4"), ("#10b981", "#84cc16")]


def tag(text: str, color: str) -> str:
    return f'<span class="tag" style="--bg:{color}1f;--fg:{color}">{escape(text)}</span>'


def win_card(i: int, title: str, why: str, steps: list[str], owner: str, effort: str, metric: str) -> None:
    c1, c2 = WIN_GRADIENTS[(i - 1) % len(WIN_GRADIENTS)]
    items = "".join(f"<li>{escape(s)}</li>" for s in steps)
    tags = tag(f"👥 {owner}", "#4f46e5") + tag(f"⏱ {effort}", "#0891b2") + tag(f"📏 {metric}", "#059669")
    st.markdown(f'<div class="win" style="--c1:{c1};--c2:{c2}"><div class="num">{i}</div><div>'
                f'<h4>{escape(title)}</h4><div class="why">{escape(why)}</div><ul>{items}</ul>{tags}</div></div>',
                unsafe_allow_html=True)


def quote(text: str, meta: str, stars: int) -> None:
    qc = BAD if stars <= 2 else "#eda100" if stars == 3 else GOOD
    st.markdown(f'<div class="quote" style="--qc:{qc}">{"★" * stars}{"☆" * (5 - stars)} &nbsp;{escape(text)}'
                f'<div class="meta">{escape(meta)}</div></div>', unsafe_allow_html=True)


def style_fig(fig, height: int):
    """Common chart chrome: transparent background, soft grid, readable font."""
    fig.update_layout(height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color="#33344a"),
                      margin=dict(l=0, r=10, t=30, b=0), hoverlabel=dict(bgcolor="white", font_size=13))
    fig.update_xaxes(gridcolor="rgba(27,27,47,.07)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(27,27,47,.07)", zeroline=False)
    return fig
