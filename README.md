# MoveInSync Play Store Insights

**Why are MoveInSync's Play Store ratings low, and what should we fix first?**
A repeatable pipeline that pulls every public Google Play review of MoveInSync's apps, uses Google Gemini to tag each
review against the employee commute journey, ranks issues by how many rating points they cost, and turns that
into a prioritised action plan. It re-runs weekly, so *"How are our Play Store ratings?"* always has a current answer.

**▶ Live dashboard:** `<add Streamlit link>` · **Data:** 24,400+ reviews, 2014 – Oct 2026

---

## The answer in one minute

| | |
|---|---|
| **Headline rating** | 4.64★ all-time (114,867 ratings). Above Routematic (4.34) and eTMS Buddy (1.68), but propped up by silent 5★ taps |
| **What people actually write** | **3.83★** over the last 12 months; **1 in 4 written reviews is 1★**. New users and HR buyers read these, and Google's displayed score weights recent ratings. |
| **Where the stars go** | Problems **inside the app** (crashes, confusing new UI, login/OTP, booking, tracking, forced prompts) cost **~0.68★**. On-ground operations (late cabs, drivers, routes, helpdesk) cost **~0.21★**. The app team can fix most of the gap itself. |
| **Releases hurt** | 5 of the last 12 releases had 7+ points more 1★ reviews than the ones before them. The current **12.19.0** is one of them (32% 1★). |
| **Nobody answers** | Developer replies to 1–2★ reviews fell from **97% (2023) to 1% (2026)**. |

## What to do, in order

### This week: three moves on the rating mechanism itself
1. **Make trip feedback skippable and route happy riders to the Play Store.**
   The app blocks use until each trip is rated (twice a day), and users come to the Play Store to leave 1★ in
   protest (*"forcing me to give rating after every ride, so I came here to give you 1 star"*). Add *Skip*. When a
   rider gives 4–5★ in-app after an on-time trip, trigger Google's **In-App Review API** (max once per 90 days). Route
   1–3★ in-app ratings to a *"What went wrong?"* ticket instead. *Owner: Product + App Eng · Effort: 1 sprint.*
2. **Restart replying to reviews within 48h.** Reviewers can update their rating after a reply. The dashboard's
   **Reply queue** drafts a specific reply with Gemini for each unanswered 1–2★ review; support edits and posts.
   *Owner: Support · Effort: start now.*
3. **Gate releases on review health.** Ship via staged rollout (5% → 20% → 100%) and run this pipeline daily during
   rollout. If the new version's 1★ share is 7+ pp above baseline, halt. The GitHub Action already exits non-zero
   on a regression. *Owner: release manager · Effort: S.*

### Next 2–6 weeks: fix in this order (priority = stars at stake × who can fix it × trend)
| # | Issue | Concrete fix | Owner |
|---|---|---|---|
| 1 | **Crashes / won't open** | **P0 on 12.19.x:** app closes on launch on Pixel 8 (Android 17), OnePlus 12 and Vivo V25 Pro. Since June 2026 users also see *"can't be opened, not downloaded from Play Store"* every few days on genuine installs: the installer/Play-Integrity check is failing closed. Make it fail open, verify server-side. Fix "no internet" on working Wi-Fi. | App Eng |
| 2 | **Confusing new UI / permissions** (fastest-growing: +7 pp of 1★ reviews in 90 days) | OTP one tap from home (no seat-belt prompt first). Mic and precise location must not block booking or QR scan. | Product |
| 3 | **Login / OTP / logged out** | OTP fallback across SMS → WhatsApp → email after 30s with delivery logging. Tell users when their number isn't registered with their employer. Never expire a session within 2h of a scheduled trip; users get logged out at the cab door and lose the OTP. | App Eng |
| 4 | **Booking / schedule** | Month/list view of all bookings (users only see the next one, or none). Restore 1-step shuttle booking. Always show *Booked / Waitlisted / Not booked*. Let waitlisted users cancel. | Product |
| 5 | **Tracking / ETA** | Stop auto-resetting map zoom every ~30s. Show GPS staleness. Allow tracking from cab assignment, not only within 1h. Cache cab no., driver phone and OTP offline for the gate. | App Eng |
| 6 | **Pop-ups / banners** | Full-screen banners at most once and never near a trip. Transport policy acceptance once per policy version. | Product |
| 7+ | Drivers, routes, helpdesk, cab delays | Weekly per-client report from review mentions to transport desks and vendors. Proactive delay pushes. In-app ticket status. | Ops / Support |

Every item in the dashboard has a success metric, effort and real user quotes as evidence.

## How it works

```
Google Play ──► scrape.py ──► reviews.csv ──► classify.py ──► classified.csv ──► analyze.py ──► app.py (Streamlit)
  (public)     incremental     (de-duped)    Gemini, JSON     (+ issue tags)    stars at stake,   dashboard + action plan
                + rating                     schema; keyword                     releases, trends   + reply queue
                snapshot                     fallback                                     ▲
                                                                                          │
                          GitHub Actions: every Monday 08:00 IST ── re-run + commit data ─┘
```

- **Stars at stake** = Σ(5 − stars) of reviews whose main complaint is X ÷ all reviews. It is how much the
  average would rise if those reviews had been 5★, so issues are compared in rating points, not mention counts.
- **Priority** = stars at stake × ownership (app/product 1.0, ops 0.5) × trend. It re-ranks every run.
- **Release regression** = 1★ share ≥ 7 pp above the previous 5 releases (min 30 reviews).

### Run it yourself
```bash
python -m venv venv && venv\Scripts\activate      # Windows (source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
copy .env.example .env                              # add GEMINI_API_KEY (optional, free)
python -m pipeline.run                              # scrape + tag + print health report
streamlit run app.py                                # dashboard at http://localhost:8501
```
Without an API key everything still runs: reviews Gemini hasn't seen are tagged by the local ML backup (or keyword rules if there are no Gemini labels yet).

### Repo layout
```
app.py                      Streamlit dashboard
pipeline/config.py          apps tracked, paths
pipeline/scrape.py          incremental review + rating-snapshot scraper
pipeline/taxonomy.py        issue categories mapped to the employee journey, owner per issue
pipeline/classify.py        Gemini tagging (JSON-schema output, resumable, stops cleanly on free quota)
pipeline/local_model.py     offline backup: TF-IDF + logistic regression trained on Gemini's labels
pipeline/analyze.py         stars at stake, trends, release regressions, devices, reply queue
pipeline/recommendations.py action playbook (fix, owner, effort, metric)
pipeline/replies.py         Gemini-drafted replies to reviews
pipeline/run.py             one-command refresh; exits 2 on release regression (for CI alerts)
.github/workflows/refresh.yml  weekly scheduled refresh
data/                       reviews, tags, rating snapshots (committed so the dashboard needs no backend)
```

### Accuracy of the backup tagger
Gemini labelled the last 12 months of reviews (2,960). Older reviews, and any review Gemini can't reach
(no key, free quota used up, network down), are tagged by a local model trained on those labels.
On a held-out 20% of Gemini's labels (`python -m pipeline.local_model`):

| Tagger | Agrees with Gemini on main issue | on 1–2★ reviews |
|---|---|---|
| Local ML model | **88%** | **76%** |
| Keyword rules | 73% | 64% |
| Always guess most common | 66% | – |

## Assumptions & limits
- **Focus:** the employee app `com.moveinsync.ets`, which is where self-booking happens. Driver and field apps are
  tracked too, but have few reviews.
- **Written reviews are a vocal subset.** The all-time headline score includes star-only taps. The goal is to move
  the recent written-review mix, which drives the displayed score and what store visitors read.
- **Public data only** (Google Play, India store). Hinglish/Hindi reviews are included; Gemini reads them natively.
- **Stars at stake is an upper bound** on what fixing an issue can recover. It is for ranking, not forecasting.
- **Unstated 1★ reviews** ("worst app") can't be attributed. That's why recommendation 1 captures *what went wrong*
  in-app before the user reaches the store.

## Tools used
Python · google-play-scraper · pandas · **Google Gemini API** (review tagging with JSON-schema output, reply drafting) ·
scikit-learn (offline backup tagger) · Streamlit + Plotly · GitHub Actions (weekly refresh) · Streamlit Community Cloud (hosting) ·
Claude Code (AI pair-programmer for building the pipeline).
