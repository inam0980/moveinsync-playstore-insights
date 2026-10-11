"""Issue taxonomy, mapped to the employee journey described in the case study
(login -> book -> get pickup time -> track -> board -> ride -> raise an issue).

Each category has:
  - label: human name for the dashboard
  - owner: which team can actually fix it (App Engineering / Product / Operations / Support)
  - keywords: used by the offline fallback classifier (no API key needed)
"""

CATEGORIES = {
    "login_access": {
        "label": "Login / OTP / Logged out",
        "owner": "App Engineering",
        "keywords": [r"\blog ?in\b", r"\botp\b", r"sign ?in", r"\bsso\b", r"password", r"not registered",
                     r"account (is )?(not|in)activ", r"verification code", r"unable to (log|sign)",
                     r"logged out", r"logs? (me )?out", r"logging out", r"session", r"unauthori[sz]ed", r"authenticat"],
    },
    "app_crash_performance": {
        "label": "Crashes / Won't open / Slow",
        "owner": "App Engineering",
        "keywords": [r"crash", r"not (opening|loading|working)", r"doesn'?t (open|load|work)", r"\bhang",
                     r"\bslow\b", r"\blag", r"\bbug", r"glitch", r"freez", r"white screen", r"blank screen",
                     r"stuck", r"keeps? closing", r"server error", r"something went wrong", r"battery", r"error",
                     r"not open", r"not installed", r"won'?t open", r"can'?t open", r"closes", r"keeps loading",
                     r"not downloaded from (the )?play ?store"],
    },
    "booking_scheduling": {
        "label": "Booking / Schedule / Cancellation",
        "owner": "Product",
        "keywords": [r"\bbook", r"cancel", r"schedul", r"roster", r"\bslot", r"cut ?off", r"ad-?hoc",
                     r"shift time", r"request (a )?cab", r"reschedul", r"modify", r"wait ?-?list"],
    },
    "tracking_eta": {
        "label": "Live tracking / ETA / Map",
        "owner": "App Engineering",
        "keywords": [r"track", r"\bgps\b", r"\beta\b", r"location", r"\bmap", r"\bzoom", r"where (is )?the cab",
                     r"cab (is )?not (showing|visible)"],
    },
    "notifications": {
        "label": "Notifications / Cab & driver details",
        "owner": "App Engineering",
        "keywords": [r"notif", r"\bsms\b", r"message", r"alert", r"cab details", r"vehicle (number|details)",
                     r"driver (number|details)", r"no update"],
    },
    "forced_prompts": {
        "label": "Forced feedback / Pop-ups / Banners",
        "owner": "Product",
        "keywords": [r"feedback", r"rate (the |every )?(trip|ride)", r"forc(e|ed|ing)", r"\bskip", r"pop ?-?ups?",
                     r"banner", r"policy (message|pop)", r"seat ?belt"],
    },
    "noshow_checkin": {
        "label": "Marked no-show / Check-in / QR boarding",
        "owner": "Product",
        "keywords": [r"no ?-?show", r"check ?-?in", r"check ?-?out", r"\bscan", r"\bqr\b"],
    },
    "ui_ux": {
        "label": "Confusing UI / New update / Permissions",
        "owner": "Product",
        "keywords": [r"\bui\b", r"interface", r"confus", r"user friendly", r"complicated", r"design",
                     r"too many (steps|clicks)", r"not intuitive", r"difficult to use", r"new update",
                     r"old version", r"permission"],
    },
    "cab_delay": {
        "label": "Cab late / Not assigned / Driver didn't come",
        "owner": "Operations",
        "keywords": [r"\blate\b", r"delay", r"not assigned", r"never (came|arrived)", r"didn'?t (come|arrive)",
                     r"not (come|came|arrived)", r"miss(ed)? (the )?(pickup|cab|shift)", r"waiting", r"waited",
                     r"\bwait\b"],
    },
    "routing_pickup_time": {
        "label": "Long routes / Pickup time too early",
        "owner": "Operations",
        "keywords": [r"\brout(e|ing)", r"pick ?up time", r"too early", r"hours? (in|before)", r"long (route|trip|ride)",
                     r"detour", r"wrong (address|location)", r"travel time"],
    },
    "driver_vehicle": {
        "label": "Driver behaviour / Vehicle condition",
        "owner": "Operations",
        "keywords": [r"driver", r"rash", r"rude", r"\bac\b", r"vehicle condition", r"dirty", r"smok",
                     r"speed", r"behaviou?r"],
    },
    "safety": {
        "label": "Safety / SOS / Escort",
        "owner": "Operations",
        "keywords": [r"safe", r"\bsos\b", r"escort", r"women", r"harass", r"emergency", r"guard"],
    },
    "support_grievance": {
        "label": "Helpdesk / Complaints ignored",
        "owner": "Support",
        "keywords": [r"support", r"complain", r"help ?desk", r"help ?line", r"customer care", r"no response",
                     r"grievance", r"ticket", r"transport (desk|team)", r"escalat"],
    },
    "praise": {
        "label": "Praise (no issue)",
        "owner": "-",
        "keywords": [r"\bgood\b", r"\bnice\b", r"\bgreat\b", r"excellent", r"awesome", r"helpful", r"\bbest\b",
                     r"\blove", r"useful", r"easy", r"convenient", r"smooth", r"super"],
    },
    "other": {
        "label": "Vague (no specific reason)",
        "owner": "-",
        "keywords": [],
    },
}

ISSUE_CATEGORIES = [k for k in CATEGORIES if k not in ("praise", "other")]
# Issues the app/product team can fix directly (vs. on-ground operations run by vendors / transport desks)
APP_OWNED = {k for k, v in CATEGORIES.items() if v["owner"] in ("App Engineering", "Product")}


def label(cat: str) -> str:
    return CATEGORIES.get(cat, CATEGORIES["other"])["label"]


def owner(cat: str) -> str:
    return CATEGORIES.get(cat, CATEGORIES["other"])["owner"]
