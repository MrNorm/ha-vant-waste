"""Constants for the Havant Waste integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "havant_waste"

BASE_URL = "https://waste.havant.gov.uk"
LOGIN_PATH = "/Identity/Account/Login"

DEFAULT_SCAN_INTERVAL = timedelta(hours=6)
BIN_DAY_SCAN_INTERVAL = timedelta(minutes=30)

# Council marks completed jobs with this Status string. Anything else on
# a today-dated row means the bin has not yet been emptied.
COMPLETED_STATUS = "Closed-Complete"

ICON_MAP: dict[str, str] = {
    "Residual 240L": "mdi:trash-can",
    "Recycling 240L": "mdi:recycle",
    "Garden 240L": "mdi:leaf",
    "Food caddy 23L": "mdi:food-apple",
}
DEFAULT_ICON = "mdi:trash-can"
