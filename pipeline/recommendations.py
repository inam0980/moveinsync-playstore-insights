"""Action playbook. Each entry is written so a team can start the next day:
what to change, who owns it, rough effort, and the metric that proves it worked.

The dashboard orders these by the live `priority` from analyze.issue_impact(), so the plan
re-ranks itself every time the pipeline runs.
"""

# Cross-cutting moves that aren't tied to one complaint category. Always shown first:
# they're cheap, fast, and act on the rating mechanism itself.
QUICK_WINS = [
    {
        "title": "Stop forcing trip feedback; route happy riders to the Play Store prompt instead",
        "why": "The app blocks use until a trip is rated, twice a day. Users say so in reviews and leave 1 star "
               "on the Play Store in protest. Meanwhile the ~65% of reviewers who are happy are never asked.",
        "what": [
            "Add a 'Skip' on the post-trip rating screen; never block booking/OTP behind it.",
            "When a rider gives 4-5 stars in-app on an on-time trip, call Google Play In-App Review API "
            "(ReviewManager.requestReviewFlow). At most once per 90 days per user, never after a late/no-show trip.",
            "When a rider gives 1-3 stars in-app, open a 'What went wrong?' form that creates a ticket "
            "instead of sending them to the store.",
        ],
        "owner": "Product + App Engineering", "effort": "S (1 sprint)",
        "metric": "Share of 5-star reviews per week; count of reviews mentioning feedback/rating/skip -> 0.",
    },
    {
        "title": "Restart replying to Play Store reviews (reply rate on 1-2 star reviews: {reply_peak:.0%} at peak, {reply_now:.0%} now)",
        "why": "Developer replies collapsed after mid-2024. Google lets reviewers "
               "edit their rating after a reply, and replies are public proof to prospective users and HR buyers.",
        "what": [
            "Reply to every 1-2 star review within 48h. Use this repo's reply queue: Claude drafts a "
            "category-specific reply, a support agent edits and posts.",
            "When a fix ships for a category, reply again to those reviewers: 'Fixed in 12.x, please update'.",
            "Route reviews that name a company/route/date to that client's transport desk as a ticket.",
        ],
        "owner": "Support", "effort": "S (start this week)",
        "metric": "Reply rate on 1-2 star reviews >= 90%; median time-to-reply < 48h; rating edits after reply.",
    },
    {
        "title": "Gate releases on review health (staged rollout + automatic regression alert)",
        "why": "{n_reg} of the last {n_rel} releases had 7+ points more 1-star reviews than the releases before them "
               "({reg_list}). Each bad release costs weeks of rating.",
        "what": [
            "Ship every release via Play Console staged rollout (5% -> 20% -> 100%).",
            "Run this pipeline daily during a rollout; if the new version's 1-star share is 7+ points above "
            "the last 5 releases, halt the rollout (Play Console 'Halt rollout').",
            "Add Android vitals (crash rate, ANR rate) thresholds to the release checklist.",
        ],
        "owner": "App Engineering (release manager)", "effort": "S",
        "metric": "No release with 1-star share > baseline + 7pp reaches 100% rollout.",
    },
]

# Per-category fixes, keyed by taxonomy category.
PLAYBOOK = {
    "app_crash_performance": {
        "fix": [
            "P0 for 12.19.x: app fails to open / closes instantly on Pixel 8 (Android 17), OnePlus 12, "
            "Vivo V25 Pro. Reproduce on those devices; check Android vitals crash clusters for 12.19.0.",
            "P0: since June 2026 users intermittently get 'app can't be opened, not downloaded from Play Store'. This is the Play Integrity / "
            "installer-source check failing for genuine installs (e.g. after device restore or Play auto-update). "
            "Fail open: log + soft-warn instead of blocking, and verify via Play Integrity API server-side.",
            "Fix 'keeps loading' on Wi-Fi ('we're nothing without internet' on working Wi-Fi): "
            "connectivity check should test the API, not the network type.",
        ],
        "effort": "M", "metric": "Crash-free users >= 99.5%; 'won't open' mentions per week -> near 0.",
    },
    "login_access": {
        "fix": [
            "OTP delivery: add delivery-status logging per channel (SMS/WhatsApp/email), auto-fallback to the "
            "next channel after 30s, and show 'resend in 30s' with the masked destination.",
            "Tell the user when the phone/email isn't registered with their employer, instead of a silent "
            "no-OTP. Show who to contact (their transport desk).",
            "Stop logging users out mid-trip: extend refresh-token lifetime; never expire a session while a "
            "trip is scheduled within the next 2 hours.",
        ],
        "effort": "M", "metric": "OTP success rate (requested -> verified) >= 97%; logout complaints -> near 0.",
    },
    "booking_scheduling": {
        "fix": [
            "Show all upcoming bookings in a month/list view (users report only the next trip is visible, "
            "or bookings confirmed by the travel desk don't appear).",
            "Restore the 1-step shuttle booking the last redesign removed; show an explicit "
            "'Booked / Waitlisted / Not booked' state after every booking attempt.",
            "Let waitlisted users cancel or switch slots; fix the default date bug (Sunday booking defaulting to Tuesday).",
        ],
        "effort": "M", "metric": "Booking success rate; 'booking not showing' mentions per week.",
    },
    "tracking_eta": {
        "fix": [
            "Stop auto-resetting map zoom every ~30s; once the user pans/zooms, keep their view until they tap 'recenter'.",
            "Show the ETA source/last GPS update time; flag stale driver GPS (> 60s) instead of showing a wrong position.",
            "Allow tracking from the moment a cab is assigned (12.19 limited it to < 1 hour before pickup).",
            "Cache cab number, driver phone and boarding OTP offline so they survive network loss at the gate.",
        ],
        "effort": "M", "metric": "ETA error (predicted vs actual pickup) p50/p90; tracking complaints per week.",
    },
    "ui_ux": {
        "fix": [
            "Remove extra taps added in recent updates (e.g. seat-belt prompt before 'View OTP'); OTP must be one tap from home.",
            "Make permissions optional: microphone and 'precise location' must not block booking or QR scanning.",
            "Before big UI changes, run a 5% staged rollout + in-app 'new design' feedback chip.",
        ],
        "effort": "S", "metric": "Taps to OTP = 1; 'new update / confusing' mentions per week.",
    },
    "forced_prompts": {
        "fix": [
            "Covered by Quick Win #1 (skippable trip feedback).",
            "Show marketing/full-screen banners at most once, never on launch when a trip is within 2 hours.",
            "Show the transport policy acceptance once per policy version, not on every launch.",
        ],
        "effort": "S", "metric": "Mentions of popup/banner/feedback/skip -> near 0.",
    },
    "notifications": {
        "fix": [
            "Push cab number, driver name and OTP as soon as a cab is assigned; resend on any change.",
            "Fix false 'trip not booked' pushes after a successful booking (reported on 12.19.0).",
            "Collapse stacked notifications per trip so the latest one is always visible.",
        ],
        "effort": "S", "metric": "% trips where cab details were pushed >= 30 min before pickup.",
    },
    "noshow_checkin": {
        "fix": [
            "Send a 'Your cab is here, check in' push + countdown before marking no-show.",
            "Never mark no-show if the pickup time changed within the last X hours without the user acknowledging.",
            "Show no-show count and an in-app dispute button (goes to transport desk).",
        ],
        "effort": "S", "metric": "No-show disputes; no-show complaints per week.",
    },
    "routing_pickup_time": {
        "fix": [
            "Give transport desks a weekly report of routes with the longest ride times and largest gaps between "
            "same-building pickups (users report 5-min gaps for neighbours).",
            "Notify users of any pickup-time change with a reason; show the planned route length.",
        ],
        "effort": "M (ops + routing)", "metric": "Avg ride time vs direct-drive time per route.",
    },
    "driver_vehicle": {
        "fix": [
            "Feed in-app driver ratings + review mentions into vendor scorecards each week; auto-flag drivers with repeat complaints.",
            "Add a 'Report driver' shortcut on the trip screen (goes to ops, not the Play Store).",
        ],
        "effort": "M (ops)", "metric": "Driver complaints per 1,000 trips by vendor.",
    },
    "support_grievance": {
        "fix": [
            "Add in-app ticket status ('Received / With transport desk / Resolved') so users see progress.",
            "Add chat/callback when the helpdesk line is busy.",
        ],
        "effort": "M", "metric": "Ticket resolution time; 'helpdesk useless' mentions.",
    },
    "cab_delay": {
        "fix": [
            "Proactive delay push with a new ETA when the cab is running > 10 min late.",
            "Share a per-client delay report with transport desks (from trip data + review mentions).",
        ],
        "effort": "M (ops)", "metric": "On-time pickup %; delay complaints per week.",
    },
    "safety": {
        "fix": [
            "Keep SOS and trip-share reachable without login (lock-screen/notification action) - users note "
            "auto-logout blocks urgent reporting.",
        ],
        "effort": "S", "metric": "SOS reachable when logged out; safety mentions.",
    },
}
