"""Standalone probe against waste.havant.gov.uk.

Loads creds from .env (HAVANT_USERNAME / HAVANT_PASSWORD), logs in, fetches the
landing page, extracts the embedded collection events JSON, and prints the
distinct Subject strings + a few sample rows so we can build a complete icon
map for the HA integration.

Not shipped with the integration — kept under scripts/ for local recon only.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys

import requests
from bs4 import BeautifulSoup

BASE = "https://waste.havant.gov.uk"
LOGIN_URL = f"{BASE}/Identity/Account/Login"
EVENTS_RE = re.compile(r"eventSettings.*?dataSource.*?isJson\((\[.*?\])\)", re.DOTALL)


def load_env(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_env(pathlib.Path(__file__).resolve().parent.parent / ".env")
    username = os.environ.get("HAVANT_USERNAME")
    password = os.environ.get("HAVANT_PASSWORD")
    if not username or not password:
        print("HAVANT_USERNAME / HAVANT_PASSWORD missing from .env", file=sys.stderr)
        return 2

    s = requests.Session()
    s.headers["User-Agent"] = "ha-vant-waste-recon/0.1"

    r = s.get(LOGIN_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    tok = soup.find("input", attrs={"name": "__RequestVerificationToken"})
    if not tok or not tok.get("value"):
        print("No anti-forgery token on login page", file=sys.stderr)
        return 3
    token = tok["value"]

    r = s.post(
        LOGIN_URL,
        data={
            "Input.Email": username,
            "Input.Password": password,
            "__RequestVerificationToken": token,
            "Input.RememberMe": "false",
        },
        timeout=30,
        allow_redirects=True,
    )
    r.raise_for_status()
    if "/Identity/Account/Login" in r.url:
        print(f"Login failed; redirected back to {r.url}", file=sys.stderr)
        return 4

    print(f"Logged in; landed on {r.url}", file=sys.stderr)

    r = s.get(BASE, timeout=30)
    r.raise_for_status()

    m = EVENTS_RE.search(r.text)
    if not m:
        landing = pathlib.Path("/tmp/havant_landing.html")
        landing.write_text(r.text)
        print(
            f"Events regex did not match; full landing page saved to {landing}",
            file=sys.stderr,
        )
        return 5

    events = json.loads(m.group(1))
    subjects = sorted({e.get("Subject", "").strip() for e in events})
    print(f"Found {len(events)} events across {len(subjects)} waste types", file=sys.stderr)

    print(json.dumps(
        {
            "subjects": subjects,
            "sample": events[:6],
            "next_per_subject": {
                subj: next(
                    (
                        e["StartTime"]
                        for e in sorted(events, key=lambda e: e["StartTime"])
                        if e.get("Subject", "").strip() == subj
                        and dt.datetime.fromisoformat(e["StartTime"]).date()
                        >= dt.date.today()
                    ),
                    None,
                )
                for subj in subjects
            },
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
