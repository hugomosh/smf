#!/usr/bin/env python3
"""Fetch Mexico women's national team fixtures and write docs/fixtures.json.

Sources (verified 2026-07-25, see README):
  - ESPN unofficial API, team id 2812 == senior women's team (slug "mex.w").
      upcoming: site.web.api.espn.com .../soccer/all/teams/2812/schedule?fixture=true
      results:  site.api.espn.com  .../soccer/all/teams/2812/schedule
  - miseleccion.mx/json/calendario.json is the official cross-check (not fetched here).

This script only fetches + normalizes. ICS rendering lives in ics.py.
Never exits non-zero on fetch failure: the previous fixtures.json is kept so
the published calendar survives ESPN outages.

Stdlib only.
"""
import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TEAM_ID = "2812"  # ESPN id for Mexico women's SENIOR team ("mex.w")
FIXTURES_PATH = Path(__file__).parent / "docs" / "fixtures.json"

UPCOMING_URL = ("https://site.web.api.espn.com/apis/site/v2/sports/soccer/all/"
                f"teams/{TEAM_ID}/schedule?fixture=true")
RESULTS_URL = ("https://site.api.espn.com/apis/site/v2/sports/soccer/all/"
               f"teams/{TEAM_ID}/schedule")

UA = {"User-Agent": "smf-calendar/1.0 (+https://github.com/hugomosh/smf)"}

# Belt and braces: team id 2812 is already the senior women's side, but if a
# youth or men's event ever sneaks into its schedule feed, drop it here.
# Inspect exclusions in the run log ("EXCLUDED:" lines).
JUNIOR_MARKERS = ("u-17", "u17", "sub-17", "u-20", "u20", "sub-20",
                  "u-23", "u23", "sub-23", "under-17", "under-20", "under-23")


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_json(url, retries=3, timeout=20):
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 2 ** attempt
            print(f"fetch failed ({e}), retry in {wait}s: {url}", file=sys.stderr)
            time.sleep(wait)
    print(f"giving up on {url}: {last_err}", file=sys.stderr)
    return None


def is_senior_femenil(event):
    """Return (ok, reason). The event must involve team 2812 and not look junior."""
    comp = (event.get("competitions") or [{}])[0]
    ids = {str((c.get("team") or {}).get("id")) for c in comp.get("competitors", [])}
    if TEAM_ID not in ids:
        return False, f"team {TEAM_ID} not in competitors {ids}"
    haystack = " ".join([
        (event.get("league") or {}).get("name") or "",
        event.get("name") or "",
        (event.get("seasonType") or {}).get("name") or "",
    ]).lower()
    for marker in JUNIOR_MARKERS:
        if marker in haystack:
            return False, f"junior marker {marker!r} in {haystack!r}"
    return True, ""


def normalize_event(event):
    """ESPN event -> normalized match dict (source-agnostic shape)."""
    comp = (event.get("competitions") or [{}])[0]
    status_type = ((comp.get("status") or {}).get("type") or {})
    sides = {}
    for c in comp.get("competitors", []):
        team = c.get("team") or {}
        score = c.get("score")
        if isinstance(score, dict):
            score = score.get("displayValue")
        sides[c.get("homeAway", "home")] = {
            "id": str(team.get("id")),
            "name": team.get("displayName") or team.get("name"),
            "score": None if score in (None, "") else str(score),
        }
    state = status_type.get("state", "pre")  # pre | in | post
    venue = comp.get("venue") or {}
    venue_name = venue.get("fullName")
    address = venue.get("address") or {}
    city = ", ".join(x for x in (address.get("city"), address.get("country")) if x)
    broadcasts = []
    for b in comp.get("broadcasts", []):
        names = b.get("media", {}).get("shortName") or ""
        if isinstance(b.get("names"), list):
            names = ", ".join(b["names"])
        if names:
            broadcasts.append(names)
    # date like "2026-11-28T20:00Z"
    date_raw = comp.get("date") or event.get("date") or ""
    return {
        "id": f"espn-{event.get('id')}",
        "source": "espn",
        "date_utc": date_raw,
        "time_valid": bool(comp.get("timeValid", event.get("timeValid", True))),
        "state": state,
        "status": status_type.get("name"),
        "status_detail": status_type.get("shortDetail") or status_type.get("detail"),
        "home": sides.get("home"),
        "away": sides.get("away"),
        "competition": (event.get("league") or {}).get("name"),
        "round": (event.get("seasonType") or {}).get("name"),
        "venue": venue_name,
        "venue_city": city or None,
        "broadcast": ", ".join(broadcasts) or None,
    }


def fingerprint(match):
    """Hash of every field that affects the rendered ICS event."""
    keys = ("date_utc", "time_valid", "state", "status", "status_detail",
            "home", "away", "competition", "round", "venue", "venue_city",
            "broadcast")
    canon = json.dumps({k: match.get(k) for k in keys}, sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()[:16]


def load_previous():
    if FIXTURES_PATH.exists():
        try:
            return {m["id"]: m for m in json.loads(FIXTURES_PATH.read_text())["matches"]}
        except Exception as e:  # noqa: BLE001
            print(f"could not parse previous fixtures.json: {e}", file=sys.stderr)
    return {}


def main():
    fetched = {}
    ok_any = False
    for url in (RESULTS_URL, UPCOMING_URL):  # upcoming last: fresher for 'pre' games
        data = fetch_json(url)
        if data is None:
            continue
        ok_any = True
        team = data.get("team", {})
        print(f"source ok: {url}\n  team={team.get('id')} {team.get('displayName')!r} "
              f"events={len(data.get('events', []))}")
        for event in data.get("events", []):
            ok, reason = is_senior_femenil(event)
            if not ok:
                print(f"EXCLUDED: event {event.get('id')} {event.get('name')!r}: {reason}")
                continue
            match = normalize_event(event)
            fetched[match["id"]] = match

    if not ok_any:
        print("all sources failed; keeping previous fixtures.json untouched")
        return 0

    previous = load_previous()
    # Matches ESPN no longer returns (rolled out of its window) are kept as-is,
    # so calendar history never disappears.
    merged = dict(previous)
    changed = 0
    for mid, match in fetched.items():
        fp = fingerprint(match)
        old = previous.get(mid)
        if old is None:
            match["seq"] = 0
            match["fingerprint"] = fp
            match["last_modified_utc"] = now_utc()
            print(f"NEW: {mid} {match['home']['name']} vs {match['away']['name']} {match['date_utc']}")
            changed += 1
        elif old.get("fingerprint") != fp:
            match["seq"] = int(old.get("seq", 0)) + 1
            match["fingerprint"] = fp
            match["last_modified_utc"] = now_utc()
            print(f"UPDATED (seq {match['seq']}): {mid}")
            changed += 1
        else:
            match = old
        merged[mid] = match

    out = {
        "team_id": TEAM_ID,
        "matches": sorted(merged.values(), key=lambda m: m["date_utc"]),
    }
    FIXTURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {FIXTURES_PATH}: {len(merged)} matches, {changed} new/updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
