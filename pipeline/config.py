"""Central config: which apps to track and where data lives."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REVIEWS_CSV = DATA_DIR / "reviews.csv"          # raw reviews (append-only, de-duplicated)
CLASSIFIED_CSV = DATA_DIR / "classified.csv"    # reviews + AI tags
SNAPSHOTS_CSV = DATA_DIR / "snapshots.csv"      # app-level rating over time (one row per run per app)

# MoveInSync apps on Google Play (developer: "MoveInSync: Enabling Hybrid Workplaces").
# The employee app is the one the case study is about; driver/field apps are tracked for context.
APPS = {
    "com.moveinsync.ets": "MoveInSync (Employee)",
    "com.moveinsync.driver.lite": "MoveInSync Partner - Lite (Driver)",
    "com.moveinsync.driver.dco": "MoveInSync - Driver Partner",
    "field.moveinsync.ets": "MoveInSync - Field app",
}
PRIMARY_APP = "com.moveinsync.ets"

# Competitors in the same space, used for benchmarking only.
COMPETITORS = {
    "com.routematic.employee": "Routematic (Employee)",
    "xdk.intel.cordova.template.eTMSBuddy": "eTMS Buddy (Delta)",
}

LANG = "en"
COUNTRY = "in"
MAX_REVIEWS_PER_APP = 30000  # safety cap per run
